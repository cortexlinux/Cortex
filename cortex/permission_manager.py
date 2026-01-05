import os
import platform
import subprocess

from cortex.branding import console


class PermissionManager:
    """Manages and fixes Docker-related file permission issues for bind mounts."""

    def __init__(self, base_path: str):
        """Initialize the manager with the project base path.

        Args:
            base_path: The root directory of the project to scan.
        """
        self.base_path = base_path

    def diagnose(self) -> list[str]:
        """Scans the directory for files owned by root (UID 0).

        Returns:
            list[str]: A list of full file paths that have permission mismatches.
        """
        root_owned_files = []
        for root, _, files in os.walk(self.base_path):
            # Improved segment matching to avoid skipping unintended folders
            path_parts = root.split(os.sep)
            if any(part in path_parts for part in ["venv", ".venv", ".git"]):
                continue

            for name in files:
                full_path = os.path.join(root, name)
                try:
                    if os.stat(full_path).st_uid == 0:
                        root_owned_files.append(full_path)
                except (PermissionError, FileNotFoundError):
                    continue
        return root_owned_files

    def check_compose_config(self) -> None:
        """Checks if docker-compose.yml uses the correct user mapping."""
        compose_path = os.path.join(self.base_path, "docker-compose.yml")
        if os.path.exists(compose_path):
            try:
                with open(compose_path, encoding="utf-8") as f:
                    content = f.read()
                    if "user:" not in content:
                        console.print(
                            "\n[bold yellow]💡 Tip: To prevent future lockouts, add "
                            "'user: \"${UID}:${GID}\"' to your services in "
                            "docker-compose.yml.[/bold yellow]"
                        )
            except Exception:
                pass

    def fix_permissions(self, file_paths: list[str]) -> bool:
        """Attempts to change ownership of files back to the current user.

        Args:
            file_paths: List of full paths to files requiring ownership changes.

        Returns:
            bool: True on success, False on failure (handles subprocess and permission errors).
        """
        if not file_paths:
            return True

        if platform.system() == "Windows":
            return False

        try:
            uid = os.getuid()
            gid = os.getgid()
            # Added 60s timeout to prevent hanging on sudo prompts
            subprocess.run(
                ["sudo", "chown", f"{uid}:{gid}"] + file_paths,
                check=True,
                capture_output=True,
                timeout=60,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, PermissionError):
            return False
