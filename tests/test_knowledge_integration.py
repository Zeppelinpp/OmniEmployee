"""Test knowledge learning integration with agent."""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


async def test_main_integration():
    """Test knowledge learning through main.py components."""
    print("\n=== Testing Main.py Integration ===\n")
    
    # Import components from main.py
    from src.omniemployee.memory.knowledge import (
        KnowledgeLearningPlugin,
        KnowledgePluginConfig,
        KnowledgeStoreConfig,
        KnowledgeVectorConfig,
    )
    from src.omniemployee.llm import LLMProvider, LLMConfig
    import uuid
    
    # Create config like main.py does
    session_id = str(uuid.uuid4())[:8]
    
    store_config = KnowledgeStoreConfig(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "biem"),
        user=os.getenv("POSTGRES_USER", ""),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )
    
    vector_config = KnowledgeVectorConfig(
        host=os.getenv("MILVUS_HOST", "localhost"),
        port=int(os.getenv("MILVUS_PORT", "19530")),
        collection_name="biem_knowledge",
        use_lite=os.getenv("MILVUS_USE_LITE", "false").lower() == "true",
    )
    
    config = KnowledgePluginConfig(
        store_config=store_config,
        vector_config=vector_config,
        enable_vector_search=True,  # Enable for real test
        user_id="main_test_user",
        session_id=session_id,
    )
    
    # Create LLM provider
    model = os.getenv("MODEL", "gpt-4o")
    llm = LLMProvider(LLMConfig(model=model, temperature=0.3))
    
    print(f"Model: {model}")
    print(f"Session: {session_id}")
    
    # Initialize plugin
    plugin = KnowledgeLearningPlugin(config)
    
    # Try to get encoder from memory system
    encoder = None
    try:
        from src.omniemployee.memory.operators import Encoder
        encoder = Encoder()
        await encoder.initialize()
        print("✓ Encoder initialized")
    except Exception as e:
        print(f"⚠ Encoder not available: {e}")
    
    await plugin.initialize(llm, encoder)
    
    if not plugin.is_available():
        print("✗ Plugin not available")
        return False
    
    print("✓ Knowledge plugin initialized")
    
    # Simulate conversation
    test_messages = [
        "Claude的最大输出token是8192",
        "Anthropic在2024年发布了Claude 3.5",
        "其实Claude 3.5 Sonnet的输出限制已经更新到64k了",  # Should trigger conflict
    ]
    
    print("\n--- Simulating Conversation ---\n")
    
    for msg in test_messages:
        print(f"User: {msg}")
        
        # Check for pending confirmation
        handled, response = await plugin.process_confirmation_response(msg)
        if handled:
            print(f"Agent: {response}")
            continue
        
        # Process message
        result = await plugin.process_message(msg, role="user")
        
        if result.action == "stored":
            n = len(result.triples_stored)
            print(f"  📚 Learned {n} new fact(s)")
            for t in result.triples_stored:
                print(f"     -> {t.display()}")
        elif result.action == "conflict":
            for prompt in result.confirmation_prompts:
                print(f"  ❓ {prompt}")
        
        print()
    
    # Simulate user confirming the update
    print("User: 是的")
    handled, response = await plugin.process_confirmation_response("是的")
    if handled:
        print(f"Agent: {response}")
    
    # Show final knowledge state
    print("\n--- Final Knowledge State ---\n")
    
    all_knowledge = await plugin.get_all_knowledge(limit=20)
    print(f"Total triples: {len(all_knowledge)}")
    for k in all_knowledge:
        print(f"  - {k.display()} [v{k.version}] [{k.source.value}]")
        if k.previous_values:
            print(f"    History: {k.previous_values}")
    
    # Test context injection
    print("\n--- Context Injection Test ---\n")
    
    context = await plugin.get_context_for_query("Claude的输出限制是多少")
    print(f"Query: 'Claude的输出限制是多少'")
    print(f"Context:\n{context}")
    
    # Cleanup
    await plugin.shutdown()
    print("\n✓ Test complete")
    
    return True


if __name__ == "__main__":
    asyncio.run(test_main_integration())
