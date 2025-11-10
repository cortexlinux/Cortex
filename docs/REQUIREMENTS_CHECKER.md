# System Requirements Pre-flight Checker

## Overview

The System Requirements Checker validates that your system meets all necessary requirements before package installation begins, preventing installation failures and providing clear guidance.

## Features

- ✅ **Disk Space Checking** - Validates available disk space with configurable safety buffer
- ✅ **RAM Validation** - Checks total and available memory
- ✅ **OS Compatibility** - Verifies OS version against compatibility matrix
- ✅ **Architecture Detection** - Validates CPU architecture (x86_64, ARM, etc.)
- ✅ **Prerequisite Validation** - Detects required and optional packages
- ✅ **GPU Detection** - Identifies NVIDIA/AMD GPUs and CUDA/ROCm
- ✅ **Warning System** - Severity-based messages (INFO/WARNING/ERROR)
- ✅ **Interactive Prompts** - User confirmation for warnings
- ✅ **Force Mode** - Override warnings and continue
- ✅ **JSON Output** - Machine-readable output for automation

## Installation

The requirements checker uses Python standard library plus optional dependencies:

```bash
# Optional (recommended)
pip install psutil rich

# Or from requirements.txt
pip install -r requirements.txt
```

## Quick Start

### Command Line Usage

```bash
# Check requirements for a package
python requirements_checker.py oracle-23-ai

# Force installation despite warnings
python requirements_checker.py oracle-23-ai --force

# Get JSON output
python requirements_checker.py oracle-23-ai --json

# Custom requirements
python requirements_checker.py my-package --min-disk 50 --min-ram 16
```

### Programmatic Usage

```python
from requirements_checker import check_requirements, PackageRequirements

# Simple check
can_install = check_requirements('postgresql')

if can_install:
    print("System meets requirements!")
else:
    print("System does not meet requirements.")

# Custom requirements
custom_req = PackageRequirements(
    package_name="my-app",
    min_disk_space_gb=20.0,
    min_ram_gb=8.0,
    required_packages=['gcc', 'python3'],
    optional_packages=['cuda']
)

can_install = check_requirements(
    "my-app",
    custom_requirements=custom_req
)
```

## Example Output

### Successful Check

```
🔍 Checking system requirements...

 ✅   Disk Space     140.2GB available (30.0GB required)
 ✅   RAM            63.7GB total (42.9GB available, 8.0GB required)
 ✅   OS             Ubuntu 24.04 LTS (supported)
 ✅   Architecture   x86_64 (compatible)
 ✅   GPU            NVIDIA GPU detected: NVIDIA GeForce RTX 3050, 4096 MiB
```

### With Warnings

```
🔍 Checking system requirements...

 ✅   Disk Space       45.2GB available (30.0GB required)
 ✅   RAM              16.0GB total (8.5GB available, 8.0GB required)
 ✅   OS               Ubuntu 22.04 LTS (supported)
 ✅   Architecture     x86_64 (compatible)
 ❌   Prerequisite: gcc  gcc is NOT installed (required)
                       💡 sudo apt-get install gcc
 ⚠️    GPU              No GPU detected (package works better with GPU acceleration)
                       💡 Performance may be reduced without GPU

❌ Cannot proceed: System does not meet minimum requirements
```

### Interactive Mode

```
🔍 Checking system requirements...

 ✅   Disk Space     100GB available (30GB required)
 ✅   RAM            32GB total (16GB available, 8GB required)
 ✅   OS             Ubuntu 24.04 LTS (supported)
 ✅   Architecture   x86_64 (compatible)
 ⚠️    GPU            No GPU detected (package works better with GPU acceleration)
                     💡 Performance may be reduced without GPU

Continue anyway? (y/N): _
```

## API Reference

### SystemRequirementsChecker

Main class for validating system requirements.

#### Constructor

```python
SystemRequirementsChecker(
    disk_buffer_percent: float = 20.0,
    enable_interactive: bool = True,
    force_mode: bool = False,
    json_output: bool = False,
    console: Optional[Console] = None
)
```

**Parameters:**
- `disk_buffer_percent`: Safety buffer for disk space (default 20%)
- `enable_interactive`: Enable interactive prompts for warnings
- `force_mode`: Skip all warnings and continue
- `json_output`: Output results as JSON
- `console`: Rich Console instance (auto-created if None)

#### Methods

##### check_disk_space(required_gb: float, path: str = '/') -> RequirementCheck

Check available disk space.

```python
checker = SystemRequirementsChecker()
result = checker.check_disk_space(required_gb=30.0)

if result.status == CheckStatus.PASS:
    print("Sufficient disk space!")
```

##### check_ram(required_gb: float, required_available_gb: float = 1.0) -> RequirementCheck

Check total and available RAM.

```python
result = checker.check_ram(required_gb=8.0, required_available_gb=4.0)
```

##### check_os_compatibility(supported_os: List[str] = None) -> RequirementCheck

Check OS version compatibility.

```python
result = checker.check_os_compatibility(['ubuntu', 'debian'])
```

##### check_architecture(supported_architectures: List[str] = None) -> RequirementCheck

Check CPU architecture.

```python
result = checker.check_architecture(['x86_64', 'amd64'])
```

##### check_prerequisites(required_packages: List[str], optional_packages: List[str] = None) -> List[RequirementCheck]

Check for prerequisite packages.

```python
results = checker.check_prerequisites(
    required_packages=['gcc', 'make'],
    optional_packages=['cuda']
)
```

##### check_gpu(requires_gpu: bool = False) -> RequirementCheck

Check for GPU availability.

```python
# GPU recommended but not required
result = checker.check_gpu(requires_gpu=False)

# GPU required
result = checker.check_gpu(requires_gpu=True)
```

##### check_python_version(min_version: Tuple[int, int] = (3, 8)) -> RequirementCheck

Check Python version.

```python
result = checker.check_python_version(min_version=(3, 9))
```

##### check_all(requirements: PackageRequirements) -> List[RequirementCheck]

Run all requirement checks for a package.

```python
requirements = PackageRequirements(
    package_name="oracle-23-ai",
    min_disk_space_gb=30.0,
    min_ram_gb=8.0,
    required_packages=['gcc', 'make']
)

results = checker.check_all(requirements)
```

##### display_results()

Display check results to console.

```python
checker.display_results()
```

##### can_proceed() -> bool

Check if installation can proceed.

```python
if checker.can_proceed():
    # Start installation
    pass
```

##### prompt_continue() -> bool

Prompt user to continue despite warnings.

```python
if checker.prompt_continue():
    # User agreed to continue
    pass
```

### PackageRequirements

Dataclass defining package requirements.

```python
PackageRequirements(
    package_name: str,
    min_disk_space_gb: float = 1.0,
    min_ram_gb: float = 2.0,
    min_available_ram_gb: float = 1.0,
    supported_os: List[str] = ["ubuntu", "debian", ...],
    supported_architectures: List[str] = ["x86_64", "amd64"],
    required_packages: List[str] = [],
    optional_packages: List[str] = [],
    requires_gpu: bool = False,
    min_python_version: Optional[Tuple[int, int]] = None
)
```

## Advanced Usage

### Custom Requirements

```python
from requirements_checker import SystemRequirementsChecker, PackageRequirements

# Define custom requirements
my_requirements = PackageRequirements(
    package_name="my-ml-app",
    min_disk_space_gb=50.0,
    min_ram_gb=16.0,
    min_available_ram_gb=8.0,
    supported_os=['ubuntu', 'debian'],
    supported_architectures=['x86_64'],
    required_packages=['gcc', 'python3', 'python3-pip'],
    optional_packages=['cuda', 'cudnn'],
    requires_gpu=True,
    min_python_version=(3, 9)
)

# Run checks
checker = SystemRequirementsChecker()
results = checker.check_all(my_requirements)
checker.display_results()

if checker.can_proceed():
    if checker.prompt_continue():
        # Proceed with installation
        pass
```

### Automation Mode (JSON Output)

```python
import json
from requirements_checker import check_requirements

# Get results as JSON
can_install = check_requirements('postgresql', json_output=True)

# Parse stdout to get detailed results
# Output includes: checks, has_errors, has_warnings, can_proceed
```

### Integration with Installation Workflow

```python
from requirements_checker import check_requirements, PackageRequirements

async def safe_install_package(package_name: str):
    """Install package with pre-flight checks."""
    
    # Define or load requirements
    requirements = PackageRequirements(package_name=package_name)
    
    # Check requirements
    can_install = check_requirements(package_name)
    
    if not can_install:
        print("Installation aborted due to requirement checks")
        return False
    
    # Proceed with installation
    # ... your installation code here ...
    
    return True
```

## Configuration

### Disk Buffer

Adjust the safety buffer for disk space:

```python
# Default 20% buffer
checker = SystemRequirementsChecker(disk_buffer_percent=20.0)

# More conservative 30% buffer
checker = SystemRequirementsChecker(disk_buffer_percent=30.0)

# No buffer (use exact requirement)
checker = SystemRequirementsChecker(disk_buffer_percent=0.0)
```

### Non-Interactive Mode

```python
# Disable user prompts (for automation)
checker = SystemRequirementsChecker(enable_interactive=False)
```

### Force Mode

```python
# Override all warnings and errors
checker = SystemRequirementsChecker(force_mode=True)
```

## Supported Operating Systems

The checker maintains a compatibility matrix for common OSes:

- **Ubuntu**: 20.04, 22.04, 24.04
- **Debian**: 10, 11, 12
- **Fedora**: 37, 38, 39, 40
- **CentOS/RHEL**: 7, 8, 9
- **Arch Linux**: rolling

Packages can specify their supported OSes:

```python
PackageRequirements(
    supported_os=['ubuntu', 'debian']  # Only these OSes
)
```

## GPU Detection

### NVIDIA GPUs

Detected via `nvidia-smi`:

```bash
# Example output
✅ GPU: NVIDIA GPU detected: NVIDIA GeForce RTX 3050, 4096 MiB
```

### AMD GPUs

Detected via `rocm-smi`:

```bash
✅ GPU: AMD GPU detected
```

### No GPU

```bash
⚠️  GPU: No GPU detected (package works better with GPU acceleration)
   💡 Performance may be reduced without GPU
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest test_requirements_checker.py -v

# With coverage
pytest test_requirements_checker.py --cov=requirements_checker --cov-report=html

# Specific test class
pytest test_requirements_checker.py::TestSystemRequirementsChecker -v
```

**Test Coverage**: 47 comprehensive tests covering all features

## Error Messages

The checker provides actionable error messages:

### Disk Space

```
❌ Disk Space: Insufficient disk space: 5.0GB available, 30.0GB required
   💡 Free up at least 25.0GB of disk space
```

### RAM

```
❌ RAM: 4.0GB total RAM (minimum 8.0GB required)
   💡 Upgrade system RAM or choose a lighter package
```

### Prerequisites

```
❌ Prerequisite: gcc - gcc is NOT installed (required)
   💡 sudo apt-get install gcc
```

### Architecture

```
❌ Architecture: armv7 not supported (requires: x86_64, amd64)
   💡 This package is not compatible with your CPU architecture
```

## Exit Codes

When used as CLI:
- `0`: Requirements met, can proceed
- `1`: Requirements not met or user cancelled

## Requirements Database

Pre-configured requirements for common packages:

```python
PACKAGE_REQUIREMENTS = {
    'oracle-23-ai': ...,    # 30GB disk, 8GB RAM, requires gcc/make
    'postgresql': ...,      # 2GB disk, 2GB RAM
    'docker': ...,          # 10GB disk, 4GB RAM, requires curl
}
```

Add your own:

```python
SystemRequirementsChecker.PACKAGE_REQUIREMENTS['my-package'] = PackageRequirements(...)
```

## Troubleshooting

### psutil not available

**Symptom**: Warnings about being unable to check disk/RAM

**Solution**:
```bash
pip install psutil
```

The checker works without psutil but provides less accurate results.

### GPU not detected despite having GPU

**Check**:
```bash
# For NVIDIA
nvidia-smi

# For AMD
rocm-smi
```

Ensure GPU drivers and tools are installed.

### False positive on prerequisites

The checker looks for commands in PATH. If you have a package installed but not in PATH, it may show as missing.

**Workaround**: Use `--force` flag or add to PATH

## Performance

- **Execution Time**: <1 second for all checks
- **Memory Usage**: <10MB
- **CPU Usage**: Negligible

## Cross-Platform Support

- ✅ **Linux** - Full support with all features
- ✅ **Windows** - Full support (uses ctypes for system info)
- ✅ **macOS** - Full support

## License

MIT License - See LICENSE file for details

## Contributing

See the main CONTRIBUTING.md for guidelines.

## Support

For issues and questions:
- GitHub Issues: https://github.com/cortexlinux/cortex/issues
- Discord: https://discord.gg/uCqHvxjU83

