# Netplan Configuration Validator

## Overview

The Netplan Configuration Validator addresses Issue #445 by providing safe, intelligent network configuration management for Netplan/NetworkManager. It prevents network outages from simple YAML typos by validating configurations before applying them.

## Features

✅ **YAML Syntax Validation** - Catches syntax errors before they break networking  
✅ **Semantic Validation** - Validates IP addresses, routes, gateways, and DNS servers  
✅ **Configuration Diff** - Shows exactly what will change  
✅ **Dry-Run Mode** - Apply changes with automatic revert timer for safety  
✅ **Plain English Errors** - User-friendly error messages, not technical jargon  
✅ **Automatic Backups** - Creates timestamped backups before applying changes  

## Installation

The validator is included in Cortex Linux 0.1.0+. No additional installation required.

## Usage

### Validate a Configuration

```bash
# Validate the system's current netplan config
sudo cortex netplan validate

# Validate a specific config file
sudo cortex netplan validate /path/to/config.yaml
```

### Show Configuration Diff

```bash
# Preview changes between current and new configuration
sudo cortex netplan diff --new-config /path/to/new-config.yaml
```

### Apply Configuration (Safe Mode)

```bash
# Apply with confirmation prompt
sudo cortex netplan apply --new-config /path/to/new-config.yaml
```

### Dry-Run with Auto-Revert

```bash
# Apply temporarily with 60-second auto-revert (default)
sudo cortex netplan dry-run --new-config /path/to/new-config.yaml

# Custom timeout (e.g., 120 seconds)
sudo cortex netplan dry-run --new-config /path/to/new-config.yaml --timeout 120
```

## How It Works

### Validation Process

1. **YAML Syntax Check** - Ensures the file is valid YAML
2. **Schema Validation** - Checks for required fields (`network`, `version`)
3. **IP Address Validation** - Validates all IPs and CIDR notation
4. **Route Validation** - Checks route destinations and gateways
5. **Gateway Validation** - Ensures gateways are valid IPs
6. **DNS Validation** - Verifies nameserver addresses

### Dry-Run Mode Safety

When using dry-run mode:

1. Configuration is validated first
2. Backup is created automatically
3. Changes are applied temporarily
4. Network connectivity is tested
5. User has N seconds to confirm (default: 60)
6. If not confirmed, **automatically reverts** to previous config
7. If network fails, **immediately reverts**

This prevents network lockouts from configuration errors.

## Examples

### Example 1: Validate Existing Config

```bash
$ sudo cortex netplan validate

✓ Validation Passed

  ℹ ✓ YAML syntax is valid
  ℹ ✓ Semantic validation passed
```

### Example 2: Detect Invalid IP Address

```yaml
# bad-config.yaml
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - 999.999.999.999/24  # Invalid IP
      gateway4: 192.168.1.1
```

```bash
$ sudo cortex netplan validate bad-config.yaml

✗ Validation Failed

Errors:
  ✗ Interface 'eth0': Invalid IP address '999.999.999.999/24': ...
```

### Example 3: Missing CIDR Notation

```yaml
# config-without-cidr.yaml
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - 192.168.1.100  # Missing /24
```

```bash
$ sudo cortex netplan validate config-without-cidr.yaml

✓ Validation Passed

Warnings:
  ⚠ Interface 'eth0': Address '192.168.1.100' missing CIDR notation (e.g., /24)
```

### Example 4: Preview Changes

```bash
$ sudo cortex netplan diff --new-config new-network.yaml

Configuration Changes:

--- /etc/netplan/01-netcfg.yaml
+++ new-network.yaml
@@ -5,7 +5,7 @@
     eth0:
-      dhcp4: true
+      dhcp4: false
+      addresses:
+        - 192.168.1.100/24
+      gateway4: 192.168.1.1
```

### Example 5: Safe Apply with Auto-Revert

```bash
$ sudo cortex netplan dry-run --new-config new-network.yaml

┌─────────────────────────────────────┐
│ ⚠️  Safety Mode                     │
│                                     │
│ DRY-RUN MODE                        │
│                                     │
│ Configuration will be applied       │
│ temporarily.                        │
│ You have 60 seconds to confirm the  │
│ changes.                            │
│ If not confirmed, configuration     │
│ will auto-revert.                   │
└─────────────────────────────────────┘

Configuration Changes:
[... diff output ...]

✓ Configuration applied
✓ Network is working

Press 'y' to keep changes, or wait 60s to auto-revert
Reverting in 60 seconds...
```

## Configuration File Format

Netplan uses YAML configuration files located in `/etc/netplan/`.

### Basic Ethernet with DHCP

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: true
```

### Static IP Configuration

```yaml
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - 192.168.1.100/24
      gateway4: 192.168.1.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
```

### Multiple Interfaces

```yaml
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
    eth1:
      addresses:
        - 10.0.0.1/24
      routes:
        - to: 0.0.0.0/0
          via: 10.0.0.254
```

### WiFi Configuration

```yaml
network:
  version: 2
  wifis:
    wlan0:
      dhcp4: true
      access-points:
        "MyWiFiNetwork":
          password: "SecurePassword123"
```

## Validation Rules

### YAML Syntax
- Must be valid YAML (no tabs, proper indentation)
- Must not be empty

### Network Configuration
- Must have `network` key
- Recommended to have `version: 2`

### Interface Names
- Must contain only alphanumeric, dash, or underscore characters
- Examples: `eth0`, `wlan0`, `enp3s0`, `br-lan`

### IP Addresses
- IPv4: `192.168.1.1` or `192.168.1.0/24`
- IPv6: `2001:db8::1` or `2001:db8::/32`
- Static IPs should include CIDR notation

### Routes
- Must have `to` field (destination network)
- Must have `via` field (gateway IP)
- Both must be valid IP addresses

### Gateways
- Must be valid IP addresses (no CIDR)
- `gateway4` for IPv4
- `gateway6` for IPv6

### DNS Servers
- Must be valid IP addresses
- Specified in `nameservers.addresses` list

## Common Errors & Solutions

### Error: "YAML syntax error"

**Cause**: Invalid YAML format (often tabs instead of spaces)

**Solution**: Use spaces for indentation, not tabs

```yaml
# ❌ Bad (tabs)
network:
	version: 2

# ✓ Good (spaces)
network:
  version: 2
```

### Error: "Invalid IP address"

**Cause**: IP address format is incorrect

**Solution**: Check IP format and CIDR notation

```yaml
# ❌ Bad
addresses:
  - 999.999.999.999/24
  - 192.168.1.1

# ✓ Good
addresses:
  - 192.168.1.100/24
  - 10.0.0.1/24
```

### Warning: "Missing CIDR notation"

**Cause**: Static IP without subnet mask

**Solution**: Add CIDR notation

```yaml
# ⚠ Warning
addresses:
  - 192.168.1.100

# ✓ Better
addresses:
  - 192.168.1.100/24
```

### Error: "Route missing required 'to' field"

**Cause**: Route configuration incomplete

**Solution**: Include both `to` and `via`

```yaml
# ❌ Bad
routes:
  - via: 192.168.1.1

# ✓ Good
routes:
  - to: 0.0.0.0/0
    via: 192.168.1.1
```

## Safety Features

### Automatic Backups

All applied configurations are backed up to `~/.cortex/netplan_backups/` with timestamps:

```
~/.cortex/netplan_backups/
  └── 01-netcfg_20260117_143022.yaml
  └── 01-netcfg_20260117_151530.yaml
```

### Connectivity Testing

Dry-run mode tests connectivity by pinging:
- 8.8.8.8 (Google DNS)
- 1.1.1.1 (Cloudflare DNS)

If both fail, configuration is **immediately reverted**.

### Auto-Revert Timer

Default 60-second countdown allows you to:
1. Test network connectivity
2. Verify services are working
3. Confirm or revert changes

## Python API

You can also use the validator programmatically:

```python
from cortex.netplan_validator import NetplanValidator

# Create validator instance
validator = NetplanValidator("/etc/netplan/01-netcfg.yaml")

# Validate configuration
result = validator.validate_file()
if result.is_valid:
    print("Configuration is valid!")
else:
    print("Errors found:")
    for error in result.errors:
        print(f"  - {error}")

# Generate diff
validator.show_diff("/path/to/new-config.yaml")

# Apply with dry-run
confirmed = validator.dry_run_with_revert("/path/to/new-config.yaml", timeout=60)
```

## Testing

Run the test suite:

```bash
pytest tests/test_netplan_validator.py -v
```

With coverage:

```bash
pytest tests/test_netplan_validator.py --cov=cortex.netplan_validator --cov-report=term-missing
```

## Known Limitations

1. **Requires sudo** - Network configuration changes require root privileges
2. **Netplan only** - Currently supports Netplan, not direct NetworkManager config
3. **Single file** - Validates one config file at a time
4. **Basic validation** - Doesn't validate advanced features like VLANs, bonds, etc.

## Future Enhancements

- [ ] Support for NetworkManager native config
- [ ] Advanced network feature validation (VLANs, bridges, bonds)
- [ ] Integration with `networkctl` for systemd-networkd
- [ ] Web UI for configuration management
- [ ] Configuration templates for common setups

## Troubleshooting

### "Permission denied" error

Run with `sudo`:

```bash
sudo cortex netplan validate
```

### "Netplan directory not found"

Netplan is not installed or not configured. Install with:

```bash
sudo apt install netplan.io
```

### "No .yaml files found"

No netplan configuration exists. Create one:

```bash
sudo nano /etc/netplan/01-netcfg.yaml
```

### Changes don't apply

1. Check validation errors with `cortex netplan validate`
2. Verify you used `sudo`
3. Check `/var/log/syslog` for netplan errors


