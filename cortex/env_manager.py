"""
Environment Variable Manager for Cortex Linux
Manages per-application environment variables with encryption support.

Features:
- Per-application environment isolation
- Encrypted storage for sensitive values
- Environment templates
- Variable validation
- Auto-load on service start
- Export/import functionality
"""

import base64
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


@dataclass
class EnvVariable:
    """Represents a single environment variable."""

    key: str
    value: str
    encrypted: bool = False
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvVariable":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class EnvTemplate:
    """Environment variable template for quick setup."""

    name: str
    description: str
    variables: Dict[str, str]  # key -> default_value or placeholder
    required_vars: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvTemplate":
        """Create from dictionary."""
        return cls(**data)


class ValidationRule:
    """Base class for environment variable validation rules."""

    def __init__(self, error_message: str = "Validation failed"):
        self.error_message = error_message

    def validate(self, key: str, value: str) -> tuple[bool, Optional[str]]:
        """
        Validate a key-value pair.

        Returns:
            Tuple of (is_valid, error_message)
        """
        raise NotImplementedError


class RegexValidator(ValidationRule):
    """Validates value against a regex pattern."""

    def __init__(self, pattern: str, error_message: str = "Value does not match pattern"):
        super().__init__(error_message)
        self.pattern = re.compile(pattern)

    def validate(self, key: str, value: str) -> tuple[bool, Optional[str]]:
        if self.pattern.match(value):
            return True, None
        return False, f"{key}: {self.error_message}"


class URLValidator(ValidationRule):
    """Validates that value is a valid URL."""

    def __init__(self):
        super().__init__("Must be a valid URL")
        self.url_pattern = re.compile(
            r"^(?:https?|ftp|postgres|postgresql|mysql|redis|mongodb|amqp)://"  # Protocol
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain
            r"localhost|"  # localhost
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # IP
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?].*)?$",  # optional path
            re.IGNORECASE,
        )

    def validate(self, key: str, value: str) -> tuple[bool, Optional[str]]:
        if self.url_pattern.match(value):
            return True, None
        return False, f"{key}: {self.error_message}"


class RequiredValidator(ValidationRule):
    """Validates that value is not empty."""

    def __init__(self):
        super().__init__("Value is required")

    def validate(self, key: str, value: str) -> tuple[bool, Optional[str]]:
        if value and value.strip():
            return True, None
        return False, f"{key}: {self.error_message}"


class EnvManager:
    """
    Manages environment variables for applications.

    Features:
    - Per-application isolation
    - Encrypted storage for secrets
    - Variable validation
    - Templates for common configurations
    """

    def __init__(self, cortex_home: Optional[Path] = None):
        """
        Initialize EnvManager.

        Args:
            cortex_home: Base directory for Cortex data (defaults to ~/.cortex)
        """
        self.cortex_home = cortex_home or Path.home() / ".cortex"
        self.env_dir = self.cortex_home / "environments"
        self.templates_dir = self.cortex_home / "env_templates"
        self.key_file = self.cortex_home / ".env_key"

        # Create directories
        self.env_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Initialize encryption
        self._init_encryption()

        # Load built-in templates
        self._load_builtin_templates()

        # Validation rules registry
        self.validation_rules: Dict[str, List[ValidationRule]] = {}
        self._register_common_validators()

    def _init_encryption(self):
        """Initialize encryption key."""
        if self.key_file.exists():
            with open(self.key_file, "rb") as f:
                self.cipher_key = f.read()
        else:
            # Generate new key using PBKDF2
            # In production, this should use a user-provided password
            # For now, we'll use machine-specific data
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            # Use machine ID or generate random key
            try:
                with open("/etc/machine-id", "rb") as f:
                    machine_id = f.read().strip()
            except FileNotFoundError:
                machine_id = os.urandom(32)

            key = kdf.derive(machine_id)
            self.cipher_key = base64.urlsafe_b64encode(key)

            # Store key securely
            self.key_file.write_bytes(self.cipher_key)
            self.key_file.chmod(0o600)

        self.cipher = Fernet(self.cipher_key)

    def _encrypt(self, value: str) -> str:
        """Encrypt a value."""
        return self.cipher.encrypt(value.encode()).decode()

    def _decrypt(self, encrypted_value: str) -> str:
        """Decrypt a value."""
        return self.cipher.decrypt(encrypted_value.encode()).decode()

    def _get_app_file(self, app_name: str) -> Path:
        """Get the file path for an application's environment."""
        return self.env_dir / f"{app_name}.json"

    def _load_app_env(self, app_name: str) -> Dict[str, EnvVariable]:
        """Load environment variables for an application."""
        app_file = self._get_app_file(app_name)
        if not app_file.exists():
            return {}

        with open(app_file) as f:
            data = json.load(f)

        return {key: EnvVariable.from_dict(var_data) for key, var_data in data.items()}

    def _save_app_env(self, app_name: str, env_vars: Dict[str, EnvVariable]):
        """Save environment variables for an application."""
        app_file = self._get_app_file(app_name)
        data = {key: var.to_dict() for key, var in env_vars.items()}

        with open(app_file, "w") as f:
            json.dump(data, f, indent=2)

        app_file.chmod(0o600)

    def set(
        self,
        app_name: str,
        key: str,
        value: str,
        encrypt: bool = False,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> bool:
        """
        Set an environment variable for an application.

        Args:
            app_name: Application name
            key: Variable name
            value: Variable value
            encrypt: Whether to encrypt the value
            description: Optional description
            tags: Optional tags for organization

        Returns:
            True if successful
        """
        # Validate
        is_valid, error = self.validate(key, value)
        if not is_valid:
            raise ValueError(error)

        env_vars = self._load_app_env(app_name)

        # Update timestamp if variable exists
        now = datetime.utcnow().isoformat()
        if key in env_vars:
            existing = env_vars[key]
            created_at = existing.created_at
        else:
            created_at = now

        # Encrypt if requested
        stored_value = self._encrypt(value) if encrypt else value

        env_vars[key] = EnvVariable(
            key=key,
            value=stored_value,
            encrypted=encrypt,
            description=description,
            created_at=created_at,
            updated_at=now,
            tags=tags or [],
        )

        self._save_app_env(app_name, env_vars)
        return True

    def get(self, app_name: str, key: str, decrypt: bool = True) -> Optional[str]:
        """
        Get an environment variable value.

        Args:
            app_name: Application name
            key: Variable name
            decrypt: Whether to decrypt encrypted values

        Returns:
            Variable value or None if not found
        """
        env_vars = self._load_app_env(app_name)
        if key not in env_vars:
            return None

        var = env_vars[key]
        if var.encrypted and decrypt:
            return self._decrypt(var.value)
        return var.value

    def delete(self, app_name: str, key: str) -> bool:
        """
        Delete an environment variable.

        Args:
            app_name: Application name
            key: Variable name

        Returns:
            True if deleted, False if not found
        """
        env_vars = self._load_app_env(app_name)
        if key not in env_vars:
            return False

        del env_vars[key]
        self._save_app_env(app_name, env_vars)
        return True

    def list(self, app_name: str) -> Dict[str, EnvVariable]:
        """
        List all environment variables for an application.

        Args:
            app_name: Application name

        Returns:
            Dictionary of variable name -> EnvVariable
        """
        return self._load_app_env(app_name)

    def list_apps(self) -> List[str]:
        """
        List all applications with environment variables.

        Returns:
            List of application names
        """
        return [
            f.stem for f in self.env_dir.glob("*.json") if f.is_file()
        ]

    def export(self, app_name: str, format: str = "env") -> str:
        """
        Export environment variables to a string.

        Args:
            app_name: Application name
            format: Export format ('env', 'json', 'yaml')

        Returns:
            Formatted string
        """
        env_vars = self._load_app_env(app_name)

        if format == "json":
            data = {}
            for key, var in env_vars.items():
                if var.encrypted:
                    data[key] = "[encrypted]"
                else:
                    data[key] = var.value
            return json.dumps(data, indent=2)

        elif format == "yaml":
            lines = []
            for key, var in env_vars.items():
                if var.encrypted:
                    value = "[encrypted]"
                else:
                    value = var.value
                # Escape quotes in YAML
                value = value.replace('"', '\\"')
                lines.append(f'{key}: "{value}"')
            return "\n".join(lines)

        else:  # env format (default)
            lines = []
            for key, var in env_vars.items():
                if var.encrypted:
                    value = "[encrypted]"
                else:
                    value = var.value
                # Escape quotes and special chars for shell
                value = value.replace('"', '\\"')
                lines.append(f'export {key}="{value}"')
            return "\n".join(lines)

    def import_env(self, app_name: str, env_data: str, format: str = "env", merge: bool = False):
        """
        Import environment variables from a string.

        Args:
            app_name: Application name
            env_data: Environment data to import
            format: Import format ('env', 'json')
            merge: If True, merge with existing vars; if False, replace
        """
        if not merge:
            # Clear existing variables
            env_vars = {}
        else:
            env_vars = self._load_app_env(app_name)

        if format == "json":
            data = json.loads(env_data)
            for key, value in data.items():
                if value != "[encrypted]":
                    # Set directly to new env_vars
                    now = datetime.utcnow().isoformat()
                    env_vars[key] = EnvVariable(
                        key=key,
                        value=value,
                        encrypted=False,
                        description="",
                        created_at=now,
                        updated_at=now,
                        tags=[],
                    )

        elif format == "env":
            for line in env_data.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Parse export KEY="value" or KEY=value
                if line.startswith("export "):
                    line = line[7:]  # Remove "export "

                if "=" not in line:
                    continue

                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()

                # Remove quotes
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                # Unescape
                value = value.replace('\\"', '"')

                if value != "[encrypted]":
                    # Set directly to new env_vars
                    now = datetime.utcnow().isoformat()
                    env_vars[key] = EnvVariable(
                        key=key,
                        value=value,
                        encrypted=False,
                        description="",
                        created_at=now,
                        updated_at=now,
                        tags=[],
                    )

        # Save the env_vars
        self._save_app_env(app_name, env_vars)

    def apply_template(self, app_name: str, template_name: str, variables: Optional[Dict[str, str]] = None):
        """
        Apply an environment template to an application.

        Args:
            app_name: Application name
            template_name: Template name
            variables: Variable overrides
        """
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found")

        variables = variables or {}

        # Check required variables
        missing = [var for var in template.required_vars if var not in variables]
        if missing:
            raise ValueError(f"Missing required variables: {', '.join(missing)}")

        # Apply template variables
        for key, default_value in template.variables.items():
            value = variables.get(key, default_value)
            self.set(app_name, key, value, description=f"From template: {template_name}")

    def create_template(self, template: EnvTemplate):
        """Create or update an environment template."""
        template_file = self.templates_dir / f"{template.name}.json"
        with open(template_file, "w") as f:
            json.dump(template.to_dict(), f, indent=2)

    def get_template(self, template_name: str) -> Optional[EnvTemplate]:
        """Get an environment template."""
        template_file = self.templates_dir / f"{template_name}.json"
        if not template_file.exists():
            return None

        with open(template_file) as f:
            data = json.load(f)

        return EnvTemplate.from_dict(data)

    def list_templates(self) -> List[EnvTemplate]:
        """List all available templates."""
        templates = []
        for template_file in self.templates_dir.glob("*.json"):
            with open(template_file) as f:
                data = json.load(f)
            templates.append(EnvTemplate.from_dict(data))
        return templates

    def _load_builtin_templates(self):
        """Load built-in environment templates."""
        builtin_templates = [
            EnvTemplate(
                name="nodejs",
                description="Node.js application environment",
                variables={
                    "NODE_ENV": "production",
                    "PORT": "3000",
                    "DATABASE_URL": "postgresql://localhost/myapp",
                    "REDIS_URL": "redis://localhost:6379",
                    "LOG_LEVEL": "info",
                },
                required_vars=["DATABASE_URL"],
                tags=["nodejs", "backend"],
            ),
            EnvTemplate(
                name="python",
                description="Python application environment",
                variables={
                    "PYTHON_ENV": "production",
                    "DATABASE_URL": "postgresql://localhost/myapp",
                    "REDIS_URL": "redis://localhost:6379",
                    "LOG_LEVEL": "INFO",
                    "DEBUG": "False",
                },
                required_vars=["DATABASE_URL"],
                tags=["python", "backend"],
            ),
            EnvTemplate(
                name="django",
                description="Django application environment",
                variables={
                    "DJANGO_SETTINGS_MODULE": "myapp.settings",
                    "SECRET_KEY": "change-me",
                    "DEBUG": "False",
                    "DATABASE_URL": "postgresql://localhost/myapp",
                    "ALLOWED_HOSTS": "localhost,127.0.0.1",
                },
                required_vars=["SECRET_KEY", "DATABASE_URL"],
                tags=["python", "django", "web"],
            ),
            EnvTemplate(
                name="docker",
                description="Docker environment variables",
                variables={
                    "DOCKER_HOST": "unix:///var/run/docker.sock",
                    "COMPOSE_PROJECT_NAME": "myapp",
                    "COMPOSE_FILE": "docker-compose.yml",
                },
                required_vars=[],
                tags=["docker", "devops"],
            ),
        ]

        for template in builtin_templates:
            template_file = self.templates_dir / f"{template.name}.json"
            if not template_file.exists():
                self.create_template(template)

    def add_validation_rule(self, key_pattern: str, rule: ValidationRule):
        """
        Add a validation rule for environment variables.

        Args:
            key_pattern: Regex pattern to match variable names
            rule: ValidationRule instance
        """
        if key_pattern not in self.validation_rules:
            self.validation_rules[key_pattern] = []
        self.validation_rules[key_pattern].append(rule)

    def _register_common_validators(self):
        """Register common validation rules."""
        # URLs
        self.add_validation_rule(r".*_URL$", URLValidator())
        self.add_validation_rule(r".*DATABASE.*", RequiredValidator())

        # API keys (must not be empty)
        self.add_validation_rule(r".*_API_KEY$", RequiredValidator())
        self.add_validation_rule(r".*_SECRET.*", RequiredValidator())

        # Ports (numeric, 1-65535)
        self.add_validation_rule(
            r".*PORT.*",
            RegexValidator(r"^([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$", "Must be a valid port number (1-65535)"),
        )

    def validate(self, key: str, value: str) -> tuple[bool, Optional[str]]:
        """
        Validate an environment variable.

        Args:
            key: Variable name
            value: Variable value

        Returns:
            Tuple of (is_valid, error_message)
        """
        for pattern, rules in self.validation_rules.items():
            if re.match(pattern, key, re.IGNORECASE):
                for rule in rules:
                    is_valid, error = rule.validate(key, value)
                    if not is_valid:
                        return False, error
        return True, None

    def get_env_dict(self, app_name: str, decrypt: bool = True) -> Dict[str, str]:
        """
        Get environment variables as a plain dictionary.

        Args:
            app_name: Application name
            decrypt: Whether to decrypt encrypted values

        Returns:
            Dictionary of key-value pairs
        """
        env_vars = self._load_app_env(app_name)
        result = {}
        for key, var in env_vars.items():
            if var.encrypted and decrypt:
                result[key] = self._decrypt(var.value)
            else:
                result[key] = var.value
        return result

    def load_env_to_os(self, app_name: str):
        """
        Load environment variables into os.environ.

        Args:
            app_name: Application name
        """
        env_dict = self.get_env_dict(app_name, decrypt=True)
        os.environ.update(env_dict)

    def delete_app(self, app_name: str) -> bool:
        """
        Delete all environment variables for an application.

        Args:
            app_name: Application name

        Returns:
            True if deleted, False if not found
        """
        app_file = self._get_app_file(app_name)
        if not app_file.exists():
            return False

        app_file.unlink()
        return True
