"""Install command handler for Cortex CLI.

Provides AI-powered package installation.
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Any, Optional

from rich.console import Console

from cortex.branding import cx_print
from cortex.coordinator import InstallationCoordinator, StepStatus
from cortex.i18n import t
from cortex.installation_history import InstallationHistory, InstallationStatus, InstallationType
from cortex.llm.interpreter import CommandInterpreter
from cortex.predictive_prevention import FailurePrediction, PredictiveErrorManager, RiskLevel
from cortex.utils.retry import DEFAULT_MAX_RETRIES
from cortex.validators import validate_install_request

console = Console()


class InstallHandler:
    """Handler for install command."""

    INSTALL_FAIL_MSG = "Installation failed"

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_idx = 0
        self.predict_manager: Optional[PredictiveErrorManager] = None

    def _debug(self, message: str) -> None:
        """Print debug message if verbose mode is enabled."""
        if self.verbose:
            console.print(f"[dim]↳ {message}[/dim]")

    def _print_status(self, emoji: str, message: str) -> None:
        """Print a status message."""
        console.print(f"{emoji} {message}")

    def _print_error(self, message: str) -> None:
        """Print an error message."""
        console.print(f"[red]✗[/red] {message}", file=sys.stderr)

    def _print_success(self, message: str) -> None:
        """Print a success message."""
        console.print(f"[green]✓[/green] {message}")

    def _animate_spinner(self, message: str) -> None:
        """Display spinner animation."""
        import time
        chars = self.spinner_chars
        for _ in range(len(chars)):
            sys.stdout.write(f"\r{chars[self.spinner_idx % len(chars)]} {message}")
            sys.stdout.flush()
            self.spinner_idx += 1
            time.sleep(0.05)
        sys.stdout.write("\r" + " " * (len(message) + 2) + "\r")
        sys.stdout.flush()

    def _clear_line(self) -> None:
        """Clear the current line."""
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()

    def _display_prediction_warning(self, prediction: FailurePrediction) -> None:
        """Display a warning about potential installation issues."""
        from rich.panel import Panel
        from rich.text import Text

        text = Text()
        text.append(f"Risk Level: {prediction.risk_level.name}\n", style="bold yellow")
        text.append("Potential Issues:\n")
        for reason in prediction.reasons:
            text.append(f"  • {reason}\n")
        if prediction.predicted_errors:
            text.append("\nPredicted Errors:\n")
            for error in prediction.predicted_errors:
                text.append(f"  ! {error}\n")
        if prediction.recommendations:
            text.append("\nRecommendations:\n")
            for rec in prediction.recommendations:
                text.append(f"  → {rec}\n")

        console.print(Panel(text, title="⚠️  Installation Risk Assessment", expand=False))

    def _confirm_risky_operation(self, prediction: FailurePrediction) -> bool:
        """Ask user to confirm a risky operation."""
        from rich.prompt import Confirm

        if prediction.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
            return Confirm.ask(
                f"{t('risk.high_risk_confirm')}\n\n{t('risk.continue_anyway')}?",
                default=False,
            )
        return True

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

    def _normalize_software_name(self, software: str) -> str:
        """Normalize software name for consistent matching."""
        return software.strip().lower().replace(" ", "-")

    def install(
        self,
        software: str,
        execute: bool = False,
        dry_run: bool = False,
        parallel: bool = False,
        json_output: bool = False,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> int:
        """Install software using the LLM-powered package manager."""
        history = InstallationHistory()
        install_id = None
        start_time = datetime.now()

        # Validate input
        is_valid, error = validate_install_request(software)
        if not is_valid:
            if json_output:
                print(json.dumps({"success": False, "error": error, "error_type": "ValueError"}))
            else:
                self._print_error(error)
            return 1

        software = self._normalize_software_name(software)

        api_key = self._get_api_key()
        if not api_key:
            error_msg = "No API key found. Please configure an API provider."
            try:
                packages = [software.split()[0]]
                install_id = history.record_installation(
                    InstallationType.INSTALL, packages, [], start_time
                )
            except Exception:
                pass
            if install_id:
                history.update_installation(install_id, InstallationStatus.FAILED, error_msg)
            if json_output:
                print(json.dumps({"success": False, "error": error_msg, "error_type": "RuntimeError"}))
            else:
                self._print_error(error_msg)
            return 1

        provider = self._get_provider()
        self._debug(f"Using provider: {provider}")
        self._debug(f"API key: {api_key[:10]}...{api_key[-4:]}")

        try:
            if not json_output:
                self._print_status("🧠", "Understanding request...")

            interpreter = CommandInterpreter(api_key=api_key, provider=provider)

            if not json_output:
                self._print_status("📦", "Planning installation...")
                for _ in range(10):
                    self._animate_spinner("Analyzing system requirements...")
                self._clear_line()

            commands = interpreter.parse(f"install {software}")

            if not commands:
                self._print_error(t("install.no_commands"))
                return 1

            # Predictive Analysis
            if not json_output:
                self._print_status("🔮", t("predictive.analyzing"))
            if not self.predict_manager:
                self.predict_manager = PredictiveErrorManager(api_key=api_key, provider=provider)
            prediction = self.predict_manager.analyze_installation(software, commands)
            if not json_output:
                self._clear_line()

            if not json_output:
                if prediction.risk_level != RiskLevel.NONE:
                    self._display_prediction_warning(prediction)
                    if execute and not self._confirm_risky_operation(prediction):
                        cx_print(f"\n{t('ui.operation_cancelled')}", "warning")
                        return 0
                else:
                    cx_print(t("predictive.no_issues_detected"), "success")

            packages = history._extract_packages_from_commands(commands)

            if execute or dry_run:
                install_id = history.record_installation(
                    InstallationType.INSTALL, packages, commands, start_time
                )

            if json_output:
                output = {
                    "success": True,
                    "commands": commands,
                    "packages": packages,
                    "install_id": install_id,
                    "prediction": {
                        "risk_level": prediction.risk_level.name,
                        "reasons": prediction.reasons,
                        "recommendations": prediction.recommendations,
                        "predicted_errors": prediction.predicted_errors,
                    },
                }
                print(json.dumps(output, indent=2))
                return 0

            self._print_status("⚙️", f"Installing {software}...")
            print("\nGenerated commands:")
            for i, cmd in enumerate(commands, 1):
                print(f"  {i}. {cmd}")

            if dry_run:
                print(f"\n({t('install.dry_run_message')})")
                if install_id:
                    history.update_installation(install_id, InstallationStatus.SUCCESS)
                return 0

            if execute:
                def progress_callback(current: int, total: int, step: Any) -> None:
                    status_emoji = "⏳"
                    if step.status == StepStatus.SUCCESS:
                        status_emoji = "✅"
                    elif step.status == StepStatus.FAILED:
                        status_emoji = "❌"
                    print(f"\n[{current}/{total}] {status_emoji} {step.description}")
                    print(f"  Command: {step.command}")

                print(f"\n{t('install.executing')}")

                if parallel:
                    return self._handle_parallel_execution(commands, software, install_id, history)

                coordinator = InstallationCoordinator(
                    commands=commands,
                    descriptions=[f"Step {i + 1}" for i in range(len(commands))],
                    timeout=300,
                    stop_on_error=True,
                    progress_callback=progress_callback,
                    max_retries=max_retries,
                )

                result = coordinator.execute()

                if result.success:
                    self._print_success(t("install.package_installed", package=software))
                    print(f"\n{t('progress.completed_in', seconds=f'{result.total_duration:.2f}')}")
                    if install_id:
                        history.update_installation(install_id, InstallationStatus.SUCCESS)
                        print(f"\n📝 Installation recorded (ID: {install_id})")
                        print(f"   To rollback: cortex rollback {install_id}")
                    return 0
                else:
                    if install_id:
                        error_msg = result.error_message or "Installation failed"
                        history.update_installation(install_id, InstallationStatus.FAILED, error_msg)
                    if result.failed_step is not None:
                        self._print_error(f"Installation failed at step {result.failed_step + 1}")
                    else:
                        self._print_error("Installation failed")
                    if result.error_message:
                        print(f"  Error: {result.error_message}", file=sys.stderr)
                    if install_id:
                        print(f"\n📝 Installation recorded (ID: {install_id})")
                        print(f"   View details: cortex history {install_id}")
                    return 1

            else:
                print("\nTo execute these commands, run with --execute flag")
                print("Example: cortex install docker --execute")
                return 0

        except ValueError as e:
            if install_id:
                history.update_installation(install_id, InstallationStatus.FAILED, str(e))
            if json_output:
                print(json.dumps({"success": False, "error": str(e), "error_type": "ValueError"}))
            else:
                self._print_error(str(e))
            return 1
        except RuntimeError as e:
            if install_id:
                history.update_installation(install_id, InstallationStatus.FAILED, str(e))
            if json_output:
                print(json.dumps({"success": False, "error": str(e), "error_type": "RuntimeError"}))
            else:
                self._print_error(f"API call failed: {str(e)}")
            return 1
        except OSError as e:
            if install_id:
                history.update_installation(install_id, InstallationStatus.FAILED, str(e))
            if json_output:
                print(json.dumps({"success": False, "error": str(e), "error_type": "OSError"}))
            else:
                self._print_error(f"System error: {str(e)}")
            return 1
        except Exception as e:
            if install_id:
                history.update_installation(install_id, InstallationStatus.FAILED, str(e))
            self._print_error(f"Unexpected error: {str(e)}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return 1

    def _handle_parallel_execution(
        self, commands: list[str], software: str, install_id: str, history: InstallationHistory
    ) -> int:
        """Handle parallel installation execution."""
        import asyncio
        from cortex.install_parallel import run_parallel_install

        def parallel_log_callback(message: str, level: str = "info"):
            if level == "success":
                cx_print(f"  ✅ {message}", "success")
            elif level == "error":
                cx_print(f"  ❌ {message}", "error")
            else:
                cx_print(f"  ℹ {message}", "info")

        try:
            success, parallel_tasks = asyncio.run(
                run_parallel_install(
                    commands=commands,
                    descriptions=[f"Step {i + 1}" for i in range(len(commands))],
                    timeout=300,
                    stop_on_error=True,
                    log_callback=parallel_log_callback,
                )
            )

            total_duration = 0.0
            if parallel_tasks:
                max_end = max(
                    (t.end_time for t in parallel_tasks if t.end_time is not None),
                    default=None,
                )
                min_start = min(
                    (t.start_time for t in parallel_tasks if t.start_time is not None),
                    default=None,
                )
                if max_end is not None and min_start is not None:
                    total_duration = max_end - min_start

            if success:
                self._print_success(t("install.package_installed", package=software))
                print(f"\n{t('progress.completed_in', seconds=f'{total_duration:.2f}')}")
                if install_id:
                    history.update_installation(install_id, InstallationStatus.SUCCESS)
                    print(f"\n📝 Installation recorded (ID: {install_id})")
                    print(f"   To rollback: cortex rollback {install_id}")
                return 0

            failed_tasks = [
                t for t in parallel_tasks if getattr(t.status, "value", "") == "failed"
            ]
            error_msg = failed_tasks[0].error if failed_tasks else "Installation failed"

            if install_id:
                history.update_installation(
                    install_id,
                    InstallationStatus.FAILED,
                    error_msg,
                )

            self._print_error(t("install.failed"))
            if error_msg:
                print(f"  {t('common.error')}: {error_msg}", file=sys.stderr)
            if install_id:
                print(f"\n📝 Installation recorded (ID: {install_id})")
                print(f"   View details: cortex history {install_id}")
            return 1

        except (ValueError, OSError) as e:
            if install_id:
                history.update_installation(install_id, InstallationStatus.FAILED, str(e))
            self._print_error(f"Parallel execution failed: {str(e)}")
            return 1
        except Exception as e:
            if install_id:
                history.update_installation(install_id, InstallationStatus.FAILED, str(e))
            self._print_error(f"Unexpected parallel execution error: {str(e)}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return 1


def add_install_parser(subparsers) -> argparse.ArgumentParser:
    """Add install parser to subparsers."""
    install_parser = subparsers.add_parser("install", help="Install software using AI")
    install_parser.add_argument("software", help="Software to install")
    install_parser.add_argument("--execute", action="store_true", help="Execute commands")
    install_parser.add_argument("--dry-run", action="store_true", help="Show commands without executing")
    install_parser.add_argument("--parallel", action="store_true", help="Run commands in parallel")
    install_parser.add_argument("--json", action="store_true", help="Output as JSON")
    install_parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="Max retries")
    return install_parser
