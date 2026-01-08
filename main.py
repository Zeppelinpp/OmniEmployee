"""OmniEmployee - Main entry point with BIEM memory integration."""

import asyncio
import os
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

console = Console()


def create_memory_config() -> MemoryConfig:
    """Create memory configuration from environment."""
    milvus_config = MilvusConfig(
        collection_name=os.getenv("MILVUS_COLLECTION", "biem_memories"),
        use_lite=os.getenv("MILVUS_USE_LITE", "true").lower() == "true",
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


def print_welcome(agent: Agent, loop: AgentLoop, memory: BIEMContextPlugin | None):
    """Print welcome message."""
    provider_info = loop.llm.get_provider_info()

    memory_status = "[green]Enabled[/green]" if memory else "[yellow]Disabled[/yellow]"
    
    console.print(
        Panel.fit(
            "[bold blue]OmniEmployee[/bold blue] - AI Coding Assistant\n"
            f"Workspace: {agent.workspace_root}\n"
            f"Provider: {provider_info['provider']}\n"
            f"Model: {provider_info['model']}\n"
            f"Memory: {memory_status}",
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
        "\n[dim]Commands: 'quit' to exit, 'stats' for info, 'memory' for memory stats, 'clear' to reset[/dim]\n"
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


async def run_interactive(agent: Agent, loop: AgentLoop, memory: BIEMContextPlugin | None):
    """Run interactive session with memory integration."""
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

            # Inject memory context before LLM call
            if memory:
                memory_context = await memory.prepare_context(user_input)
                if memory_context:
                    # Add memory context to system prompt temporarily
                    original_prompt = agent.context._system_prompt
                    agent.context.set_system_prompt(
                        original_prompt + "\n\n" + memory_context
                    )

            # Run agent with streaming
            console.print("\n[bold blue]Assistant:[/bold blue]")

            response_chunks = []
            async for chunk in loop.run_stream(user_input):
                console.print(chunk, end="")
                response_chunks.append(chunk)

            console.print("\n")
            
            # Restore original system prompt
            if memory:
                agent.context.set_system_prompt(original_prompt)
            
            # Record interaction to memory
            if memory:
                full_response = "".join(response_chunks)
                await memory.record_user_message(user_input)
                await memory.record_assistant_message(full_response)

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


async def run_single(agent: Agent, loop: AgentLoop, memory: BIEMContextPlugin | None, prompt: str):
    """Run a single prompt and exit."""
    # Inject memory context
    if memory:
        memory_context = await memory.prepare_context(prompt)
        if memory_context:
            original_prompt = agent.context._system_prompt
            agent.context.set_system_prompt(original_prompt + "\n\n" + memory_context)
    
    result = await loop.run(prompt)

    if result.state == LoopState.COMPLETED:
        console.print(Markdown(result.response))
        
        # Record to memory
        if memory:
            await memory.record_user_message(prompt)
            await memory.record_assistant_message(result.response)
            
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

    try:
        # Check for single prompt mode
        prompt = os.getenv("PROMPT")
        if prompt:
            await run_single(agent, loop, memory, prompt)
            return

        # Interactive mode
        print_welcome(agent, loop, memory)
        await run_interactive(agent, loop, memory)
        
    finally:
        # Cleanup
        if memory:
            await memory.shutdown()
            console.print("[dim]Memory system shutdown[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
