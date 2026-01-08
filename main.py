"""OmniEmployee - Main entry point with BIEM memory and knowledge learning integration."""

import asyncio
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

# Load environment variables from .env file
load_dotenv()

from src.omniemployee.core import Agent, AgentConfig, AgentLoop, LoopConfig, LoopState
from src.omniemployee.llm import LLMProvider
from src.omniemployee.memory import BIEMContextPlugin, MemoryConfig
from src.omniemployee.memory.storage import MilvusConfig, PostgresConfig
from src.omniemployee.memory.knowledge import (
    KnowledgeLearningPlugin,
    KnowledgePluginConfig,
    KnowledgeStoreConfig,
    KnowledgeVectorConfig,
)

console = Console()


def create_memory_config() -> MemoryConfig:
    """Create memory configuration from environment."""
    milvus_config = MilvusConfig(
        collection_name=os.getenv("MILVUS_COLLECTION", "biem_memories"),
        use_lite=os.getenv("MILVUS_USE_LITE", "false").lower() == "true",
    )
    
    postgres_config = PostgresConfig(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "biem"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )
    
    return MemoryConfig(
        milvus_config=milvus_config,
        postgres_config=postgres_config,
        auto_start_tasks=False,  # Don't start background tasks in interactive mode
    )


def create_knowledge_config(session_id: str, user_id: str = "") -> KnowledgePluginConfig:
    """Create knowledge learning configuration from environment."""
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
    
    return KnowledgePluginConfig(
        store_config=store_config,
        vector_config=vector_config,
        enable_vector_search=os.getenv("KNOWLEDGE_VECTOR_SEARCH", "true").lower() == "true",
        user_id=user_id or os.getenv("USER_ID", "default"),
        session_id=session_id,
    )


def print_welcome(
    agent: Agent,
    loop: AgentLoop,
    memory: BIEMContextPlugin | None,
    knowledge: KnowledgeLearningPlugin | None = None,
):
    """Print welcome message."""
    provider_info = loop.llm.get_provider_info()

    memory_status = "[green]Enabled[/green]" if memory else "[yellow]Disabled[/yellow]"
    knowledge_status = "[green]Enabled[/green]" if knowledge and knowledge.is_available() else "[yellow]Disabled[/yellow]"
    
    console.print(
        Panel.fit(
            "[bold blue]OmniEmployee[/bold blue] - AI Coding Assistant\n"
            f"Workspace: {agent.workspace_root}\n"
            f"Provider: {provider_info['provider']}\n"
            f"Model: {provider_info['model']}\n"
            f"Memory: {memory_status}\n"
            f"Knowledge Learning: {knowledge_status}",
            title="Welcome",
        )
    )

    # Print available skills
    stats = agent.get_stats()
    if stats["skills"]["available"]:
        console.print(
            f"\n[dim]Available skills: {', '.join(stats['skills']['available'])}[/dim]"
        )

    # Print available tools
    console.print(f"[dim]Available tools: {', '.join(stats['tools'])}[/dim]")

    console.print(
        "\n[dim]Commands: 'quit' to exit, 'stats' for info, 'memory' for memory stats, 'knowledge' for learned facts, 'clear' to reset[/dim]\n"
    )


def print_models():
    """Print available models."""
    models = LLMProvider.list_models()
    console.print("\n[bold]Available Models:[/bold]")
    for provider, model_list in models.items():
        console.print(f"\n[cyan]{provider}:[/cyan]")
        for m in model_list:
            console.print(f"  • {m}")
    console.print()


async def print_memory_stats(memory: BIEMContextPlugin | None):
    """Print memory system statistics."""
    if not memory:
        console.print("[yellow]Memory system not enabled[/yellow]")
        return
    
    stats = await memory.get_stats()
    summary = memory.format_stats_summary(stats)
    console.print(Panel(summary, title="Memory Stats"))


async def print_knowledge_stats(knowledge: KnowledgeLearningPlugin | None):
    """Print knowledge learning statistics."""
    if not knowledge or not knowledge.is_available():
        console.print("[yellow]Knowledge learning not enabled[/yellow]")
        return
    
    stats = await knowledge.get_stats()
    triples = await knowledge.get_all_knowledge(limit=10)
    
    lines = [
        f"Total triples: {stats.get('total_triples', 0)}",
        f"Unique subjects: {stats.get('unique_subjects', 0)}",
        f"Unique predicates: {stats.get('unique_predicates', 0)}",
        f"Total updates: {stats.get('total_updates', 0)}",
        f"Pending confirmations: {stats.get('pending_confirmations', 0)}",
    ]
    
    if triples:
        lines.append("\n[bold]Recent Knowledge:[/bold]")
        for t in triples[:10]:
            source_tag = f"[{t.source.value}]" if t.confidence < 1.0 else "[verified]"
            lines.append(f"  • {t.display()} {source_tag}")
    
    console.print(Panel("\n".join(lines), title="Knowledge Stats"))


async def run_interactive(
    agent: Agent,
    loop: AgentLoop,
    memory: BIEMContextPlugin | None,
    knowledge: KnowledgeLearningPlugin | None = None,
):
    """Run interactive session with memory and knowledge learning integration."""
    while True:
        try:
            user_input = Prompt.ask("[bold green]You[/bold green]")

            if not user_input.strip():
                continue

            cmd = user_input.lower().strip()

            if cmd == "quit" or cmd == "exit":
                console.print("[dim]Goodbye![/dim]")
                break

            if cmd == "stats":
                stats = agent.get_stats()
                console.print(Panel(str(stats), title="Agent Stats"))
                continue

            if cmd == "memory":
                await print_memory_stats(memory)
                continue

            if cmd == "knowledge":
                await print_knowledge_stats(knowledge)
                continue

            if cmd == "models":
                print_models()
                continue

            if cmd == "provider":
                info = loop.llm.get_provider_info()
                console.print(Panel(str(info), title="Provider Info"))
                continue

            if cmd == "clear":
                agent.context.clear()
                console.print("[dim]Context cleared.[/dim]")
                continue

            # Check if this is a response to pending knowledge confirmation
            if knowledge and knowledge.is_available():
                handled, response_msg = await knowledge.process_confirmation_response(user_input)
                if handled:
                    console.print(f"\n[bold blue]Assistant:[/bold blue] {response_msg}\n")
                    continue

            # Build combined context
            context_parts = []
            
            # Inject memory context
            if memory:
                memory_context = await memory.prepare_context(user_input)
                if memory_context:
                    context_parts.append(memory_context)
            
            # Inject learned knowledge context
            if knowledge and knowledge.is_available():
                knowledge_context = await knowledge.get_context_for_query(user_input)
                if knowledge_context:
                    context_parts.append(knowledge_context)
            
            if context_parts:
                agent.context.set_memory_context("\n\n".join(context_parts))

            # Run agent with streaming
            console.print("\n[bold blue]Assistant:[/bold blue]")

            response_chunks = []
            async for chunk in loop.run_stream(user_input):
                console.print(chunk, end="")
                response_chunks.append(chunk)

            console.print("\n")
            
            # Clear memory context after response
            if memory or knowledge:
                agent.context.clear_memory_context()
            
            full_response = "".join(response_chunks)
            
            # Record interaction to memory
            if memory:
                await memory.record_user_message(user_input)
                await memory.record_assistant_message(full_response)
            
            # Process message for knowledge extraction
            if knowledge and knowledge.is_available():
                result = await knowledge.process_message(user_input, role="user")
                
                if result.action == "stored":
                    n = len(result.triples_stored)
                    console.print(f"[dim]📚 Learned {n} new fact(s)[/dim]")
                elif result.action == "conflict":
                    # Show confirmation prompts
                    for prompt in result.confirmation_prompts:
                        console.print(f"\n[yellow]❓ {prompt}[/yellow]")

            # Show stats if in verbose mode
            if os.getenv("VERBOSE"):
                ctx_stats = agent.context.get_context_stats()
                console.print(
                    f"[dim]Tokens: ~{ctx_stats['estimated_tokens']} ({ctx_stats['usage_percent']}%)[/dim]\n"
                )

        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Type 'quit' to exit.[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            if os.getenv("DEBUG"):
                import traceback
                traceback.print_exc()


async def run_single(
    agent: Agent,
    loop: AgentLoop,
    memory: BIEMContextPlugin | None,
    knowledge: KnowledgeLearningPlugin | None,
    prompt: str,
):
    """Run a single prompt and exit."""
    # Build combined context
    context_parts = []
    
    if memory:
        memory_context = await memory.prepare_context(prompt)
        if memory_context:
            context_parts.append(memory_context)
    
    if knowledge and knowledge.is_available():
        knowledge_context = await knowledge.get_context_for_query(prompt)
        if knowledge_context:
            context_parts.append(knowledge_context)
    
    if context_parts:
        agent.context.set_memory_context("\n\n".join(context_parts))
    
    result = await loop.run(prompt)

    if result.state == LoopState.COMPLETED:
        console.print(Markdown(result.response))
        
        # Record to memory
        if memory:
            await memory.record_user_message(prompt)
            await memory.record_assistant_message(result.response)
        
        # Extract knowledge
        if knowledge and knowledge.is_available():
            await knowledge.process_message(prompt, role="user")
            
    elif result.state == LoopState.ERROR:
        console.print(f"[red]Error: {result.error}[/red]")
    elif result.state == LoopState.MAX_ITERATIONS:
        console.print(f"[yellow]Warning: Reached max iterations[/yellow]")
        console.print(Markdown(result.response))

    return result


async def init_memory() -> BIEMContextPlugin | None:
    """Initialize memory system."""
    if os.getenv("DISABLE_MEMORY", "").lower() == "true":
        return None
    
    try:
        config = create_memory_config()
        memory = BIEMContextPlugin(config)
        await memory.initialize()
        console.print("[dim]Memory system initialized[/dim]")
        return memory
    except Exception as e:
        console.print(f"[yellow]Warning: Memory init failed: {e}[/yellow]")
        console.print("[dim]Continuing without memory...[/dim]")
        return None


async def init_knowledge(llm: LLMProvider, encoder=None) -> KnowledgeLearningPlugin | None:
    """Initialize knowledge learning system."""
    if os.getenv("DISABLE_KNOWLEDGE", "").lower() == "true":
        return None
    
    try:
        session_id = str(uuid.uuid4())[:8]  # Short session ID
        config = create_knowledge_config(session_id)
        knowledge = KnowledgeLearningPlugin(config)
        await knowledge.initialize(llm, encoder)
        
        if knowledge.is_available():
            console.print("[dim]Knowledge learning initialized[/dim]")
            return knowledge
        else:
            return None
    except Exception as e:
        console.print(f"[yellow]Warning: Knowledge init failed: {e}[/yellow]")
        console.print("[dim]Continuing without knowledge learning...[/dim]")
        return None


async def main():
    """Main entry point."""
    workspace = Path.cwd()

    # Get model from env or default
    model = os.getenv("MODEL", "gpt-4o")

    # Initialize agent
    agent_config = AgentConfig(
        workspace_root=str(workspace),
        skills_dir="src/skills",
        model=model,
    )

    agent = Agent(agent_config)
    agent.discover_skills()

    # Initialize loop
    loop_config = LoopConfig(
        model=model,
        max_iterations=int(os.getenv("MAX_ITERATIONS", "50")),
        temperature=float(os.getenv("TEMPERATURE", "0.7")),
    )

    loop = AgentLoop(agent, loop_config)
    
    # Initialize memory system
    memory = await init_memory()
    
    # Initialize knowledge learning (uses the same LLM for extraction)
    # Get encoder from memory if available
    encoder = memory._memory._encoder if memory and hasattr(memory, '_memory') else None
    knowledge = await init_knowledge(loop.llm, encoder)

    try:
        # Check for single prompt mode
        prompt = os.getenv("PROMPT")
        if prompt:
            await run_single(agent, loop, memory, knowledge, prompt)
            return

        # Interactive mode
        print_welcome(agent, loop, memory, knowledge)
        await run_interactive(agent, loop, memory, knowledge)
        
    finally:
        # Cleanup
        if memory:
            await memory.shutdown()
            console.print("[dim]Memory system shutdown[/dim]")
        if knowledge:
            await knowledge.shutdown()
            console.print("[dim]Knowledge learning shutdown[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
