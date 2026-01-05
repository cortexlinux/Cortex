"""
Docker Permission Management Module.

This module provides tools to diagnose and repair file ownership issues
that occur when Docker containers create files in host-mounted directories.
"""

import os
import platform
import subprocess

from cortex.branding import console

# Standard project directories to ignore during scans
EXCLUDED_DIRS = {
    "venv",
    ".venv",
    ".git",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
}


class PermissionManager:
    """Manages and fixes Docker-related file permission issues for bind mounts."""

    def __init__(self, base_path: str):
        """Initialize the manager with the project base path.

        Args:
            base_path: The root directory of the project to scan.
        """
        self.base_path = base_path
        # Cache current system IDs to avoid multiple system calls
        self.host_uid = os.getuid() if platform.system() != "Windows" else 1000
        self.host_gid = os.getgid() if platform.system() != "Windows" else 1000

    def diagnose(self) -> list[str]:
        """Scans for files not owned by the current host user.

        Returns:
            list[str]: A list of full file paths with ownership mismatches.
        """
        mismatched_files = []
        for root, dirs, files in os.walk(self.base_path):
            # Efficiently skip excluded directories by modifying dirs in-place
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

            for name in files:
                full_path = os.path.join(root, name)
                try:
                    # Catch any file not owned by the current user
                    # This handles both root (0) and other container-specific UIDs
                    if os.stat(full_path).st_uid != self.host_uid:
                        mismatched_files.append(full_path)
                except (PermissionError, FileNotFoundError):
                    continue
        return mismatched_files

    def generate_compose_settings(self) -> str:
        """Generates the recommended user mapping for docker-compose.yml.

        Returns:
            str: A formatted YAML snippet for the user directive.
        """
        # Provides the exact configuration needed to prevent future issues
        return (
            f'    user: "{self.host_uid}:{self.host_gid}"\n'
            "    # Or for better portability across different machines:\n"
            '    # user: "${UID}:${GID}"'
        )

    def check_compose_config(self) -> None:
        """Checks if docker-compose.yml contains correct user mapping."""
        compose_path = os.path.join(self.base_path, "docker-compose.yml")
        if os.path.exists(compose_path):
            try:
                with open(compose_path, encoding="utf-8") as f:
                    content = f.read()

                if "user:" not in content:
                    console.print(
                        "\n[bold yellow]💡 Recommended Docker-Compose settings:[/bold yellow]"
                    )
                    console.print(self.generate_compose_settings())
            except Exception:
                # Silently fail if file is unreadable to avoid blocking the main flow
                pass

    def fix_permissions(self, file_paths: list[str]) -> bool:
        """Attempts to change ownership of files back to the current host user.

        Args:
            file_paths: List of full paths to files requiring ownership changes.

        Returns:
            bool: True if the command executed successfully, False otherwise.
        """
        if not file_paths or platform.system() == "Windows":
            return False

        try:
            # Execute ownership change using sudo to reclaim files
            subprocess.run(
                ["sudo", "chown", f"{self.host_uid}:{self.host_gid}"] + file_paths,
                check=True,
                capture_output=True,
                timeout=60,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, PermissionError):
            return False
