# Tarball/Source Build Helper

Build software from source tarballs with automatic dependency detection and tracking.

## Overview

The tarball helper analyzes source directories to detect build systems and dependencies, installs required development packages, and tracks manual installations for easy cleanup. It supports:

- Automatic build system detection (CMake, Autotools, Meson, Make, Python)
- Dependency extraction from build configuration files
- Missing package identification and installation
- Manual installation tracking and cleanup
- Packaged alternative suggestions

## Quick Start

```bash
# Analyze a source directory
$ cortex tarball analyze ./nginx-1.25.3
Build System: autotools
Dependencies:
  - zlib.h (header) → zlib1g-dev ✓ Found
  - openssl (pkg-config) → libssl-dev ✗ Missing
  - pcre.h (header) → libpcre3-dev ✗ Missing

Missing packages to install:
  sudo apt install libssl-dev libpcre3-dev

Build commands:
  ./configure
  make -j$(nproc)
  sudo make install

# Install missing dependencies
$ cortex tarball install-deps ./nginx-1.25.3
Installing 2 packages...
✓ All packages installed

# Track the installation
$ cortex tarball track nginx ./nginx-1.25.3 --packages libssl-dev,libpcre3-dev
✓ Tracked installation: nginx

# List tracked installations
$ cortex tarball list
Name    Installed At          Packages  Prefix
nginx   2024-01-15T10:30:00   2         /usr/local

# Clean up later
$ cortex tarball cleanup nginx
Remove 2 packages that were installed for this build? [Y/n]: y
✓ Removed 'nginx' from tracking
```

## Commands

### `cortex tarball analyze <source_dir>`

Analyze a source directory to detect build system and dependencies.

```bash
cortex tarball analyze ./nginx-1.25.3
cortex tarball analyze ~/src/myproject
```

Output includes:
- Detected build system
- Packaged alternatives (if available)
- Dependencies table with installation status
- Missing packages to install
- Suggested build commands

### `cortex tarball install-deps <source_dir>`

Install missing dependencies for building from source.

```bash
cortex tarball install-deps ./nginx-1.25.3
cortex tarball install-deps ./nginx-1.25.3 --dry-run
```

Options:
- `--dry-run`: Show what would be installed without executing

### `cortex tarball track <name> <source_dir>`

Track a manual installation for later cleanup.

```bash
cortex tarball track nginx ./nginx-1.25.3
cortex tarball track nginx ./nginx-1.25.3 --packages libssl-dev,libpcre3-dev
```

Options:
- `--packages`: Comma-separated list of apt packages installed for this build

### `cortex tarball list`

List all tracked manual installations.

```bash
cortex tarball list
```

### `cortex tarball cleanup <name>`

Remove a tracked manual installation and optionally uninstall packages.

```bash
cortex tarball cleanup nginx
cortex tarball cleanup nginx --dry-run
```

Options:
- `--dry-run`: Show what would be removed without executing

## Supported Build Systems

| Build System | Detection Files | Dependency Sources |
|--------------|-----------------|-------------------|
| CMake | `CMakeLists.txt` | `find_package()`, `pkg_check_modules()`, `CHECK_INCLUDE_FILE()` |
| Autotools | `configure.ac`, `configure.in`, `configure` | `AC_CHECK_HEADERS`, `PKG_CHECK_MODULES`, `AC_CHECK_LIB` |
| Meson | `meson.build` | `dependency()` |
| Make | `Makefile` | Manual analysis required |
| Python | `setup.py`, `pyproject.toml` | Adds `python3-dev`, `python3-pip` |

## Build Commands by System

### CMake

```bash
mkdir -p build && cd build
cmake ..
make -j$(nproc)
sudo make install
```

### Autotools

```bash
# If configure.ac exists but not configure:
autoreconf -fi

./configure
make -j$(nproc)
sudo make install
```

### Meson

```bash
meson setup build
ninja -C build
sudo ninja -C build install
```

### Python

```bash
pip install .
```

## Dependency Mappings

The helper includes mappings for common dependencies:

### Headers to Packages

| Header | Apt Package |
|--------|-------------|
| `zlib.h` | `zlib1g-dev` |
| `openssl/ssl.h` | `libssl-dev` |
| `curl/curl.h` | `libcurl4-openssl-dev` |
| `sqlite3.h` | `libsqlite3-dev` |
| `png.h` | `libpng-dev` |
| `ncurses.h` | `libncurses-dev` |
| `readline/readline.h` | `libreadline-dev` |

### pkg-config to Packages

| pkg-config Name | Apt Package |
|-----------------|-------------|
| `openssl` | `libssl-dev` |
| `libcurl` | `libcurl4-openssl-dev` |
| `zlib` | `zlib1g-dev` |
| `glib-2.0` | `libglib2.0-dev` |
| `gtk+-3.0` | `libgtk-3-dev` |
| `sqlite3` | `libsqlite3-dev` |

### Build Tools

| Tool | Apt Package |
|------|-------------|
| `gcc`, `g++`, `make` | `build-essential` |
| `cmake` | `cmake` |
| `meson` | `meson` |
| `ninja` | `ninja-build` |
| `autoconf` | `autoconf` |
| `automake` | `automake` |
| `pkg-config` | `pkg-config` |

## Data Storage

Installation history is stored in `~/.cortex/manual_builds.json`:

```json
{
  "nginx": {
    "source_dir": "/home/user/src/nginx-1.25.3",
    "installed_at": "2024-01-15T10:30:00",
    "packages_installed": ["libssl-dev", "libpcre3-dev"],
    "files_installed": [],
    "prefix": "/usr/local"
  }
}
```

## Workflow Example

### Building nginx from Source

```bash
# Download and extract
wget https://nginx.org/download/nginx-1.25.3.tar.gz
tar xzf nginx-1.25.3.tar.gz
cd nginx-1.25.3

# Analyze dependencies
cortex tarball analyze .

# Note: Cortex suggests packaged alternative
# Consider: sudo apt install nginx

# If you still want to build from source:
cortex tarball install-deps .

# Build
./configure --prefix=/usr/local
make -j$(nproc)
sudo make install

# Track the installation
cortex tarball track nginx . --packages libssl-dev,libpcre3-dev,zlib1g-dev

# Later, clean up
cortex tarball cleanup nginx
```

## Limitations

- Dependency detection relies on pattern matching in build files
- Some complex or custom build systems may not be fully detected
- Package mappings cover common libraries but not all possible dependencies
- Manual inspection of build output may be needed for uncommon dependencies

## Troubleshooting

### Missing dependency not detected

If a build fails due to a missing dependency that wasn't detected:

1. Check the build error for the missing header or library
2. Search for the apt package: `apt-cache search <name>`
3. Install manually and track: `cortex tarball track <name> . --packages <pkg>`

### Build system not detected

If the build system shows as "unknown":

1. Check if build files exist in the source directory
2. Some projects may use non-standard build configurations
3. Manually run the appropriate build commands

### Package alternative suggested but outdated

The packaged version may be older than the source you're building:

```bash
# Check packaged version
apt-cache policy nginx

# Compare with source version
# If source is newer, proceed with manual build
```
