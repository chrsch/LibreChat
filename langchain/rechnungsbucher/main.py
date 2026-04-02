#!/usr/bin/env python3
"""
Rechnungsbücher — Standalone LangChain Agent

Interactive CLI that processes supplier invoices from Nextcloud and books
them into the Collmex accounting system.

Usage:
    python main.py                          # interactive chat loop
    python main.py "Rechnungen buchen"      # single-shot command
"""

from __future__ import annotations

import sys

from rich.console import Console
from rich.markdown import Markdown

from config import (
    load_collmex_config,
    load_nextcloud_config,
    load_llm_config,
    load_agent_config,
)
from tools.collmex_tools import init_collmex_tools
from tools.nextcloud_tools import init_nextcloud_tools
from agent import create_agent

console = Console()


def print_agent_response(events) -> None:
    """Stream agent events and print the final AI message."""
    for event in events:
        # LangGraph events: each is a dict with "messages"
        messages = event.get("messages", [])
        for msg in messages:
            if msg.type == "ai" and msg.content:
                console.print(Markdown(msg.content))
            elif msg.type == "tool":
                # Optionally show tool calls for debugging
                pass


def run_interactive(agent) -> None:
    """Interactive chat loop."""
    console.print(
        "[bold green]Rechnungsbücher Agent[/bold green] — type your request or 'quit' to exit.\n"
    )
    state = {"messages": []}

    while True:
        try:
            user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nBye!")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            console.print("Bye!")
            break

        if not user_input:
            continue

        state["messages"].append({"role": "user", "content": user_input})

        console.print("[bold yellow]Agent:[/bold yellow]")
        try:
            result = agent.invoke(state)
            state = result  # carry forward the full state for multi-turn
            # Print the last AI message
            for msg in reversed(result.get("messages", [])):
                if msg.type == "ai" and msg.content:
                    console.print(Markdown(msg.content))
                    break
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")


def run_single(agent, prompt: str) -> None:
    """Run a single prompt and exit."""
    state = {"messages": [{"role": "user", "content": prompt}]}
    console.print(f"[bold cyan]You:[/bold cyan] {prompt}")
    console.print("[bold yellow]Agent:[/bold yellow]")

    try:
        result = agent.invoke(state)
        for msg in reversed(result.get("messages", [])):
            if msg.type == "ai" and msg.content:
                console.print(Markdown(msg.content))
                break
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)


def main() -> None:
    console.print("[dim]Loading configuration...[/dim]")

    collmex_cfg = load_collmex_config()
    nextcloud_cfg = load_nextcloud_config()
    llm_cfg = load_llm_config()
    agent_cfg = load_agent_config()

    # Initialise tool backends
    init_collmex_tools(collmex_cfg)
    init_nextcloud_tools(nextcloud_cfg)

    console.print("[dim]Creating agent...[/dim]")
    agent = create_agent(llm_cfg, agent_cfg)
    console.print("[dim]Ready.[/dim]\n")

    # Single-shot or interactive
    if len(sys.argv) > 1:
        run_single(agent, " ".join(sys.argv[1:]))
    else:
        run_interactive(agent)


if __name__ == "__main__":
    main()
