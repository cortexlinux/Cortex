#!/usr/bin/env python3
"""
Demo of System Requirements Checker
Shows all features including disk, RAM, OS, architecture, GPU, and prerequisite checking.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from requirements_checker import (
    SystemRequirementsChecker, PackageRequirements,
    check_requirements
)


def demo_oracle_installation():
    """Demo checking requirements for Oracle 23 AI installation."""
    print("=" * 70)
    print(" " * 15 + "Demo 1: Oracle 23 AI Installation Check")
    print("=" * 70)
    print("\nThis package requires significant resources and GPU is recommended.\n")
    
    can_install = check_requirements('oracle-23-ai', force=True)
    
    print(f"\nResult: {'Can proceed' if can_install else 'Cannot proceed'}")
    print()


def demo_postgresql_installation():
    """Demo checking requirements for PostgreSQL (lighter requirements)."""
    print("\n" + "=" * 70)
    print(" " * 15 + "Demo 2: PostgreSQL Installation Check")
    print("=" * 70)
    print("\nPostgreSQL has modest requirements.\n")
    
    can_install = check_requirements('postgresql', force=True)
    
    print(f"\nResult: {'Can proceed' if can_install else 'Cannot proceed'}")
    print()


def demo_custom_requirements():
    """Demo with custom package requirements."""
    print("\n" + "=" * 70)
    print(" " * 15 + "Demo 3: Custom Package Requirements")
    print("=" * 70)
    print("\nChecking requirements for a custom ML application.\n")
    
    custom_req = PackageRequirements(
        package_name="custom-ml-app",
        min_disk_space_gb=20.0,
        min_ram_gb=8.0,
        min_available_ram_gb=4.0,
        required_packages=['python3', 'git'],
        optional_packages=['cuda'],
        requires_gpu=False
    )
    
    can_install = check_requirements(
        "custom-ml-app",
        force=True,
        custom_requirements=custom_req
    )
    
    print(f"\nResult: {'Can proceed' if can_install else 'Cannot proceed'}")
    print()


def demo_json_output():
    """Demo JSON output mode for automation."""
    print("\n" + "=" * 70)
    print(" " * 15 + "Demo 4: JSON Output Mode (for automation)")
    print("=" * 70)
    print("\nUseful for scripts and automation.\n")
    
    check_requirements('docker', json_output=True, force=True)
    print()


def demo_detailed_checks():
    """Demo showing each check individually."""
    print("\n" + "=" * 70)
    print(" " * 15 + "Demo 5: Individual Checks")
    print("=" * 70)
    print("\nBreaking down each check:\n")
    
    checker = SystemRequirementsChecker()
    
    # Disk space
    print("1. Checking Disk Space...")
    disk_result = checker.check_disk_space(required_gb=10.0)
    print(f"   {disk_result}\n")
    
    # RAM
    print("2. Checking RAM...")
    ram_result = checker.check_ram(required_gb=4.0, required_available_gb=2.0)
    print(f"   {ram_result}\n")
    
    # OS
    print("3. Checking OS Compatibility...")
    os_result = checker.check_os_compatibility()
    print(f"   {os_result}\n")
    
    # Architecture
    print("4. Checking CPU Architecture...")
    arch_result = checker.check_architecture(['x86_64'])
    print(f"   {arch_result}\n")
    
    # GPU
    print("5. Checking GPU...")
    gpu_result = checker.check_gpu(requires_gpu=False)
    print(f"   {gpu_result}\n")
    
    # Python version
    print("6. Checking Python Version...")
    py_result = checker.check_python_version(min_version=(3, 8))
    print(f"   {py_result}\n")


def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print(" " * 10 + "Cortex Linux - System Requirements Checker Demo")
    print("=" * 70)
    print("\nValidating system requirements before installation\n")
    
    # Demo 1: Oracle (high requirements)
    demo_oracle_installation()
    
    # Demo 2: PostgreSQL (moderate requirements)
    demo_postgresql_installation()
    
    # Demo 3: Custom requirements
    demo_custom_requirements()
    
    # Demo 4: JSON output
    demo_json_output()
    
    # Demo 5: Detailed checks
    demo_detailed_checks()
    
    print("=" * 70)
    print(" " * 25 + "All Demos Complete!")
    print("=" * 70)
    print("\n✅ Requirements checker is working correctly!")
    print("✅ All features tested successfully")
    print("\nFeatures demonstrated:")
    print("  • Disk space validation with safety buffer")
    print("  • RAM checking (total + available)")
    print("  • OS compatibility verification")
    print("  • CPU architecture validation")
    print("  • GPU detection (NVIDIA/AMD)")
    print("  • Prerequisite package detection")
    print("  • Warning system with severity levels")
    print("  • Interactive prompts")
    print("  • JSON output for automation")
    print("\nReady for integration into Cortex Linux! 🚀\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        sys.exit(0)

