"""Ask command handler for Cortex CLI.

Provides natural language question answering about the system.
"""

import argparse
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown

from cortex.ask import AskHandler
from cortex.branding import cx_print

console = Console()


class AskHandlerWrapper:
    """Wrapper for ask command functionality."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._console = console

    def _debug(self, message: str) -> None:
        """Print debug message if verbose mode is enabled."""
        if self.verbose:
            self._console.print(f"[dim]↳ {message}[/dim]")

    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment."""
        import os
        return os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")

    def _get_provider(self) -> str:
        """Determine which LLM provider to use."""
        import os
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        elif os.environ.get("OPENAI_API_KEY"):
            return "openai"
        elif os.environ.get("OLLAMA_HOST"):
            return "ollama"
        elif os.environ.get("KIMI_API_KEY"):
            return "kimi"
        return "auto"

    def _print_error(self, message: str) -> None:
        """Print an error message."""
        self._console.print(f"[red]✗[/red] {message}", file=__import__('sys').stderr)

    def ask(self, question: str, do_mode: bool = False) -> int:
        """Answer a natural language question about the system.

        Args:
            question: The natural language question to answer
            do_mode: If True, enable execution mode where AI can run commands
        """
        api_key = self._get_api_key()
        if not api_key:
            self._print_error("No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.")
            return 1

        provider = self._get_provider()
        self._debug(f"Using provider: {provider}")

        try:
            handler = AskHandler(
                api_key=api_key,
                provider=provider,
                do_mode=do_mode,
            )

            if do_mode:
                return self._run_interactive_do_session(handler, question)
            else:
                answer = handler.ask(question)
                console.print(Markdown(answer))
                return 0
        except ImportError as e:
            self._print_error(str(e))
            cx_print(
                "Install the required SDK or set CORTEX_PROVIDER=ollama for local mode.", "info"
            )
            return 1
        except ValueError as e:
            self._print_error(str(e))
            return 1
        except RuntimeError as e:
            self._print_error(str(e))
            return 1

    def _run_interactive_do_session(self, handler: AskHandler, initial_question: Optional[str] = None) -> int:
        """Run an interactive session with execution capabilities."""
        from rich.prompt import Prompt

        from cortex.ask import _print_cortex_banner, _restore_terminal_theme, _set_terminal_theme

        try:
            _set_terminal_theme()
            _print_cortex_banner()
        except Exception:
            pass

        question = initial_question
        PURPLE_LIGHT = "#ff79c6"
        GRAY = "#6272a4"
        INDENT = "   "

        try:
            while True:
                try:
                    if not question:
                        question = Prompt.ask(
                            f"{INDENT}[bold {PURPLE_LIGHT}]What would you like to do?[/bold {PURPLE_LIGHT}]"
                        )

                    if not question or question.lower() in ["exit", "quit", "q"]:
                        console.print(f"{INDENT}[{GRAY}]Goodbye![/{GRAY}]")
                        return 0

                    if question.strip().lower() == "/theme":
                        from cortex.ask import get_current_theme, set_theme, show_theme_selector

                        selected = show_theme_selector()
                        if selected:
                            set_theme(selected)
                            theme = get_current_theme()
                            console.print(
                                f"{INDENT}[{theme['success']}]● Theme changed to {theme['name']}[/{theme['success']}]"
                            )
                        else:
                            console.print(f"{INDENT}[{GRAY}]Theme selection cancelled[/{GRAY}]")

                        _print_cortex_banner()
                        question = None
                        continue

                    result = handler.ask(question)
                    if result:
                        console.print(Markdown(result))

                    question = None

                except KeyboardInterrupt:
                    console.print(f"\n{INDENT}[{GRAY}]Session ended.[/{GRAY}]")
                    return 0
                except Exception as e:
                    self._print_error(f"Error: {e}")
                    question = None
        finally:
            try:
                _restore_terminal_theme()
            except Exception:
                pass


def add_ask_parser(subparsers) -> argparse.ArgumentParser:
    """Add ask parser to subparsers."""
    ask_parser = subparsers.add_parser("ask", help="Ask questions about your system")
    ask_parser.add_argument("question", nargs="...", help="Question to ask")
    ask_parser.add_argument("--do", action="store_true", help="Enable execution mode")
    return ask_parser
