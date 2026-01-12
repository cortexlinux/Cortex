"""Cortex Trust - Trust level management for reducing prompt friction."""

import os
import json
from pathlib import Path
from typing import Optional, Set, Dict, List
from enum import Enum


class TrustScope(Enum):
    COMMAND = "command"
    COMMAND_TYPE = "type"
    DIRECTORY = "directory"
    GLOBAL = "global"


class TrustManager:
    CONFIG_FILE = Path.home() / ".config" / "cortex" / "trust.json"
    
    def __init__(self):
        self._session_commands: Set[str] = set()
        self._session_command_types: Set[str] = set()
        self._session_directories: Set[str] = set()
        self._global_commands: Set[str] = set()
        self._global_command_types: Set[str] = set()
        self._load_global_trust()
    
    def _load_global_trust(self) -> None:
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE) as f:
                    data = json.load(f)
                    self._global_commands = set(data.get("commands", []))
                    self._global_command_types = set(data.get("command_types", []))
            except (json.JSONDecodeError, IOError):
                pass
    
    def _save_global_trust(self) -> None:
        self.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_FILE, 'w') as f:
            json.dump({"commands": list(self._global_commands), "command_types": list(self._global_command_types)}, f, indent=2)
    
    def _get_command_type(self, command: str) -> str:
        parts = command.strip().split()
        if not parts:
            return ""
        base = parts[0]
        if len(parts) > 1 and base in ('docker', 'git', 'apt', 'pip', 'npm', 'systemctl'):
            return f"{base} {parts[1]}"
        return base
    
    def is_trusted(self, command: str, directory: Optional[str] = None) -> bool:
        command = command.strip()
        command_type = self._get_command_type(command)
        if command in self._session_commands or command in self._global_commands:
            return True
        if command_type in self._session_command_types or command_type in self._global_command_types:
            return True
        if directory:
            directory = os.path.abspath(directory)
            for trusted_dir in self._session_directories:
                if directory.startswith(trusted_dir):
                    return True
        return False
    
    def add_session_trust(self, command: str, scope: TrustScope = TrustScope.COMMAND_TYPE) -> None:
        if scope == TrustScope.COMMAND:
            self._session_commands.add(command.strip())
        elif scope == TrustScope.COMMAND_TYPE:
            self._session_command_types.add(self._get_command_type(command))
    
    def add_directory_trust(self, directory: str) -> None:
        self._session_directories.add(os.path.abspath(directory))
    
    def add_global_trust(self, command: str, scope: TrustScope = TrustScope.COMMAND_TYPE) -> None:
        if scope == TrustScope.COMMAND:
            self._global_commands.add(command.strip())
        elif scope == TrustScope.COMMAND_TYPE:
            self._global_command_types.add(self._get_command_type(command))
        self._save_global_trust()
    
    def remove_trust(self, command: str) -> None:
        command = command.strip()
        command_type = self._get_command_type(command)
        self._session_commands.discard(command)
        self._session_command_types.discard(command_type)
        self._global_commands.discard(command)
        self._global_command_types.discard(command_type)
        self._save_global_trust()
    
    def clear_session_trust(self) -> None:
        self._session_commands.clear()
        self._session_command_types.clear()
        self._session_directories.clear()
    
    def clear_all_trust(self) -> None:
        self.clear_session_trust()
        self._global_commands.clear()
        self._global_command_types.clear()
        self._save_global_trust()
    
    def list_trusted(self) -> Dict[str, List[str]]:
        return {
            "session_commands": list(self._session_commands),
            "session_command_types": list(self._session_command_types),
            "session_directories": list(self._session_directories),
            "global_commands": list(self._global_commands),
            "global_command_types": list(self._global_command_types),
        }


trust_manager = TrustManager()
