"""Remove command handler for Cortex CLI.

Provides safe package removal with impact analysis.
"""

import argparse
import sys
from typing import Optional

from rich.console import Console
from rich.table import Table

from cortex.branding import cx_print
from cortex.i18n import t
from cortex.installation_history import InstallationHistory, InstallationStatus, InstallationType
from cortex.uninstall_impact import ImpactResult, ImpactSeverity, ServiceStatus, UninstallImpactAnalyzer

console = Console()


class RemoveHandler:
    """Handler for remove command."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._console = console

    def _debug(self, message: str) -> None:
        """Print debug message if verbose mode is enabled."""
        if self.verbose:
            self._console.print(f"[dim]↳ {message}[/dim]")

    def _print_error(self, message: str) -> None:
        """Print an error message."""
        self._console.print(f"[red]✗[/red] {message}", file=sys.stderr)

    def remove(self, args: argparse.Namespace) -> int:
        """Handle package removal with impact analysis."""
        package = args.package
        dry_run = getattr(args, "dry_run", True)
        purge = getattr(args, "purge", False)
        force = getattr(args, "force", False)
        json_output = getattr(args, "json", False)

        result = self._analyze_package_removal(package)
        if result is None:
            return 1

        if self._check_package_not_found(result):
            return 1

        self._output_impact_result(result, json_output)

        if dry_run:
            console.print()
            cx_print("Dry run mode - no changes made", "info")
            cx_print(f"To proceed with removal: cortex remove {package} --execute", "info")
            return 0

        if not self._can_proceed_with_removal(result, force, args, package, purge):
            return self._removal_blocked_or_cancelled(result, force)

        return self._execute_removal(package, purge)

    def _analyze_package_removal(self, package: str) -> Optional[ImpactResult]:
        """Initialize analyzer and perform impact analysis."""
        try:
            analyzer = UninstallImpactAnalyzer()
            return analyzer.analyze(package)
        except FileNotFoundError:
            self._print_error("Package manager tools not found")
            return None
        except ValueError as e:
            self._print_error(str(e))
            return None
        except Exception as e:
            self._print_error(f"Analysis failed: {str(e)}")
            return None

    def _check_package_not_found(self, result: ImpactResult) -> bool:
        """Check if package doesn't exist at all."""
        if result.severity == ImpactSeverity.NOT_FOUND:
            self._print_error(f"Package '{result.package}' is not installed")
            self._display_services(result)
            return True
        return False

    def _output_impact_result(self, result: ImpactResult, json_output: bool = False) -> None:
        """Output impact analysis results."""
        self._display_impact_report(result)
        self._display_warnings(result)
        self._display_services(result)

        if json_output:
            import json
            output = {
                "package": result.package,
                "severity": result.severity.name,
                "removable": result.is_removable,
                "warnings": [w.message for w in result.warnings],
                "affected_services": [s.name for s in result.affected_services],
                "affected_packages": list(result.affected_packages),
            }
            print(json.dumps(output, indent=2))

    def _display_impact_report(self, result: ImpactResult) -> None:
        """Display impact analysis report."""
        from rich.panel import Panel
        from rich.text import Text

        text = Text()

        severity_style = {
            ImpactSeverity.SAFE: "green",
            ImpactSeverity.LOW: "yellow",
            ImpactSeverity.MEDIUM: "orange1",
            ImpactSeverity.HIGH: "red1",
            ImpactSeverity.CRITICAL: "red",
        }.get(result.severity, "white")

        text.append(f"Package: {result.package}\n", style="bold")
        text.append(f"Impact Level: ", style="dim")
        text.append(f"{result.severity.value}\n", style=severity_style)

        if result.is_removable:
            text.append("Status: ✅ Can be safely removed\n", style="green")
        else:
            text.append("Status: ⚠️  Removal not recommended\n", style="yellow")

        console.print(Panel(text, title="📊 Impact Analysis", expand=False))

    def _display_warnings(self, result: ImpactResult) -> None:
        """Display warnings if any."""
        if result.warnings:
            console.print("\n⚠️  Warnings:")
            for warning in result.warnings:
                console.print(f"  • {warning.message}")

    def _display_services(self, result: ImpactResult) -> None:
        """Display affected services."""
        if result.affected_services:
            console.print("\n🔧 Affected Services:")
            for service in result.affected_services:
                status_icon = "🟢" if service.status == ServiceStatus.RUNNING else "⚪"
                console.print(f"  {status_icon} {service.name} ({service.status.value})")

    def _can_proceed_with_removal(
        self, result: ImpactResult, force: bool, args: argparse.Namespace, package: str, purge: bool
    ) -> bool:
        """Check if removal can proceed with user confirmation."""
        if result.is_removable:
            if result.severity in (ImpactSeverity.MEDIUM, ImpactSeverity.HIGH, ImpactSeverity.CRITICAL):
                if not force:
                    from rich.prompt import Confirm
                    return Confirm.ask(f"\n{t('remove.confirm_removal')}", default=False)
            return True
        return False

    def _removal_blocked_or_cancelled(self, result: ImpactResult, force: bool) -> int:
        """Handle blocked or cancelled removal."""
        if not result.is_removable:
            if not force:
                console.print(f"\n{t('remove.blocked')}")
                return 0
            else:
                console.print(f"\n⚠️  {t('remove.force_warning')}")
        return 0

    def _execute_removal(self, package: str, purge: bool) -> int:
        """Execute package removal."""
        from cortex.coordinator import InstallationCoordinator

        history = InstallationHistory()
        commands = [f"apt-get remove -y{' --purge' if purge else ''} {package}"]

        console.print(f"\n{t('remove.executing')}...")

        coordinator = InstallationCoordinator(
            commands=commands,
            descriptions=[f"Remove {package}"],
            timeout=300,
            stop_on_error=True,
        )

        result = coordinator.execute()

        if result.success:
            self._print_success(t("remove.completed", package=package))
            install_id = history.record_installation(
                InstallationType.REMOVE, [package], commands, result.end_time
            )
            history.update_installation(install_id, InstallationStatus.SUCCESS)
            console.print(f"\n📝 Removal recorded (ID: {install_id})")
            return 0
        else:
            self._print_error(t("remove.failed"))
            if result.error_message:
                print(f"  Error: {result.error_message}")
            return 1


def add_remove_parser(subparsers) -> argparse.ArgumentParser:
    """Add remove parser to subparsers."""
    remove_parser = subparsers.add_parser("remove", help="Remove installed software")
    remove_parser.add_argument("package", help="Package to remove")
    remove_parser.add_argument("--dry-run", action="store_true", help="Show impact without removing")
    remove_parser.add_argument("--purge", action="store_true", help="Remove configuration files")
    remove_parser.add_argument("--force", action="store_true", help="Force removal despite warnings")
    remove_parser.add_argument("--json", action="store_true", help="Output as JSON")
    return remove_parser
