"""OmniEmployee - Main entry point."""

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


console = Console()


def print_welcome(agent: Agent, loop: AgentLoop):
    """Print welcome message."""
    provider_info = loop.llm.get_provider_info()
    
    console.print(Panel.fit(
        "[bold blue]OmniEmployee[/bold blue] - AI Coding Assistant\n"
        f"Workspace: {agent.workspace_root}\n"
        f"Provider: {provider_info['provider']}\n"
        f"Model: {provider_info['model']}\n"
        f"API Base: {provider_info['api_base']}",
        title="Welcome"
    ))
    
    # Print available skills
    stats = agent.get_stats()
    if stats["skills"]["available"]:
        console.print(f"\n[dim]Available skills: {', '.join(stats['skills']['available'])}[/dim]")
    
    # Print available tools
    console.print(f"[dim]Available tools: {', '.join(stats['tools'])}[/dim]")
    
    console.print("\n[dim]Commands: 'quit' to exit, 'stats' for info, 'models' to list models, 'provider' for provider info[/dim]\n")


def print_models():
    """Print available models."""
    models = LLMProvider.list_models()
    console.print("\n[bold]Available Models:[/bold]")
    for provider, model_list in models.items():
        console.print(f"\n[cyan]{provider}:[/cyan]")
        for m in model_list:
            console.print(f"  • {m}")
    console.print()


def print_env_template():
    """Print .env template."""
    template = LLMProvider.get_env_template()
    console.print("\n[bold].env Template:[/bold]")
    console.print(template)


async def run_interactive(agent: Agent, loop: AgentLoop):
    """Run interactive session."""
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
            
            if cmd == "models":
                print_models()
                continue
            
            if cmd == "provider":
                info = loop.llm.get_provider_info()
                console.print(Panel(str(info), title="Provider Info"))
                continue
            
            if cmd == "env":
                print_env_template()
                continue
            
            if cmd == "clear":
                agent.context.clear()
                console.print("[dim]Context cleared.[/dim]")
                continue
            
            # Run agent with streaming
            console.print("\n[bold blue]Assistant:[/bold blue]")
            
            async for chunk in loop.run_stream(user_input):
                console.print(chunk, end="")
            
            console.print("\n")
            
            # Show stats if in verbose mode
            if os.getenv("VERBOSE"):
                ctx_stats = agent.context.get_context_stats()
                console.print(f"[dim]Tokens: ~{ctx_stats['estimated_tokens']} ({ctx_stats['usage_percent']}%)[/dim]\n")
            
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Type 'quit' to exit.[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            if os.getenv("DEBUG"):
                import traceback
                traceback.print_exc()


async def run_single(agent: Agent, loop: AgentLoop, prompt: str):
    """Run a single prompt and exit."""
    result = await loop.run(prompt)
    
    if result.state == LoopState.COMPLETED:
        console.print(Markdown(result.response))
    elif result.state == LoopState.ERROR:
        console.print(f"[red]Error: {result.error}[/red]")
    elif result.state == LoopState.MAX_ITERATIONS:
        console.print(f"[yellow]Warning: Reached max iterations[/yellow]")
        console.print(Markdown(result.response))
    
    return result


async def main():
    """Main entry point."""
    workspace = Path.cwd()
    
    # Get model from env or default to qwen-plus for DashScope
    model = os.getenv("MODEL", "gpt-4o")
    
    # Initialize agent
    agent_config = AgentConfig(
        workspace_root=str(workspace),
        skills_dir="src/skills",  # Skills are in src/skills/ directory
        model=model
    )
    
    agent = Agent(agent_config)
    
    # Discover available skills
    agent.discover_skills()
    
    # Initialize loop - LLMProvider will auto-detect provider and load config from env
    loop_config = LoopConfig(
        model=model,
        max_iterations=int(os.getenv("MAX_ITERATIONS", "50")),
        temperature=float(os.getenv("TEMPERATURE", "0.7")),
    )
    
    loop = AgentLoop(agent, loop_config)
    
    # Check for single prompt mode
    prompt = os.getenv("PROMPT")
    if prompt:
        await run_single(agent, loop, prompt)
        return
    
    # Interactive mode
    print_welcome(agent, loop)
    await run_interactive(agent, loop)


if __name__ == "__main__":
    asyncio.run(main())
