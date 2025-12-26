#!/usr/bin/env python3
"""Test script for reference loading when encountering errors."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from rich.console import Console
from rich.panel import Panel

from src.omniemployee.core import Agent, AgentConfig, AgentLoop, LoopConfig

console = Console()


def print_separator(title: str = ""):
    if title:
        console.print(f"\n[bold cyan]{'=' * 20} {title} {'=' * 20}[/bold cyan]\n")
    else:
        console.print(f"\n[dim]{'─' * 60}[/dim]\n")


async def test_reference_loading():
    """Test that Agent loads reference.md when encountering errors."""
    workspace = Path.cwd()
    model = os.getenv("MODEL", "qwen3-max")
    
    agent_config = AgentConfig(
        workspace_root=str(workspace),
        skills_dir="src/skills",
        model=model
    )
    
    agent = Agent(agent_config)
    agent.discover_skills()
    
    print_separator("Agent Initialized")
    console.print(f"[green]Model:[/green] {model}")
    console.print(f"[green]Available Skills:[/green] {agent.get_stats()['skills']['available']}")
    
    loop_config = LoopConfig(
        model=model,
        max_iterations=15,
        temperature=0.7,
    )
    
    loop = AgentLoop(agent, loop_config)
    
    # Test with a city that doesn't exist - should trigger reference loading
    print_separator("Test: Booking to Non-Existent City")
    
    test_prompt = "我想从北京订一张去旧金山的机票，明天出发，经济舱，1个人"
    
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
    
    # Show final stats
    print_separator("Final Stats")
    stats = agent.get_stats()
    console.print(f"[green]Loaded Skills:[/green] {stats['skills']['loaded']}")
    ctx_stats = agent.context.get_context_stats()
    console.print(f"[green]Context Tokens:[/green] ~{ctx_stats['estimated_tokens']} ({ctx_stats['usage_percent']}%)")
    console.print(f"[green]Loop State:[/green] {loop.state.value}")
    console.print(f"[green]Total Tool Calls:[/green] {loop._tool_calls_count}")


async def main():
    console.print(Panel.fit(
        "[bold blue]OmniEmployee[/bold blue] - Reference Loading Test\n"
        "Testing if Agent loads reference.md when encountering errors",
        title="Test"
    ))
    
    await test_reference_loading()
    
    console.print("\n[bold green]Test completed![/bold green]")


if __name__ == "__main__":
    asyncio.run(main())

