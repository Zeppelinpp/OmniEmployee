"""Test script for Knowledge Learning System."""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


async def test_knowledge_store():
    """Test PostgreSQL knowledge store."""
    print("\n=== Testing Knowledge Store (PostgreSQL) ===\n")
    
    from src.omniemployee.memory.knowledge import (
        KnowledgeStore,
        KnowledgeStoreConfig,
        KnowledgeTriple,
        KnowledgeSource,
    )
    
    config = KnowledgeStoreConfig(
        host="localhost",
        port=5432,
        database="biem",
    )
    
    store = KnowledgeStore(config)
    
    try:
        await store.connect()
        print("✓ Connected to PostgreSQL")
        
        # Create a test triple
        triple = KnowledgeTriple(
            subject="Python",
            predicate="created_by",
            object="Guido van Rossum",
            confidence=0.95,
            source=KnowledgeSource.USER_STATED,
            user_id="test_user",
            session_id="test_session",
        )
        
        # Store it
        triple_id = await store.store(triple)
        print(f"✓ Stored triple: {triple.display()} -> id={triple_id[:8]}...")
        
        # Query by subject
        results = await store.query_by_subject("Python", "test_user")
        print(f"✓ Query by subject 'Python': found {len(results)} triple(s)")
        for r in results:
            print(f"  - {r.display()} [v{r.version}]")
        
        # Search
        results = await store.search("Python creator", "test_user")
        print(f"✓ Full-text search 'Python creator': found {len(results)} result(s)")
        
        # Get stats
        stats = await store.get_stats("test_user")
        print(f"✓ Stats: {stats}")
        
        # Test update (conflict scenario)
        triple2 = KnowledgeTriple(
            subject="Python",
            predicate="created_by",
            object="Guido",  # Shorter version
            confidence=0.9,
            source=KnowledgeSource.USER_CORRECTION,
            user_id="test_user",
        )
        
        await store.store(triple2)
        
        # Check version incremented
        updated = await store.get_by_subject_predicate("Python", "created_by", "test_user")
        if updated:
            print(f"✓ After conflict update: {updated.display()}")
            print(f"  - Version: {updated.version}")
            print(f"  - Previous values: {updated.previous_values}")
        
        await store.disconnect()
        print("✓ Disconnected from PostgreSQL")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_knowledge_extractor():
    """Test LLM-driven knowledge extraction."""
    print("\n=== Testing Knowledge Extractor (LLM) ===\n")
    
    from src.omniemployee.memory.knowledge import KnowledgeExtractor, ExtractorConfig
    from src.omniemployee.llm import LLMProvider, LLMConfig
    
    # Use configured model
    model = os.getenv("MODEL", "gpt-4o")
    llm_config = LLMConfig(model=model, temperature=0.3)
    llm = LLMProvider(llm_config)
    
    extractor = KnowledgeExtractor(config=ExtractorConfig(min_confidence=0.5))
    await extractor.initialize(llm)
    
    if not extractor.is_available():
        print("✗ Extractor not available (no LLM)")
        return False
    
    print(f"✓ Using model: {model}")
    
    test_cases = [
        ("Claude 3.5 Sonnet has a context window of 200k tokens", True),
        ("I think Python is the best language", False),  # Opinion
        ("What's the capital of France?", False),  # Question
        ("GPT-4 was released in March 2023", True),
    ]
    
    for msg, should_be_factual in test_cases:
        result = await extractor.extract(msg)
        status = "✓" if result.is_factual == should_be_factual else "✗"
        print(f"{status} '{msg[:50]}...'")
        print(f"   is_factual={result.is_factual}, intent={result.intent.value}")
        if result.triples:
            for t in result.triples:
                print(f"   -> {t.display()}")
    
    return True


async def test_conflict_detection():
    """Test conflict detection and confirmation flow."""
    print("\n=== Testing Conflict Detection ===\n")
    
    from src.omniemployee.memory.knowledge import (
        KnowledgeStore,
        KnowledgeStoreConfig,
        KnowledgeTriple,
        KnowledgeSource,
        KnowledgeConflictDetector,
        ConflictConfig,
    )
    
    config = KnowledgeStoreConfig(host="localhost", port=5432, database="biem")
    store = KnowledgeStore(config)
    await store.connect()
    
    detector = KnowledgeConflictDetector(store, ConflictConfig())
    
    # Ensure we have an existing triple
    existing = KnowledgeTriple(
        subject="GPT-4",
        predicate="context_window",
        object="8k tokens",
        user_id="test_user",
        source=KnowledgeSource.USER_STATED,
    )
    await store.store(existing)
    print(f"✓ Stored existing: {existing.display()}")
    
    # Try to add conflicting knowledge
    new_triple = KnowledgeTriple(
        subject="GPT-4",
        predicate="context_window",
        object="128k tokens",  # Different value!
        user_id="test_user",
        source=KnowledgeSource.USER_STATED,
    )
    
    conflict = await detector.check(new_triple)
    
    if conflict.has_conflict:
        print(f"✓ Conflict detected!")
        print(f"   Existing: {conflict.existing_triple.display()}")
        print(f"   New: {conflict.new_triple.display()}")
        print(f"   Suggestion: {conflict.suggestion}")
    else:
        print("✗ No conflict detected (unexpected)")
    
    await store.disconnect()
    return conflict.has_conflict


async def test_full_integration():
    """Test the full KnowledgeLearningPlugin."""
    print("\n=== Testing Full Integration ===\n")
    
    from src.omniemployee.memory.knowledge import (
        KnowledgeLearningPlugin,
        KnowledgePluginConfig,
        KnowledgeStoreConfig,
        KnowledgeVectorConfig,
    )
    from src.omniemployee.llm import LLMProvider, LLMConfig
    
    model = os.getenv("MODEL", "gpt-4o")
    llm = LLMProvider(LLMConfig(model=model, temperature=0.3))
    
    config = KnowledgePluginConfig(
        store_config=KnowledgeStoreConfig(host="localhost", port=5432, database="biem"),
        vector_config=KnowledgeVectorConfig(host="localhost", port=19530),
        enable_vector_search=False,  # Disable for simpler test
        user_id="integration_test",
        session_id="test_session_1",
    )
    
    plugin = KnowledgeLearningPlugin(config)
    await plugin.initialize(llm)
    
    if not plugin.is_available():
        print("✗ Plugin not available")
        return False
    
    print("✓ Plugin initialized")
    
    # Test 1: Store new knowledge
    result = await plugin.process_message("Python was created by Guido van Rossum in 1991")
    print(f"\nTest 1 - New knowledge:")
    print(f"  Action: {result.action}")
    if result.triples_stored:
        for t in result.triples_stored:
            print(f"  Stored: {t.display()}")
    
    # Test 2: Query related knowledge
    context = await plugin.get_context_for_query("Who created Python?")
    print(f"\nTest 2 - Context for 'Who created Python?':")
    print(context if context else "  (no context)")
    
    # Test 3: Get all knowledge
    all_knowledge = await plugin.get_all_knowledge()
    print(f"\nTest 3 - All knowledge for user:")
    for k in all_knowledge[:5]:
        print(f"  - {k.display()} [{k.source.value}]")
    
    # Test 4: Stats
    stats = await plugin.get_stats()
    print(f"\nTest 4 - Stats: {stats}")
    
    await plugin.shutdown()
    print("\n✓ Plugin shutdown complete")
    
    return True


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Knowledge Learning System Tests")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Knowledge Store
    results["store"] = await test_knowledge_store()
    
    # Test 2: Conflict Detection
    results["conflict"] = await test_conflict_detection()
    
    # Test 3: Knowledge Extractor (requires LLM)
    try:
        results["extractor"] = await test_knowledge_extractor()
    except Exception as e:
        print(f"✗ Extractor test failed: {e}")
        results["extractor"] = False
    
    # Test 4: Full Integration
    try:
        results["integration"] = await test_full_integration()
    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        results["integration"] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(results.values())
    print(f"\nOverall: {'All tests passed!' if all_passed else 'Some tests failed'}")
    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
