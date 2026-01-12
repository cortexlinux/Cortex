"""
System Health Check for Cortex Linux
Performs diagnostic checks and provides fix suggestions.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from cortex.ui import (
    console,
    section,
    spinner,
    success,
    warning,
    error,
    summary_box,
    info,
)
from cortex.validators import validate_api_key
from cortex.branding import show_banner
import time


class SystemDoctor:
    """
    Performs comprehensive system health checks and diagnostics.

    Checks for:
    - Python version compatibility
    - Required Python dependencies
    - GPU drivers (NVIDIA/AMD)
    - CUDA/ROCm availability
    - Ollama installation and status
    - API key configuration
    - Disk space availability
    - System memory

    Attributes:
        warnings: List of non-critical issues found
        failures: List of critical issues that may prevent operation
        suggestions: List of fix commands for issues
        passes: List of successful checks
    """

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.failures: list[str] = []
        self.suggestions: list[str] = []
        self.passes: list[str] = []

    def run_checks(self) -> int:
        """
        Run all health checks and return appropriate exit code.

        Exit codes:
            0: All checks passed, system is healthy
            1: Warnings found, system can operate but has recommendations
            2: Critical failures found, system may not work properly

        Returns:
            int: Exit code reflecting system health status (0, 1, or 2)
        """
        console.print()
        show_banner()
        console.print()
        success("Cortex System Health Check")
        console.print()

        with spinner("[CX] Scanning system..."):
            time.sleep(0.5)
            # System Info (includes API provider and security features)
            self._print_section("System Configuration")
            self._check_api_keys()
            self._check_security_tools()

            # Python & Dependencies
            self._print_section("Python & Dependencies")
            self._check_python()
            self._check_dependencies()
   
            time.sleep(0.5)
            self._print_section("GPU & Acceleration")
            self._check_gpu_driver()
            self._check_cuda()
            time.sleep(0.5)
            self._print_section("AI & Services")
            self._check_ollama()

            time.sleep(0.5)
            self._print_section("System Resources")
            self._check_disk_space()
            self._check_memory()

        self._print_summary()

        if self.failures:
            return 2  # Critical failures
        elif self.warnings:
            return 1  # Warnings only
        return 0  # All good

    def _print_section(self, title: str) -> None:
        """Print a section header using UI's section helper."""
        section(title)

    def _print_check(
        self,
        status: str,
        message: str,
        suggestion: Optional[str] = None,
    ) -> None:
        """
        Print a check result using UI helpers and track statuses.

        Args:
            status: One of "PASS", "WARN", "FAIL", or "INFO"
            message: Description of the check result
            suggestion: Optional fix command or suggestion
        """
        if status == "PASS":
            success(message, details=(suggestion or ""))
            self.passes.append(message)
        elif status == "WARN":
            warning(message, details=(suggestion or ""))
            self.warnings.append(message)
            if suggestion:
                self.suggestions.append(suggestion)
        elif status == "FAIL":
            error(message, details=(suggestion or ""))
            self.failures.append(message)
            if suggestion:
                self.suggestions.append(suggestion)
        else:
            info(message)
            # INFO neither pass nor fail; don't add to pass/warn/fail lists.

    def _check_python(self) -> None:
        """Check Python version compatibility."""
        version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        if sys.version_info >= (3, 10):  # noqa: UP036
            self._print_check("PASS", f"Python {version}")
        else:
            self._print_check(
                "FAIL",
                f"Python {version} (3.10+ required)",
                "Install Python 3.10+: sudo apt install python3.11",
            )

    def _check_dependencies(self) -> None:
        """Check packages from requirements.txt."""
        missing: list[str] = []
        requirements_path = Path("requirements.txt")

        if not requirements_path.exists():
            self._print_check("WARN", "No requirements.txt found")
            return

        # Map requirement names to importable module names
        name_overrides = {
            "pyyaml": "yaml",
            "typing-extensions": "typing_extensions",
            "python-dotenv": "dotenv",
        }

        try:
            with open(requirements_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        raw_name = line.split("==")[0].split(">")[0].split("<")[0].strip()
                        pkg_name = name_overrides.get(
                            raw_name.lower(), raw_name.lower().replace("-", "_")
                        )
                        try:
                            __import__(pkg_name)
                        except ImportError:
                            missing.append(raw_name)
        except Exception:
            self._print_check("WARN", "Could not read requirements.txt")
            return

        if not missing:
            self._print_check("PASS", "All requirements.txt packages installed")
        elif len(missing) < 3:
            self._print_check(
                "WARN",
                f"Missing from requirements.txt: {', '.join(missing)}",
                "Install dependencies: pip install -r requirements.txt",
            )
        else:
            self._print_check(
                "FAIL",
                f"Missing {len(missing)} packages from requirements.txt: {', '.join(missing[:3])}...",
                "Install dependencies: pip install -r requirements.txt",
            )

    def _check_gpu_driver(self) -> None:
        """Check for GPU drivers (NVIDIA or AMD ROCm)."""
        # Check NVIDIA
        if shutil.which("nvidia-smi"):
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    version = result.stdout.strip().split("\n")[0]
                    self._print_check("PASS", f"NVIDIA Driver {version}")
                    return
            except (subprocess.TimeoutExpired, Exception):
                pass

        # Check AMD ROCm
        if shutil.which("rocm-smi"):
            try:
                result = subprocess.run(
                    ["rocm-smi", "--showdriverversion"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    self._print_check("PASS", "AMD ROCm driver detected")
                    return
            except (subprocess.TimeoutExpired, Exception):
                pass

        # No GPU found - this is a warning, not a failure
        self._print_check(
            "WARN",
            "No GPU detected (CPU-only mode supported, local inference will be slower)",
            "Optional: Install NVIDIA/AMD drivers for acceleration",
        )

    def _check_cuda(self) -> None:
        """Check CUDA/ROCm availability for GPU acceleration."""
        # Check CUDA (nvcc)
        if shutil.which("nvcc"):
            try:
                result = subprocess.run(
                    ["nvcc", "--version"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and "release" in result.stdout:
                    version_line = result.stdout.split("release")[1].split(",")[0].strip()
                    self._print_check("PASS", f"CUDA {version_line}")
                    return
            except (subprocess.TimeoutExpired, Exception):
                pass

        # Check ROCm
        rocm_info_path = Path("/opt/rocm/.info/version")
        if rocm_info_path.exists():
            try:
                version = rocm_info_path.read_text(encoding="utf-8").strip()
                self._print_check("PASS", f"ROCm {version}")
                return
            except (OSError, UnicodeDecodeError):
                self._print_check("PASS", "ROCm installed")
                return
        elif Path("/opt/rocm").exists():
            self._print_check("PASS", "ROCm installed")
            return

        # Check if PyTorch reports CUDA available (software level)
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                self._print_check("PASS", "CUDA available (PyTorch)")
                return
        except ImportError:
            # torch not installed; just continue
            pass
        except Exception:
            # any other torch-related issue, ignore here
            pass

        self._print_check(
            "WARN",
            "CUDA/ROCm not found (GPU acceleration unavailable)",
            "Install CUDA: https://developer.nvidia.com/cuda-downloads",
        )

    def _check_ollama(self) -> None:
        """Check if Ollama is installed and running."""
        if not shutil.which("ollama"):
            self._print_check(
                "WARN",
                "Ollama not installed",
                "Install Ollama: curl https://ollama.ai/install.sh | sh",
            )
            return

        # If requests present, query localhost
        try:
            import requests  # type: ignore

            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                self._print_check("PASS", "Ollama installed and running")
                return
        except Exception:
            pass

        # Ollama installed but likely not running
        self._print_check(
            "WARN", "Ollama installed but not running", "Start Ollama: ollama serve &"
        )

    def _check_api_keys(self) -> None:
        """Check if API keys are configured for cloud models."""
        is_valid, provider, error_msg = validate_api_key()

        if is_valid:
            self._print_check("PASS", f"{provider} API key configured")
            return

        # If provider is explicitly set to Ollama (local), treat as pass
        ollama_provider = os.environ.get("CORTEX_PROVIDER", "").lower()
        if ollama_provider == "ollama":
            self._print_check("PASS", "API Provider: Ollama (local)")
            return

        # Otherwise warn
        self._print_check(
            "WARN",
            "No API keys configured (required for cloud models)",
            "Configure API key: export ANTHROPIC_API_KEY=sk-... or run 'cortex wizard'",
        )

    def _check_security_tools(self) -> None:
        """Check security features like Firejail availability."""
        firejail_path = shutil.which("firejail")
        if firejail_path:
            self._print_check("PASS", f"Firejail available at {firejail_path}")
        else:
            self._print_check(
                "WARN",
                "Firejail not installed (sandboxing unavailable)",
                "Install: sudo apt-get install firejail",
            )

    def _check_disk_space(self) -> None:
        """Check available disk space for model storage."""
        try:
            usage = shutil.disk_usage(os.path.expanduser("~"))
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)

            if free_gb > 20:
                self._print_check(
                    "PASS", f"{free_gb:.1f}GB free disk space ({total_gb:.1f}GB total)"
                )
            elif free_gb > 10:
                self._print_check(
                    "WARN",
                    f"{free_gb:.1f}GB free (20GB+ recommended for models)",
                    "Free up disk space: sudo apt clean && docker system prune -a",
                )
            else:
                self._print_check(
                    "FAIL",
                    f"Only {free_gb:.1f}GB free (critically low)",
                    "Free up disk space: sudo apt autoremove && sudo apt clean",
                )
        except (OSError, Exception) as e:
            self._print_check("WARN", f"Could not check disk space: {type(e).__name__}")

    def _check_memory(self) -> None:
        """Check system RAM availability."""
        mem_gb = self._get_system_memory()

        if mem_gb is None:
            self._print_check("WARN", "Could not detect system RAM")
            return

        if mem_gb >= 16:
            self._print_check("PASS", f"{mem_gb:.1f}GB RAM")
        elif mem_gb >= 8:
            self._print_check(
                "WARN",
                f"{mem_gb:.1f}GB RAM (16GB recommended for larger models)",
                "Consider upgrading RAM or use smaller models",
            )
        else:
            self._print_check(
                "FAIL",
                f"Only {mem_gb:.1f}GB RAM (8GB minimum required)",
                 "Upgrade RAM to at least 8GB",
            )

    def _get_system_memory(self) -> Optional[float]:
        """
        Get system memory in GB.

        Returns:
            float: Total system memory in GB, or None if detection fails
        """
        # Try /proc/meminfo (Linux)
        try:
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_kb = int(line.split()[1])
                        return mem_kb / (1024**2)
        except (OSError, ValueError, IndexError):
            pass

        # Try psutil (cross-platform)
        try:
            import psutil  # type: ignore

            return psutil.virtual_memory().total / (1024**3)
        except ImportError:
            pass
        except Exception:
            pass

        return None

    def _print_summary(self) -> None:
        """Print summary and suggested fixes using UI helpers."""
        console.print()

        # Build counts and short summary items
        summary_items: list[str] = []
        if self.passes:
            summary_items.append(f"Passed: {len(self.passes)} checks")
        if self.warnings:
            summary_items.append(f"Warnings: {len(self.warnings)}")
        if self.failures:
            summary_items.append(f"Failures: {len(self.failures)}")

        # Use summary_box for a human-friendly block
        success_state = not (self.failures or self.warnings)
        summary_box("SYSTEM HEALTH SUMMARY", summary_items, success=success_state)

        # Detailed panels for suggestions if present
        if self.suggestions:
            console.print()
            console.print("[bold cyan]💡 Suggested fixes:[/bold cyan]")
            for i, suggestion in enumerate(self.suggestions, 1):
                console.print(f"   [dim]{i}.[/dim] {suggestion}")
            console.print()

        if self.failures:
            error(f"{len(self.failures)} critical failure(s) found")
            for fmsg in self.failures:
                console.print(f"  - [red]✗[/red] {fmsg}")
        elif self.warnings:
            warning(f"{len(self.warnings)} warning(s) found")
            for wmsg in self.warnings:
                console.print(f"    [yellow]⚠[/yellow] {wmsg}")
        else:
            success("All checks passed! System is healthy.")

def run_doctor() -> int:
    """
    Run the system doctor and return exit code.

    Returns:
        int: Exit code (0 = all good, 1 = warnings, 2 = failures)
    """
    doctor = SystemDoctor()
    return doctor.run_checks()


if __name__ == "__main__":
    sys.exit(run_doctor())
