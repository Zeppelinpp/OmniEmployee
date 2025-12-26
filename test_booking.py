#!/usr/bin/env python3
"""Test script for book-flight skill with progressive disclosure."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from src.omniemployee.core import Agent, AgentConfig, AgentLoop, LoopConfig, LoopState

console = Console()


def print_separator(title: str = ""):
    """Print a visual separator."""
    if title:
        console.print(f"\n[bold cyan]{'=' * 20} {title} {'=' * 20}[/bold cyan]\n")
    else:
        console.print(f"\n[dim]{'─' * 60}[/dim]\n")


async def test_booking_flow():
    """Test the flight booking flow with progressive disclosure."""
    workspace = Path.cwd()
    model = os.getenv("MODEL", "qwen3-max")
    
    # Initialize agent
    agent_config = AgentConfig(
        workspace_root=str(workspace),
        skills_dir="src/skills",
        model=model
    )
    
    agent = Agent(agent_config)
    
    # Discover available skills
    agent.discover_skills()
    
    # Print initial state
    print_separator("Agent Initialized")
    stats = agent.get_stats()
    console.print(f"[green]Workspace:[/green] {agent.workspace_root}")
    console.print(f"[green]Model:[/green] {model}")
    console.print(f"[green]Available Skills:[/green] {stats['skills']['available']}")
    console.print(f"[green]Loaded Skills:[/green] {stats['skills']['loaded']}")
    console.print(f"[green]Available Tools:[/green] {stats['tools']}")
    
    # Initialize loop
    loop_config = LoopConfig(
        model=model,
        max_iterations=20,
        temperature=0.7,
    )
    
    loop = AgentLoop(agent, loop_config)
    
    # Test with incomplete booking request
    print_separator("Test: Incomplete Booking Request")
    
    test_prompt = "我想订一张去东京的机票"
    
    console.print(f"[bold green]User:[/bold green] {test_prompt}\n")
    console.print("[bold blue]Assistant:[/bold blue]")
    
    try:
        async for chunk in loop.run_stream(test_prompt):
            console.print(chunk, end="")
        console.print("\n")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return
    
    # Show stats after first interaction
    print_separator("Stats After First Interaction")
    stats = agent.get_stats()
    console.print(f"[green]Loaded Skills:[/green] {stats['skills']['loaded']}")
    ctx_stats = agent.context.get_context_stats()
    console.print(f"[green]Context Tokens:[/green] ~{ctx_stats['estimated_tokens']} ({ctx_stats['usage_percent']}%)")
    
    # Simulate user providing more information
    print_separator("Test: User Provides More Info")
    
    followup = "从北京出发，明天的航班，经济舱，1个人"
    
    console.print(f"[bold green]User:[/bold green] {followup}\n")
    console.print("[bold blue]Assistant:[/bold blue]")
    
    try:
        async for chunk in loop.run_stream(followup):
            console.print(chunk, end="")
        console.print("\n")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return
    
    # Show final stats
    print_separator("Final Stats")
    stats = agent.get_stats()
    console.print(f"[green]Loaded Skills:[/green] {stats['skills']['loaded']}")
    ctx_stats = agent.context.get_context_stats()
    console.print(f"[green]Context Tokens:[/green] ~{ctx_stats['estimated_tokens']} ({ctx_stats['usage_percent']}%)")
    console.print(f"[green]Loop State:[/green] {loop.state.value}")
    console.print(f"[green]Total Iterations:[/green] {loop._iteration}")
    console.print(f"[green]Total Tool Calls:[/green] {loop._tool_calls_count}")


async def main():
    """Main entry point."""
    console.print(Panel.fit(
        "[bold blue]OmniEmployee[/bold blue] - Book Flight Skill Test\n"
        "Testing progressive disclosure and multi-turn interaction",
        title="Test"
    ))
    
    await test_booking_flow()
    
    console.print("\n[bold green]Test completed![/bold green]")


if __name__ == "__main__":
    asyncio.run(main())

