"""Import command handler for Cortex CLI.

Provides dependency file import functionality.
"""

import argparse
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from cortex.branding import cx_print
from cortex.dependency_importer import DependencyImporter, PackageEcosystem, ParseResult
from cortex.validators import validate_install_request

console = Console()


class ImportDepHandler:
    """Handler for import_deps command."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.importer = DependencyImporter()

    def _debug(self, message: str) -> None:
        """Print debug message if verbose mode is enabled."""
        if self.verbose:
            console.print(f"[dim]↳ {message}[/dim]")

    def _print_error(self, message: str) -> None:
        """Print an error message."""
        console.print(f"[red]✗[/red] {message}", file=__import__('sys').stderr)

    def import_deps(self, args: argparse.Namespace) -> int:
        """Handle dependency import."""
        files = getattr(args, "file", None)
        all_files = getattr(args, "all", False)
        dry_run = getattr(args, "dry_run", True)
        execute = getattr(args, "execute", False)

        if all_files:
            return self._import_all(dry_run, execute)
        elif files:
            return self._import_single_file(files, dry_run, execute)
        else:
            self._print_error("No files specified")
            return 1

    def _import_single_file(self, file_path: str, dry_run: bool, execute: bool) -> int:
        """Import dependencies from a single file."""
        result = self.importer.parse_file(file_path)

        if not result.success:
            self._print_error(f"Failed to parse {file_path}: {result.error}")
            return 1

        self._display_parse_result(result)

        if dry_run:
            console.print("\nDry run mode - no changes made", style="blue")
            return 0

        if execute:
            return self._execute_install(result.packages, result.ecosystem)

        return 0

    def _import_all(self, dry_run: bool, execute: bool) -> int:
        """Import dependencies from all supported files."""
        results = self.importer.discover_and_parse()

        if not results:
            console.print("No dependency files found", style="yellow")
            return 0

        all_packages = set()
        ecosystems_found = set()

        for result in results:
            self._display_parse_result(result)
            all_packages.update(result.packages)
            ecosystems_found.add(result.ecosystem)

        console.print(f"\nTotal packages to install: {len(all_packages)}")
        console.print(f"Ecosystems: {', '.join(e.value for e in ecosystems_found)}")

        if dry_run:
            console.print("\nDry run mode - no changes made", style="blue")
            return 0

        if execute:
            return self._execute_multi_install(list(all_packages))

        return 0

    def _display_parse_result(self, result: ParseResult) -> None:
        """Display parse result."""
        text = Text()
        text.append(f"File: {result.file_path}\n")
        text.append(f"Ecosystem: {result.ecosystem.value}\n")
        text.append(f"Packages found: {len(result.packages)}\n")

        if result.packages:
            text.append("\nPackages:")
            for pkg in result.packages[:10]:
                text.append(f"  • {pkg}\n")
            if len(result.packages) > 10:
                text.append(f"  ... and {len(result.packages) - 10} more")

        console.print(Panel(text, title="📄 Dependency File", expand=False))

    def _execute_install(self, packages: list[str], ecosystem: PackageEcosystem) -> int:
        """Execute package installation."""
        from cortex.coordinator import InstallationCoordinator

        if not packages:
            return 0

        console.print(f"\nInstalling {len(packages)} packages...")

        is_valid, error = validate_install_request(" ".join(packages))
        if not is_valid:
            self._print_error(error)
            return 1

        commands = self.importer.generate_install_commands(packages, ecosystem)

        if not commands:
            self._print_error("Failed to generate install commands")
            return 1

        coordinator = InstallationCoordinator(
            commands=commands,
            descriptions=[f"Install {pkg}" for pkg in packages[:5]],
            timeout=300,
            stop_on_error=True,
        )

        result = coordinator.execute()

        if result.success:
            console.print("Installation completed", style="green")
            return 0
        else:
            self._print_error(f"Installation failed: {result.error_message}")
            return 1

    def _execute_multi_install(self, packages: list[str]) -> int:
        """Execute multi-ecosystem installation."""
        from cortex.coordinator import InstallationCoordinator

        console.print(f"\nInstalling {len(packages)} packages across ecosystems...")

        commands = []
        descriptions = []

        ecosystems = {
            PackageEcosystem.PYTHON: "pip install",
            PackageEcosystem.NODE: "npm install",
            PackageEcosystem.GO: "go install",
            PackageEcosystem.RUST: "cargo install",
        }

        for ecosystem in PackageEcosystem:
            pkgs = [p for p in packages if self._package_ecosystem(p) == ecosystem]
            if pkgs:
                cmds = self.importer.generate_install_commands(pkgs, ecosystem)
                commands.extend(cmds)
                descriptions.extend([f"Install {p}" for p in pkgs[:3]])

        if not commands:
            self._print_error("No install commands generated")
            return 1

        coordinator = InstallationCoordinator(
            commands=commands,
            descriptions=descriptions,
            timeout=300,
            stop_on_error=True,
        )

        result = coordinator.execute()

        if result.success:
            console.print("All installations completed", style="green")
            return 0
        else:
            self._print_error(f"Installation failed: {result.error_message}")
            return 1

    def _package_ecosystem(self, package: str) -> PackageEcosystem:
        """Determine ecosystem for a package."""
        if "@" in package or package.startswith("npm:"):
            return PackageEcosystem.NODE
        elif package.startswith("go:") or "/" in package:
            return PackageEcosystem.GO
        elif ".toml" in package or "cargo" in package:
            return PackageEcosystem.RUST
        return PackageEcosystem.PYTHON


def add_import_deps_parser(subparsers) -> argparse.ArgumentParser:
    """Add import_deps parser to subparsers."""
    import_parser = subparsers.add_parser(
        "import", help="Import dependencies from project files"
    )
    import_parser.add_argument("file", nargs="?", help="Dependency file to import")
    import_parser.add_argument(
        "--all", action="store_true", help="Import from all supported files in directory"
    )
    import_parser.add_argument(
        "--dry-run", action="store_true", default=True, help="Show what would be installed"
    )
    import_parser.add_argument(
        "--execute", action="store_true", help="Actually install the packages"
    )

    return import_parser
