"""
Cortex Desktop Notification Module.
Handles system alerts with Smart DND (Do Not Disturb) mode.
"""
import os
import shutil
import subprocess
import json
from datetime import datetime, time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Configuration
CONFIG_DIR = Path.home() / ".cortex"
CONFIG_FILE = CONFIG_DIR / "notify_config.json"

@dataclass
class NotifyConfig:
    enabled: bool = True
    dnd_enabled: bool = True
    dnd_start: str = "22:00"
    dnd_end: str = "08:00"

class NotificationManager:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> NotifyConfig:
        if not CONFIG_FILE.exists():
            return NotifyConfig()
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                return NotifyConfig(**data)
        except Exception:
            return NotifyConfig()

    def save_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config.__dict__, f, indent=2)

    def _is_dnd_active(self) -> bool:
        if not self.config.dnd_enabled:
            return False
        
        now = datetime.now().time()
        try:
            start = datetime.strptime(self.config.dnd_start, "%H:%M").time()
            end = datetime.strptime(self.config.dnd_end, "%H:%M").time()
        except ValueError:
            return False # Invalid config, disable DND logic

        if start < end:
            return start <= now <= end
        else: # Over midnight (e.g. 22:00 to 08:00)
            return now >= start or now <= end

    def send(self, title: str, message: str, level: str = "normal") -> bool:
        """
        Send a desktop notification via notify-send.
        Returns True if sent, False if suppressed or failed.
        """
        if not self.config.enabled:
            return False

        if self._is_dnd_active() and level != "critical":
            # Suppress non-critical notifications in DND
            return False

        # Linux Native Integration
        notify_bin = shutil.which('notify-send')
        if not notify_bin:
            # Fallback to console log if binary missing
            print(f"[{level.upper()}] {title}: {message}")
            return True

        urgency = "critical" if level == "critical" else "normal"
        
        try:
            subprocess.run(
                [notify_bin, title, message, "-u", urgency, "-a", "Cortex"],
                check=True,
                capture_output=True
            )
            return True
        except subprocess.SubprocessError:
            return False

# --- CLI Entry Point ---
def notify_cli(title: str, message: str, configure: bool = False, dnd_toggle: bool = False):
    """CLI handler for notifications."""
    manager = NotificationManager()

    if configure:
        print(f"Current Config: {manager.config}")
        return

    if dnd_toggle:
        manager.config.dnd_enabled = not manager.config.dnd_enabled
        manager.save_config()
        status = "enabled" if manager.config.dnd_enabled else "disabled"
        print(f"✅ Smart DND mode {status}.")
        return

    # Send Notification
    sent = manager.send(title, message)
    if sent:
        print("✅ Notification sent.")
    else:
        print("zzz Notification suppressed (DND or Disabled).")

if __name__ == "__main__":
    # Test run
    notify_cli("Cortex Test", "Hello from CLI!", dnd_toggle=False)
