# Package Version Pinning

Pin specific package versions to prevent unwanted updates.

## Overview

The pinning system allows you to lock packages to specific versions, preventing automatic updates that might break your production environment. This is essential for:

- **Production stability**: Keep database servers, web servers, and critical dependencies at tested versions
- **Compatibility**: Ensure Python, Node.js, or other runtimes stay compatible with your code
- **Compliance**: Maintain specific versions for security audits or regulatory requirements

## Quick Start

```bash
# Pin a package to exact version
cortex pin add postgresql@14.10

# Pin to minor version (allows patch updates)
cortex pin add python3@3.11.* --type minor

# List all pins
cortex pin list

# Check if update is blocked
cortex pin check nginx 1.25.0
```

## Commands

### `cortex pin add`

Pin a package to a specific version.

```bash
cortex pin add <package>[@version] [options]

Options:
  --reason, -r    Reason for pinning (stored for documentation)
  --type, -t      Pin type: exact, minor, major, range (default: exact)
  --source, -s    Package source: apt, pip, npm (default: apt)
  --sync-apt      Also run apt-mark hold for system-level protection
```

**Examples:**

```bash
# Pin exact version
cortex pin add postgresql@14.10

# Pin with reason
cortex pin add postgresql@14.10 --reason "Production database"

# Pin minor version (14.* matches 14.0, 14.1, 14.10, etc.)
cortex pin add postgresql@14.* --type minor

# Pin major version
cortex pin add postgresql@14 --type major

# Pin version range
cortex pin add python3@">=3.11,<3.12" --type range

# Pin pip package
cortex pin add flask@2.0.0 --source pip

# Pin npm package
cortex pin add express@4.18.0 --source npm

# Also sync with apt-mark hold
cortex pin add nginx@1.24.0 --sync-apt
```

### `cortex pin remove`

Remove a package pin.

```bash
cortex pin remove <package> [options]

Options:
  --sync-apt      Also run apt-mark unhold
```

**Examples:**

```bash
cortex pin remove postgresql
cortex pin remove nginx --sync-apt
```

### `cortex pin list`

List all pinned packages.

```bash
cortex pin list [options]

Options:
  --source, -s    Filter by source: apt, pip, npm
  --json          Output as JSON
```

**Example Output:**

```
📌 Pinned Packages

  postgresql: 14.10 (apt)
    pinned 5 days ago
    Reason: Production database

  python3: 3.11.* (minor version) (apt)
    pinned 10 days ago
    Reason: ML dependencies require Python 3.11
    ✓ Synced with apt-mark hold

  flask: 2.0.0 (pip)
    pinned today

Total: 3 pinned package(s)
```

### `cortex pin show`

Show detailed information about a pin.

```bash
cortex pin show <package>
```

**Example Output:**

```
📌 Pin Details: postgresql

  Package: postgresql
  Version: 14.10
  Pin Type: exact
  Source: apt
  Pinned At: 2024-12-25T10:30:00
  Age: 5 days
  Reason: Production database - do not upgrade without testing
  Synced with apt: Yes
```

### `cortex pin check`

Check if updating a package to a new version is allowed.

```bash
cortex pin check <package> <version>
```

**Examples:**

```bash
# Check if nginx can be updated
$ cortex pin check nginx 1.25.0
⊘ Update blocked: Package nginx is pinned to 1.24.0
  Use --force flag to override

# Check non-pinned package
$ cortex pin check apache2 2.4.58
✓ Package is not pinned, update allowed
```

### `cortex pin export`

Export pins to a file for backup or sharing.

```bash
cortex pin export [options]

Options:
  --output, -o    Output file (default: pins.json)
```

**Example:**

```bash
cortex pin export --output my-pins.json
```

### `cortex pin import`

Import pins from a file.

```bash
cortex pin import <file> [options]

Options:
  --merge         Merge with existing pins (default)
  --replace       Replace all existing pins
```

**Examples:**

```bash
# Import and merge with existing
cortex pin import pins.json --merge

# Replace all pins
cortex pin import production-pins.json --replace
```

### `cortex pin sync`

Sync all apt pins with system-level `apt-mark hold`.

```bash
cortex pin sync
```

This ensures packages are protected at both Cortex and system levels.

### `cortex pin clear`

Remove all pins.

```bash
cortex pin clear [options]

Options:
  --force, -f     Skip confirmation prompt
```

## Pin Types

### Exact Pin (`--type exact`)

Pins to the exact version specified. No updates allowed unless forced.

```bash
cortex pin add postgresql@14.10
# Only 14.10 is allowed
```

### Minor Pin (`--type minor`)

Allows patch version updates within the same minor version.

```bash
cortex pin add postgresql@14.* --type minor
# Allows: 14.0, 14.1, 14.10, 14.10.1
# Blocks: 15.0, 13.0
```

### Major Pin (`--type major`)

Allows any version within the same major version.

```bash
cortex pin add postgresql@14 --type major
# Allows: 14.0, 14.10, 14.99
# Blocks: 15.0, 13.0
```

### Range Pin (`--type range`)

Uses semver-style constraints for flexible version control.

```bash
cortex pin add python3@">=3.11,<3.12" --type range
# Allows: 3.11.0, 3.11.5, 3.11.10
# Blocks: 3.10.0, 3.12.0

# Other range examples:
cortex pin add node@">=18.0.0" --type range    # 18.0 and above
cortex pin add redis@"<8.0.0" --type range     # Below 8.0
```

## Integration with Install

When you run `cortex install`, the system automatically checks for pinned packages:

```bash
$ cortex install nginx postgresql redis

⚠️  Some packages are pinned:
   ⊘ postgresql (pinned to 14.10)

Use 'cortex pin remove <package>' to unpin, or install will respect pins.
```

## Pin File Format

Pins are stored in `~/.cortex/pins.json`:

```json
{
  "version": "1.0",
  "pins": [
    {
      "package": "postgresql",
      "version": "14.10",
      "pin_type": "exact",
      "source": "apt",
      "pinned_at": "2024-12-25T10:30:00",
      "reason": "Production database",
      "synced_with_apt": true
    }
  ],
  "metadata": {
    "last_modified": "2024-12-25T10:30:00",
    "cortex_version": "0.2.0"
  }
}
```

## Best Practices

### 1. Pin Production-Critical Packages

```bash
# Database servers
cortex pin add postgresql@14.10 --reason "Production DB" --sync-apt
cortex pin add mysql-server@8.0.35 --reason "Production DB"

# Web servers
cortex pin add nginx@1.24.0 --reason "Load balancer"
```

### 2. Use Minor Pins for Runtimes

Allow security patches while preventing major changes:

```bash
cortex pin add python3@3.11.* --type minor --reason "App requires 3.11"
cortex pin add nodejs@20.* --type minor --reason "Frontend build"
```

### 3. Document Your Pins

Always use `--reason` for team communication:

```bash
cortex pin add redis@7.0.0 --reason "Breaking changes in 7.2 - test before upgrade"
```

### 4. Export Before System Changes

```bash
# Before major upgrades
cortex pin export --output pins-backup-$(date +%Y%m%d).json
```

### 5. Sync with apt-mark for Critical Servers

```bash
# Ensure system-level protection
cortex pin sync
```

## Troubleshooting

### Pin not blocking updates?

1. Check pin type matches your needs:
   ```bash
   cortex pin show postgresql
   ```

2. Verify the package name matches exactly:
   ```bash
   cortex pin list --json | grep -i postgres
   ```

### apt-mark sync failed?

Ensure you have sudo permissions:
```bash
sudo cortex pin sync
```

### Corrupted pins file?

Backup and recreate:
```bash
mv ~/.cortex/pins.json ~/.cortex/pins.json.bak
cortex pin add postgresql@14.10  # Recreate needed pins
```

## API Usage

For programmatic access:

```python
from cortex.pin_manager import PinManager, PinType, PackageSource

# Create manager
pin_mgr = PinManager()

# Add pin
success, msg = pin_mgr.add_pin(
    package="postgresql",
    version="14.10",
    reason="Production database",
    pin_type=PinType.EXACT,
    source=PackageSource.APT,
)

# Check if update allowed
result = pin_mgr.check_update_allowed("postgresql", "15.0")
if not result.allowed:
    print(f"Blocked: {result.message}")

# List pins
for pin in pin_mgr.list_pins():
    print(f"{pin.package}: {pin.version}")
```

## Related Commands

- `cortex install` - Install packages (respects pins)
- `cortex history` - View installation history
- `cortex rollback` - Undo installations
