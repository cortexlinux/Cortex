import subprocess
from pathlib import Path

class GitManager:
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)

    def init_repo(self):
        if (self.config_path / ".git").exists():
            return False

        subprocess.run(
            ["git", "init"],
            cwd=self.config_path,
            check=True
        )
        return True
