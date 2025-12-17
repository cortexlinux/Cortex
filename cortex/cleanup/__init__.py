"""
Cleanup module for Cortex.

This module provides disk cleanup functionality including:
- Scanning for cleanup opportunities (package cache, orphaned packages, temp files, logs)
- Executing cleanup operations with undo capability
- Managing quarantined files for safe recovery
- Scheduling automatic cleanup tasks
"""

from cortex.cleanup.cleaner import DiskCleaner
from cortex.cleanup.manager import CleanupManager, QuarantineItem
from cortex.cleanup.scanner import CleanupScanner, ScanResult

__all__ = [
    "CleanupScanner",
    "ScanResult",
    "DiskCleaner",
    "CleanupManager",
    "QuarantineItem",
]
