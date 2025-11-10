#!/usr/bin/env python3
"""
System Requirements Pre-flight Checker for Cortex Linux
Validates system meets requirements before installation begins.

Features:
- Disk space checking with safety buffer
- RAM validation (total + available)
- OS compatibility matrix
- CPU architecture validation
- Prerequisite package detection
- GPU/CUDA detection
- Warning/error reporting with severity levels
- Interactive prompts with override options
"""

import os
import sys
import platform
import shutil
import subprocess
import json
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class CheckStatus(Enum):
    """Status of a requirement check."""
    PASS = "pass"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


class Severity(Enum):
    """Severity level for messages."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class RequirementCheck:
    """Result of a single requirement check."""
    name: str
    status: CheckStatus
    message: str
    actual_value: Optional[Any] = None
    required_value: Optional[Any] = None
    severity: Severity = Severity.INFO
    can_continue: bool = True
    suggestion: Optional[str] = None
    
    def __str__(self) -> str:
        """String representation of check result."""
        icon = {
            CheckStatus.PASS: "✅",
            CheckStatus.WARNING: "⚠️",
            CheckStatus.ERROR: "❌",
            CheckStatus.INFO: "ℹ️"
        }.get(self.status, "?")
        
        return f"{icon} {self.name}: {self.message}"


@dataclass
class PackageRequirements:
    """Requirements for a package installation."""
    package_name: str
    min_disk_space_gb: float = 1.0
    min_ram_gb: float = 2.0
    min_available_ram_gb: float = 1.0
    supported_os: List[str] = field(default_factory=lambda: ["ubuntu", "debian", "fedora", "centos", "rhel"])
    supported_architectures: List[str] = field(default_factory=lambda: ["x86_64", "amd64"])
    required_packages: List[str] = field(default_factory=list)
    optional_packages: List[str] = field(default_factory=list)
    requires_gpu: bool = False
    min_python_version: Optional[Tuple[int, int]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'package_name': self.package_name,
            'min_disk_space_gb': self.min_disk_space_gb,
            'min_ram_gb': self.min_ram_gb,
            'min_available_ram_gb': self.min_available_ram_gb,
            'supported_os': self.supported_os,
            'supported_architectures': self.supported_architectures,
            'required_packages': self.required_packages,
            'optional_packages': self.optional_packages,
            'requires_gpu': self.requires_gpu,
            'min_python_version': self.min_python_version
        }


class SystemRequirementsChecker:
    """
    Validates system meets requirements before installation.
    
    Features:
    - Disk space, RAM, OS, CPU validation
    - Prerequisite package detection
    - GPU/CUDA detection
    - Warning system with severity levels
    - Interactive prompts
    - JSON output mode
    """
    
    # OS compatibility matrix
    SUPPORTED_OS = {
        'ubuntu': ['20.04', '22.04', '24.04'],
        'debian': ['10', '11', '12'],
        'fedora': ['37', '38', '39', '40'],
        'centos': ['7', '8', '9'],
        'rhel': ['8', '9'],
        'arch': ['rolling']
    }
    
    # Package requirements database (examples)
    PACKAGE_REQUIREMENTS = {
        'oracle-23-ai': PackageRequirements(
            package_name='oracle-23-ai',
            min_disk_space_gb=30.0,
            min_ram_gb=8.0,
            min_available_ram_gb=4.0,
            requires_gpu=False,  # Works better with GPU but not required
            required_packages=['gcc', 'make', 'libaio1'],
            optional_packages=['cuda', 'nvidia-cuda'],  # GPU related to trigger check
        ),
        'postgresql': PackageRequirements(
            package_name='postgresql',
            min_disk_space_gb=2.0,
            min_ram_gb=2.0,
            min_available_ram_gb=0.5,
            required_packages=[],
        ),
        'docker': PackageRequirements(
            package_name='docker',
            min_disk_space_gb=10.0,
            min_ram_gb=4.0,
            min_available_ram_gb=2.0,
            required_packages=['curl', 'ca-certificates'],
        ),
    }
    
    def __init__(self, 
                 disk_buffer_percent: float = 20.0,
                 enable_interactive: bool = True,
                 force_mode: bool = False,
                 json_output: bool = False,
                 console: Optional[Any] = None):
        """
        Initialize system requirements checker.
        
        Args:
            disk_buffer_percent: Safety buffer for disk space (default 20%)
            enable_interactive: Enable interactive prompts
            force_mode: Skip warnings and continue
            json_output: Output results as JSON
            console: Rich console instance (created if None)
        """
        self.disk_buffer_percent = disk_buffer_percent
        self.enable_interactive = enable_interactive
        self.force_mode = force_mode
        self.json_output = json_output
        
        # Rich console
        if RICH_AVAILABLE and not json_output:
            self.console = console or Console()
        else:
            self.console = None
        
        # Check results
        self.checks: List[RequirementCheck] = []
        self.has_errors: bool = False
        self.has_warnings: bool = False
    
    def check_disk_space(self, required_gb: float, path: str = '/') -> RequirementCheck:
        """
        Check available disk space.
        
        Args:
            required_gb: Required disk space in GB
            path: Path to check (default: root)
            
        Returns:
            RequirementCheck result
        """
        try:
            if PSUTIL_AVAILABLE:
                disk = psutil.disk_usage(path)
                available_gb = disk.free / (1024 ** 3)
            else:
                # Fallback for Windows
                if os.name == 'nt':
                    import ctypes
                    free_bytes = ctypes.c_ulonglong(0)
                    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                        ctypes.c_wchar_p(path), 
                        None, None, 
                        ctypes.pointer(free_bytes)
                    )
                    available_gb = free_bytes.value / (1024 ** 3)
                else:
                    # Unix fallback using df
                    result = subprocess.run(
                        ['df', '-BG', path],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        if len(lines) >= 2:
                            parts = lines[1].split()
                            available_str = parts[3].replace('G', '')
                            available_gb = float(available_str)
                    else:
                        available_gb = 0
            
            # Apply safety buffer
            required_with_buffer = required_gb * (1 + self.disk_buffer_percent / 100)
            
            if available_gb >= required_with_buffer:
                return RequirementCheck(
                    name="Disk Space",
                    status=CheckStatus.PASS,
                    message=f"{available_gb:.1f}GB available ({required_gb:.1f}GB required)",
                    actual_value=f"{available_gb:.1f}GB",
                    required_value=f"{required_gb:.1f}GB",
                    severity=Severity.INFO
                )
            elif available_gb >= required_gb:
                return RequirementCheck(
                    name="Disk Space",
                    status=CheckStatus.WARNING,
                    message=f"{available_gb:.1f}GB available (low buffer, {required_gb:.1f}GB required)",
                    actual_value=f"{available_gb:.1f}GB",
                    required_value=f"{required_gb:.1f}GB",
                    severity=Severity.WARNING,
                    can_continue=True,
                    suggestion="Free up disk space for safer installation"
                )
            else:
                return RequirementCheck(
                    name="Disk Space",
                    status=CheckStatus.ERROR,
                    message=f"Insufficient disk space: {available_gb:.1f}GB available, {required_gb:.1f}GB required",
                    actual_value=f"{available_gb:.1f}GB",
                    required_value=f"{required_gb:.1f}GB",
                    severity=Severity.ERROR,
                    can_continue=False,
                    suggestion=f"Free up at least {(required_gb - available_gb):.1f}GB of disk space"
                )
        except Exception as e:
            return RequirementCheck(
                name="Disk Space",
                status=CheckStatus.WARNING,
                message=f"Could not check disk space: {str(e)}",
                severity=Severity.WARNING,
                can_continue=True
            )
    
    def check_ram(self, required_gb: float, required_available_gb: float = 1.0) -> RequirementCheck:
        """
        Check total and available RAM.
        
        Args:
            required_gb: Required total RAM in GB
            required_available_gb: Required available RAM in GB
            
        Returns:
            RequirementCheck result
        """
        try:
            if PSUTIL_AVAILABLE:
                mem = psutil.virtual_memory()
                total_gb = mem.total / (1024 ** 3)
                available_gb = mem.available / (1024 ** 3)
            else:
                # Fallback methods
                if os.name == 'nt':
                    # Windows
                    import ctypes
                    class MEMORYSTATUSEX(ctypes.Structure):
                        _fields_ = [
                            ("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                        ]
                    
                    stat = MEMORYSTATUSEX()
                    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                    total_gb = stat.ullTotalPhys / (1024 ** 3)
                    available_gb = stat.ullAvailPhys / (1024 ** 3)
                else:
                    # Linux fallback
                    with open('/proc/meminfo', 'r') as f:
                        meminfo = f.read()
                    
                    total_match = re.search(r'MemTotal:\s+(\d+)', meminfo)
                    available_match = re.search(r'MemAvailable:\s+(\d+)', meminfo)
                    
                    if total_match:
                        total_gb = int(total_match.group(1)) / (1024 ** 2)
                    if available_match:
                        available_gb = int(available_match.group(1)) / (1024 ** 2)
            
            # Check total RAM
            if total_gb < required_gb:
                return RequirementCheck(
                    name="RAM",
                    status=CheckStatus.ERROR,
                    message=f"{total_gb:.1f}GB total RAM (minimum {required_gb:.1f}GB required)",
                    actual_value=f"{total_gb:.1f}GB",
                    required_value=f"{required_gb:.1f}GB",
                    severity=Severity.ERROR,
                    can_continue=False,
                    suggestion="Upgrade system RAM or choose a lighter package"
                )
            
            # Check available RAM
            if available_gb < required_available_gb:
                return RequirementCheck(
                    name="RAM",
                    status=CheckStatus.WARNING,
                    message=f"{total_gb:.1f}GB total, {available_gb:.1f}GB available (need {required_available_gb:.1f}GB free)",
                    actual_value=f"{available_gb:.1f}GB available",
                    required_value=f"{required_available_gb:.1f}GB available",
                    severity=Severity.WARNING,
                    can_continue=True,
                    suggestion="Close other applications to free up RAM"
                )
            
            return RequirementCheck(
                name="RAM",
                status=CheckStatus.PASS,
                message=f"{total_gb:.1f}GB total ({available_gb:.1f}GB available, {required_gb:.1f}GB required)",
                actual_value=f"{total_gb:.1f}GB",
                required_value=f"{required_gb:.1f}GB",
                severity=Severity.INFO
            )
            
        except Exception as e:
            return RequirementCheck(
                name="RAM",
                status=CheckStatus.WARNING,
                message=f"Could not check RAM: {str(e)}",
                severity=Severity.WARNING,
                can_continue=True
            )
    
    def check_os_compatibility(self, supported_os: List[str] = None) -> RequirementCheck:
        """
        Check OS version compatibility.
        
        Args:
            supported_os: List of supported OS names
            
        Returns:
            RequirementCheck result
        """
        try:
            # Detect OS
            system = platform.system().lower()
            
            if system == 'linux':
                # Try to detect distribution
                os_name, os_version = self._detect_linux_distribution()
                
                if not supported_os:
                    # No specific requirement, any Linux is OK
                    return RequirementCheck(
                        name="OS",
                        status=CheckStatus.PASS,
                        message=f"{os_name} {os_version}",
                        actual_value=f"{os_name} {os_version}",
                        severity=Severity.INFO
                    )
                
                # Check if OS is supported
                if os_name.lower() in [s.lower() for s in supported_os]:
                    # Check version
                    if os_name.lower() in self.SUPPORTED_OS:
                        supported_versions = self.SUPPORTED_OS[os_name.lower()]
                        if os_version in supported_versions or 'rolling' in supported_versions:
                            return RequirementCheck(
                                name="OS",
                                status=CheckStatus.PASS,
                                message=f"{os_name} {os_version} (supported)",
                                actual_value=f"{os_name} {os_version}",
                                severity=Severity.INFO
                            )
                        else:
                            return RequirementCheck(
                                name="OS",
                                status=CheckStatus.WARNING,
                                message=f"{os_name} {os_version} (version not tested, supported: {', '.join(supported_versions)})",
                                actual_value=f"{os_name} {os_version}",
                                required_value=f"{os_name} {supported_versions}",
                                severity=Severity.WARNING,
                                can_continue=True,
                                suggestion="Installation may work but hasn't been tested on this version"
                            )
                    else:
                        return RequirementCheck(
                            name="OS",
                            status=CheckStatus.PASS,
                            message=f"{os_name} {os_version}",
                            actual_value=f"{os_name} {os_version}",
                            severity=Severity.INFO
                        )
                else:
                    return RequirementCheck(
                        name="OS",
                        status=CheckStatus.WARNING,
                        message=f"{os_name} {os_version} (not officially supported)",
                        actual_value=f"{os_name} {os_version}",
                        required_value=', '.join(supported_os),
                        severity=Severity.WARNING,
                        can_continue=True,
                        suggestion="Package may not work correctly on this OS"
                    )
            
            elif system == 'windows':
                version = platform.version()
                return RequirementCheck(
                    name="OS",
                    status=CheckStatus.INFO,
                    message=f"Windows {version}",
                    actual_value=f"Windows {version}",
                    severity=Severity.INFO
                )
            
            elif system == 'darwin':
                version = platform.mac_ver()[0]
                return RequirementCheck(
                    name="OS",
                    status=CheckStatus.INFO,
                    message=f"macOS {version}",
                    actual_value=f"macOS {version}",
                    severity=Severity.INFO
                )
            
            else:
                return RequirementCheck(
                    name="OS",
                    status=CheckStatus.WARNING,
                    message=f"Unknown OS: {system}",
                    actual_value=system,
                    severity=Severity.WARNING,
                    can_continue=True
                )
                
        except Exception as e:
            return RequirementCheck(
                name="OS",
                status=CheckStatus.WARNING,
                message=f"Could not detect OS: {str(e)}",
                severity=Severity.WARNING,
                can_continue=True
            )
    
    def _detect_linux_distribution(self) -> Tuple[str, str]:
        """
        Detect Linux distribution and version.
        
        Returns:
            Tuple of (distribution_name, version)
        """
        # Try /etc/os-release first (standard)
        if os.path.exists('/etc/os-release'):
            with open('/etc/os-release', 'r') as f:
                content = f.read()
                name_match = re.search(r'NAME="?([^"\n]+)"?', content)
                version_match = re.search(r'VERSION_ID="?([^"\n]+)"?', content)
                
                name = name_match.group(1) if name_match else "Linux"
                version = version_match.group(1) if version_match else "unknown"
                
                # Simplify name (e.g., "Ubuntu 22.04 LTS" -> "Ubuntu")
                name = name.split()[0]
                
                return name, version
        
        # Fallback to lsb_release
        try:
            result = subprocess.run(
                ['lsb_release', '-a'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                output = result.stdout
                name_match = re.search(r'Distributor ID:\s*(.+)', output)
                version_match = re.search(r'Release:\s*(.+)', output)
                
                name = name_match.group(1).strip() if name_match else "Linux"
                version = version_match.group(1).strip() if version_match else "unknown"
                
                return name, version
        except:
            pass
        
        # Final fallback
        return "Linux", "unknown"
    
    def check_architecture(self, supported_architectures: List[str] = None) -> RequirementCheck:
        """
        Check CPU architecture compatibility.
        
        Args:
            supported_architectures: List of supported architectures
            
        Returns:
            RequirementCheck result
        """
        try:
            machine = platform.machine().lower()
            
            # Normalize architecture names
            arch_map = {
                'x86_64': 'x86_64',
                'amd64': 'x86_64',
                'i386': 'x86',
                'i686': 'x86',
                'armv7l': 'armv7',
                'aarch64': 'arm64',
                'arm64': 'arm64',
            }
            
            normalized_arch = arch_map.get(machine, machine)
            
            if not supported_architectures:
                return RequirementCheck(
                    name="Architecture",
                    status=CheckStatus.PASS,
                    message=f"{normalized_arch} (compatible)",
                    actual_value=normalized_arch,
                    severity=Severity.INFO
                )
            
            # Normalize supported architectures
            normalized_supported = [arch_map.get(a.lower(), a.lower()) for a in supported_architectures]
            
            if normalized_arch in normalized_supported:
                return RequirementCheck(
                    name="Architecture",
                    status=CheckStatus.PASS,
                    message=f"{normalized_arch} (compatible)",
                    actual_value=normalized_arch,
                    required_value=', '.join(supported_architectures),
                    severity=Severity.INFO
                )
            else:
                return RequirementCheck(
                    name="Architecture",
                    status=CheckStatus.ERROR,
                    message=f"{normalized_arch} not supported (requires: {', '.join(supported_architectures)})",
                    actual_value=normalized_arch,
                    required_value=', '.join(supported_architectures),
                    severity=Severity.ERROR,
                    can_continue=False,
                    suggestion="This package is not compatible with your CPU architecture"
                )
        except Exception as e:
            return RequirementCheck(
                name="Architecture",
                status=CheckStatus.WARNING,
                message=f"Could not detect architecture: {str(e)}",
                severity=Severity.WARNING,
                can_continue=True
            )
    
    def check_prerequisites(self, required_packages: List[str], optional_packages: List[str] = None) -> List[RequirementCheck]:
        """
        Check for prerequisite packages.
        
        Args:
            required_packages: List of required package names
            optional_packages: List of optional package names
            
        Returns:
            List of RequirementCheck results
        """
        checks = []
        
        for package in required_packages:
            is_installed = self._is_package_installed(package)
            
            if is_installed:
                checks.append(RequirementCheck(
                    name=f"Prerequisite: {package}",
                    status=CheckStatus.PASS,
                    message=f"{package} is installed",
                    severity=Severity.INFO
                ))
            else:
                checks.append(RequirementCheck(
                    name=f"Prerequisite: {package}",
                    status=CheckStatus.ERROR,
                    message=f"{package} is NOT installed (required)",
                    severity=Severity.ERROR,
                    can_continue=False,
                    suggestion=self._get_install_command(package)
                ))
        
        # Check optional packages
        if optional_packages:
            for package in optional_packages:
                is_installed = self._is_package_installed(package)
                
                if not is_installed:
                    checks.append(RequirementCheck(
                        name=f"Optional: {package}",
                        status=CheckStatus.WARNING,
                        message=f"{package} not installed (recommended)",
                        severity=Severity.WARNING,
                        can_continue=True,
                        suggestion=self._get_install_command(package)
                    ))
        
        return checks
    
    def _is_package_installed(self, package: str) -> bool:
        """Check if a package/command is installed."""
        # Check if command exists in PATH
        return shutil.which(package) is not None
    
    def _get_install_command(self, package: str) -> str:
        """Get installation command for a package."""
        if os.path.exists('/usr/bin/apt') or os.path.exists('/usr/bin/apt-get'):
            return f"sudo apt-get install {package}"
        elif os.path.exists('/usr/bin/yum'):
            return f"sudo yum install {package}"
        elif os.path.exists('/usr/bin/dnf'):
            return f"sudo dnf install {package}"
        elif os.path.exists('/usr/bin/pacman'):
            return f"sudo pacman -S {package}"
        else:
            return f"Install {package} using your package manager"
    
    def check_gpu(self, requires_gpu: bool = False) -> RequirementCheck:
        """
        Check for GPU availability.
        
        Args:
            requires_gpu: Whether GPU is required (vs recommended)
            
        Returns:
            RequirementCheck result
        """
        try:
            # Check for NVIDIA GPU
            nvidia_detected = False
            nvidia_info = ""
            
            if shutil.which('nvidia-smi'):
                try:
                    result = subprocess.run(
                        ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        nvidia_detected = True
                        gpu_info = result.stdout.strip().split('\n')[0]
                        nvidia_info = gpu_info
                except:
                    pass
            
            # Check for AMD GPU (ROCm)
            amd_detected = False
            if shutil.which('rocm-smi'):
                try:
                    result = subprocess.run(
                        ['rocm-smi', '--showproductname'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0 and 'GPU' in result.stdout:
                        amd_detected = True
                except:
                    pass
            
            if nvidia_detected:
                return RequirementCheck(
                    name="GPU",
                    status=CheckStatus.PASS,
                    message=f"NVIDIA GPU detected: {nvidia_info}",
                    actual_value=nvidia_info,
                    severity=Severity.INFO
                )
            elif amd_detected:
                return RequirementCheck(
                    name="GPU",
                    status=CheckStatus.PASS,
                    message="AMD GPU detected",
                    actual_value="AMD GPU",
                    severity=Severity.INFO
                )
            else:
                if requires_gpu:
                    return RequirementCheck(
                        name="GPU",
                        status=CheckStatus.ERROR,
                        message="No GPU detected (required for this package)",
                        severity=Severity.ERROR,
                        can_continue=False,
                        suggestion="Install NVIDIA or AMD GPU drivers, or choose CPU-only version"
                    )
                else:
                    return RequirementCheck(
                        name="GPU",
                        status=CheckStatus.WARNING,
                        message="No GPU detected (package works better with GPU acceleration)",
                        severity=Severity.WARNING,
                        can_continue=True,
                        suggestion="Performance may be reduced without GPU"
                    )
        except Exception as e:
            return RequirementCheck(
                name="GPU",
                status=CheckStatus.INFO,
                message=f"Could not detect GPU: {str(e)}",
                severity=Severity.INFO,
                can_continue=True
            )
    
    def check_python_version(self, min_version: Tuple[int, int] = (3, 8)) -> RequirementCheck:
        """
        Check Python version.
        
        Args:
            min_version: Minimum Python version (major, minor)
            
        Returns:
            RequirementCheck result
        """
        try:
            current_version = sys.version_info[:2]
            version_str = f"{current_version[0]}.{current_version[1]}"
            required_str = f"{min_version[0]}.{min_version[1]}"
            
            if current_version >= min_version:
                return RequirementCheck(
                    name="Python Version",
                    status=CheckStatus.PASS,
                    message=f"Python {version_str} (requires {required_str}+)",
                    actual_value=version_str,
                    required_value=f"{required_str}+",
                    severity=Severity.INFO
                )
            else:
                return RequirementCheck(
                    name="Python Version",
                    status=CheckStatus.ERROR,
                    message=f"Python {version_str} (requires {required_str}+ or higher)",
                    actual_value=version_str,
                    required_value=f"{required_str}+",
                    severity=Severity.ERROR,
                    can_continue=False,
                    suggestion=f"Upgrade Python to {required_str} or higher"
                )
        except Exception as e:
            return RequirementCheck(
                name="Python Version",
                status=CheckStatus.WARNING,
                message=f"Could not check Python version: {str(e)}",
                severity=Severity.WARNING,
                can_continue=True
            )
    
    def check_all(self, requirements: PackageRequirements) -> List[RequirementCheck]:
        """
        Run all requirement checks for a package.
        
        Args:
            requirements: Package requirements
            
        Returns:
            List of all check results
        """
        self.checks = []
        
        # Disk space
        disk_check = self.check_disk_space(requirements.min_disk_space_gb)
        self.checks.append(disk_check)
        
        # RAM
        ram_check = self.check_ram(requirements.min_ram_gb, requirements.min_available_ram_gb)
        self.checks.append(ram_check)
        
        # OS
        os_check = self.check_os_compatibility(requirements.supported_os)
        self.checks.append(os_check)
        
        # Architecture
        arch_check = self.check_architecture(requirements.supported_architectures)
        self.checks.append(arch_check)
        
        # Python version
        if requirements.min_python_version:
            python_check = self.check_python_version(requirements.min_python_version)
            self.checks.append(python_check)
        
        # Prerequisites
        if requirements.required_packages or requirements.optional_packages:
            prereq_checks = self.check_prerequisites(
                requirements.required_packages,
                requirements.optional_packages
            )
            self.checks.extend(prereq_checks)
        
        # GPU (if relevant)
        if requirements.requires_gpu or any('gpu' in pkg.lower() or 'cuda' in pkg.lower() 
                                            for pkg in requirements.optional_packages):
            gpu_check = self.check_gpu(requirements.requires_gpu)
            self.checks.append(gpu_check)
        
        # Update status flags
        self.has_errors = any(c.status == CheckStatus.ERROR for c in self.checks)
        self.has_warnings = any(c.status == CheckStatus.WARNING for c in self.checks)
        
        return self.checks
    
    def display_results(self):
        """Display check results to console."""
        if self.json_output:
            self._display_json()
            return
        
        if RICH_AVAILABLE and self.console:
            self._display_rich()
        else:
            self._display_plain()
    
    def _display_plain(self):
        """Display results in plain text."""
        print("\n🔍 Checking system requirements...\n")
        
        for check in self.checks:
            print(str(check))
            if check.suggestion:
                print(f"   💡 {check.suggestion}")
        
        print()
    
    def _display_rich(self):
        """Display results using rich formatting."""
        self.console.print("\n[bold cyan]🔍 Checking system requirements...[/bold cyan]\n")
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Status", width=3)
        table.add_column("Check", ratio=1)
        table.add_column("Result", ratio=2)
        
        for check in self.checks:
            if check.status == CheckStatus.PASS:
                icon = "[green]✅[/green]"
                style = "green"
            elif check.status == CheckStatus.WARNING:
                icon = "[yellow]⚠️[/yellow]"
                style = "yellow"
            elif check.status == CheckStatus.ERROR:
                icon = "[red]❌[/red]"
                style = "red"
            else:
                icon = "[blue]ℹ️[/blue]"
                style = "blue"
            
            table.add_row(icon, f"[bold]{check.name}[/bold]", f"[{style}]{check.message}[/{style}]")
            
            if check.suggestion:
                table.add_row("", "", f"[dim]💡 {check.suggestion}[/dim]")
        
        self.console.print(table)
        self.console.print()
    
    def _display_json(self):
        """Display results as JSON."""
        output = {
            'checks': [
                {
                    'name': c.name,
                    'status': c.status.value,
                    'message': c.message,
                    'actual_value': c.actual_value,
                    'required_value': c.required_value,
                    'severity': c.severity.value,
                    'can_continue': c.can_continue,
                    'suggestion': c.suggestion
                }
                for c in self.checks
            ],
            'has_errors': self.has_errors,
            'has_warnings': self.has_warnings,
            'can_proceed': not self.has_errors or self.force_mode
        }
        print(json.dumps(output, indent=2))
    
    def can_proceed(self) -> bool:
        """
        Check if installation can proceed.
        
        Returns:
            True if no blocking errors or force mode enabled
        """
        if self.force_mode:
            return True
        
        return not self.has_errors
    
    def prompt_continue(self) -> bool:
        """
        Prompt user if they want to continue despite warnings.
        
        Returns:
            True if user wants to continue
        """
        if not self.enable_interactive or self.force_mode:
            return True
        
        if not self.has_warnings:
            return True
        
        try:
            response = input("\nContinue anyway? (y/N): ").strip().lower()
            return response in ('y', 'yes')
        except (EOFError, KeyboardInterrupt):
            return False


def check_requirements(package_name: str, 
                      force: bool = False,
                      json_output: bool = False,
                      custom_requirements: Optional[PackageRequirements] = None) -> bool:
    """
    Check system requirements for a package installation.
    
    Args:
        package_name: Name of package to check
        force: Force installation despite warnings/errors
        json_output: Output as JSON
        custom_requirements: Custom requirements (uses database if None)
        
    Returns:
        True if installation can proceed
    """
    checker = SystemRequirementsChecker(
        force_mode=force,
        json_output=json_output
    )
    
    # Get requirements from database or use custom
    if custom_requirements:
        requirements = custom_requirements
    else:
        requirements = SystemRequirementsChecker.PACKAGE_REQUIREMENTS.get(
            package_name,
            PackageRequirements(package_name=package_name)  # Default requirements
        )
    
    # Run all checks
    checker.check_all(requirements)
    
    # Display results
    checker.display_results()
    
    # Check if can proceed
    if not checker.can_proceed():
        if not json_output:
            if RICH_AVAILABLE:
                console = Console()
                console.print("[red]❌ Cannot proceed: System does not meet minimum requirements[/red]\n")
            else:
                print("❌ Cannot proceed: System does not meet minimum requirements\n")
        return False
    
    # Prompt if warnings
    if checker.has_warnings and not force:
        return checker.prompt_continue()
    
    return True


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Check system requirements for package installation'
    )
    parser.add_argument('package', help='Package name to check requirements for')
    parser.add_argument('--force', action='store_true', help='Skip warnings and continue')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--min-disk', type=float, help='Minimum disk space in GB')
    parser.add_argument('--min-ram', type=float, help='Minimum RAM in GB')
    
    args = parser.parse_args()
    
    # Create custom requirements if specified
    custom_req = None
    if args.min_disk or args.min_ram:
        custom_req = PackageRequirements(
            package_name=args.package,
            min_disk_space_gb=args.min_disk or 1.0,
            min_ram_gb=args.min_ram or 2.0
        )
    
    can_install = check_requirements(
        args.package,
        force=args.force,
        json_output=args.json,
        custom_requirements=custom_req
    )
    
    sys.exit(0 if can_install else 1)


if __name__ == '__main__':
    main()

