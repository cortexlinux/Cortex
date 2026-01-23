#!/bin/bash
# Test script for Netplan Validator
# Demonstrates all features of the netplan validator

set -e

echo "====================================="
echo "Netplan Validator Test Script"
echo "====================================="
echo

# Create test directory
TEST_DIR="/tmp/cortex_netplan_test_$$"
mkdir -p "$TEST_DIR"
echo "Created test directory: $TEST_DIR"
echo

# Create a valid config
echo "Creating valid configuration..."
cat > "$TEST_DIR/valid-config.yaml" << 'EOF'
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: true
    eth1:
      addresses:
        - 192.168.1.100/24
      gateway4: 192.168.1.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
EOF

# Create a config with invalid YAML
echo "Creating invalid YAML configuration..."
cat > "$TEST_DIR/invalid-yaml.yaml" << 'EOF'
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
    invalid indentation here
EOF

# Create a config with invalid IPs
echo "Creating configuration with invalid IPs..."
cat > "$TEST_DIR/invalid-ips.yaml" << 'EOF'
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - 999.999.999.999/24
      gateway4: invalid.ip.address
      nameservers:
        addresses:
          - 8.8.8.8.8
EOF

# Create a config without CIDR
echo "Creating configuration without CIDR notation..."
cat > "$TEST_DIR/no-cidr.yaml" << 'EOF'
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - 192.168.1.100
      gateway4: 192.168.1.1
EOF

# Create a modified config for diff testing
echo "Creating modified configuration..."
cat > "$TEST_DIR/modified-config.yaml" << 'EOF'
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: false
      addresses:
        - 10.0.0.100/24
      gateway4: 10.0.0.1
    eth1:
      addresses:
        - 192.168.1.100/24
      gateway4: 192.168.1.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
EOF

echo "Test configurations created in $TEST_DIR"
echo

# Run tests
echo "====================================="
echo "Test 1: Validate valid configuration"
echo "====================================="
cortex netplan validate "$TEST_DIR/valid-config.yaml"
echo

echo "====================================="
echo "Test 2: Validate invalid YAML"
echo "====================================="
cortex netplan validate "$TEST_DIR/invalid-yaml.yaml" || true
echo

echo "====================================="
echo "Test 3: Validate invalid IPs"
echo "====================================="
cortex netplan validate "$TEST_DIR/invalid-ips.yaml" || true
echo

echo "====================================="
echo "Test 4: Validate config without CIDR"
echo "====================================="
cortex netplan validate "$TEST_DIR/no-cidr.yaml"
echo

echo "====================================="
echo "Test 5: Show diff between configs"
echo "====================================="
cortex netplan diff "$TEST_DIR/valid-config.yaml" --new-config "$TEST_DIR/modified-config.yaml" || true
echo

echo "====================================="
echo "All tests completed!"
echo "====================================="
echo
echo "Test files are in: $TEST_DIR"
echo "To clean up: rm -rf $TEST_DIR"
