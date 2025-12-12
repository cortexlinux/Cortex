
import os
import sys
import shutil
import subprocess
import glob
import gzip
import time
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cortex.packages import PackageManager
from cortex.installation_history import InstallationHistory, InstallationType, InstallationStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CleanupOpportunity:
    type: str  # 'package_cache', 'orphans', 'logs', 'temp'
    size_bytes: int
    description: str
    items: List[str]  # List of files or packages

class DiskOptimizer:
    def __init__(self):
        self.pm = PackageManager()
        self.history = InstallationHistory()
        self.backup_dir = Path("/var/lib/cortex/backups/cleanup")
        self._ensure_backup_dir()

    def _ensure_backup_dir(self):
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self.backup_dir = Path.home() / ".cortex" / "backups" / "cleanup"
            self.backup_dir.mkdir(parents=True, exist_ok=True)

    def scan(self) -> List[CleanupOpportunity]:
        """Scan system for cleanup opportunities"""
        opportunities = []
        
        # 1. Package Manager Cleanup
        pkg_info = self.pm.get_cleanable_items()
        
        if pkg_info.get("cache_size_bytes", 0) > 0:
            opportunities.append(CleanupOpportunity(
                type="package_cache",
                size_bytes=pkg_info["cache_size_bytes"],
                description="Package manager cache",
                items=["Package cache files"]
            ))
            
        if pkg_info.get("orphaned_packages"):
            opportunities.append(CleanupOpportunity(
                type="orphans",
                size_bytes=pkg_info.get("orphaned_size_bytes", 0),
                description=f"Orphaned packages ({len(pkg_info['orphaned_packages'])})",
                items=pkg_info["orphaned_packages"]
            ))

        # 2. Old Logs
        log_opp = self._scan_logs()
        if log_opp:
            opportunities.append(log_opp)
            
        # 3. Temp Files
        temp_opp = self._scan_temp_files()
        if temp_opp:
            opportunities.append(temp_opp)
            
        return opportunities

    def _scan_logs(self) -> Optional[CleanupOpportunity]:
        """Scan for rotatable/compressible logs"""
        log_dir = "/var/log"
        if not os.path.exists(log_dir):
            return None
            
        candidates = []
        total_size = 0
        
        # Look for .1, .2, or .log.old files that aren't compressed
        patterns = ["**/*.1", "**/*.2", "**/*.log.old"]
        for pattern in patterns:
            for log_file in glob.glob(os.path.join(log_dir, pattern), recursive=True):
                try:
                    size = os.path.getsize(log_file)
                    # Helper to skip if looks like binary/compressed
                    if not log_file.endswith('.gz'):
                        candidates.append(log_file)
                        total_size += size
                except (OSError, PermissionError):
                    pass
        
        if candidates:
            return CleanupOpportunity(
                type="logs",
                size_bytes=total_size,
                description=f"Old log files ({len(candidates)})",
                items=candidates
            )
        return None

    def _scan_temp_files(self) -> Optional[CleanupOpportunity]:
        """Scan for old temp files"""
        temp_dirs = ["/tmp", "/var/tmp"]
        candidates = []
        total_size = 0
        # Files older than 7 days
        cutoff = time.time() - (7 * 86400)
        
        for d in temp_dirs:
            if not os.path.exists(d):
                continue
            try:
                for root, _, files in os.walk(d):
                    for name in files:
                        fpath = os.path.join(root, name)
                        try:
                            stat = os.stat(fpath)
                            if stat.st_atime < cutoff and stat.st_mtime < cutoff:
                                candidates.append(fpath)
                                total_size += stat.st_size
                        except (OSError, PermissionError):
                            pass
            except (OSError, PermissionError):
                pass
                
        if candidates:
            return CleanupOpportunity(
                type="temp",
                size_bytes=total_size,
                description=f"Old temporary files ({len(candidates)})",
                items=candidates
            )
        return None

    def run_cleanup(self, opportunities: List[CleanupOpportunity], safe: bool = True) -> Dict[str, any]:
        """Execute cleanup for given opportunities"""
        results = {
            "freed_bytes": 0,
            "actions": [],
            "errors": []
        }
        
        # Create a cleanup session ID for potential rollback
        cleanup_id = f"cleanup_{int(time.time())}"
        session_backup_dir = self.backup_dir / cleanup_id
        if safe:
            session_backup_dir.mkdir(parents=True, exist_ok=True)
        
        for opp in opportunities:
            try:
                if opp.type == "package_cache":
                    cmds = self.pm.get_cleanup_commands("cache")
                    for cmd in cmds:
                        # Prepend sudo if likely needed and not running as root
                        if os.geteuid() != 0 and not cmd.startswith("sudo"):
                            cmd = f"sudo {cmd}"
                        
                        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                        if proc.returncode == 0:
                            results["freed_bytes"] += opp.size_bytes
                            results["actions"].append(f"Cleaned package cache")
                        else:
                            results["errors"].append(f"Failed to clean cache: {proc.stderr}")
                
                elif opp.type == "orphans":
                    cmds = self.pm.get_cleanup_commands("orphans")
                    # For orphans, we should record this as a removal op in InstallationHistory for Undo
                    # But standard history tracks 'install' primarily. We'll use a custom record.
                    if safe:
                         # Snapshot current packages before removal
                        pass # InstallationHistory handles this if we use record_installation

                    for cmd in cmds:
                        if os.geteuid() != 0 and not cmd.startswith("sudo"):
                            cmd = f"sudo {cmd}"
                        
                        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                        if proc.returncode == 0:
                            results["freed_bytes"] += opp.size_bytes
                            results["actions"].append(f"Removed orphaned packages")
                        else:
                            results["errors"].append(f"Failed to remove orphans: {proc.stderr}")

                elif opp.type == "logs":
                    freed = self._compress_logs(opp.items, session_backup_dir if safe else None)
                    results["freed_bytes"] += freed
                    results["actions"].append(f"Compressed {len(opp.items)} log files")
                
                elif opp.type == "temp":
                    freed = self._remove_files(opp.items, session_backup_dir if safe else None)
                    results["freed_bytes"] += freed
                    results["actions"].append(f"Removed {len(opp.items)} temp files")
                    
            except Exception as e:
                results["errors"].append(str(e))
                
        return results

    def _compress_logs(self, files: List[str], backup_dir: Optional[Path]) -> int:
        freed = 0
        for fpath in files:
            try:
                original_size = os.path.getsize(fpath)
                
                # Backup if safe mode
                if backup_dir:
                    # Maintain directory structure in backup
                    rel_path = os.path.relpath(fpath, "/")
                    dest = backup_dir / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(fpath, dest)
                
                # Compress
                # We need sudo if we don't own the file
                if not os.access(fpath, os.W_OK):
                    # Use sudo gzip
                    subprocess.run(["sudo", "gzip", "-f", fpath], check=True)
                    # Check new size
                    if os.path.exists(fpath + ".gz"):
                         new_size = os.path.getsize(fpath + ".gz")
                         freed += (original_size - new_size)
                else:
                    with open(fpath, 'rb') as f_in:
                         with gzip.open(fpath + '.gz', 'wb') as f_out:
                             shutil.copyfileobj(f_in, f_out)
                    os.remove(fpath)
                    new_size = os.path.getsize(fpath + ".gz")
                    freed += (original_size - new_size)
                    
            except Exception as e:
                logger.error(f"Failed to compress {fpath}: {e}")
                
        return freed

    def _remove_files(self, files: List[str], backup_dir: Optional[Path]) -> int:
        freed = 0
        for fpath in files:
            try:
                size = os.path.getsize(fpath)
                 # Backup
                if backup_dir:
                    rel_path = os.path.relpath(fpath, "/")
                    dest = backup_dir / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(fpath, dest)
                
                # Remove
                if not os.access(fpath, os.W_OK) and not os.access(os.path.dirname(fpath), os.W_OK):
                    subprocess.run(["sudo", "rm", "-f", fpath], check=True)
                else:
                    os.remove(fpath)
                freed += size
            except Exception as e:
                logger.error(f"Failed to remove {fpath}: {e}")
        return freed

    def schedule_cleanup(self, frequency: str) -> bool:
        """
        Schedule cleanup job.
        frequency: 'daily', 'weekly', 'monthly'
        """
        # Using cron
        script_path = os.path.abspath(sys.argv[0])
        # Assumes running from cortex wrapper or python module
        # Simplest is to run 'cortex cleanup run --safe'
        
        cron_cmd = "cortex cleanup run --safe > /var/log/cortex-cleanup.log 2>&1"
        
        cron_time = "@daily"
        if frequency == 'weekly': cron_time = "@weekly"
        elif frequency == 'monthly': cron_time = "@monthly"
        
        entry = f"{cron_time} {cron_cmd}"
        
        try:
            # Check if crontab entry exists
            current_crontab = subprocess.run("crontab -l", shell=True, capture_output=True, text=True).stdout
            if cron_cmd in current_crontab:
                # Update existing? For now just return
                return True
                
            new_crontab = current_crontab + f"\n# Cortex Auto-Cleanup\n{entry}\n"
            
            proc = subprocess.run(
                ["crontab", "-"],
                input=new_crontab,
                text=True,
                capture_output=True
            )
            return proc.returncode == 0
        except Exception:
            return False

    def restore(self, cleanup_id: str) -> bool:
        """Undo a cleanup session"""
        # Logic:
        # 1. Find backup folder
        # 2. Restore files (logs, temp)
        # 3. For packages, use history rollback if available, or just reinstall what was removed?
        # Since we didn't fully integrate with InstallationHistory for the cleanup op yet (just CLI wrapper),
        # we might need to rely on the backup files for logs/temp.
        # For packages, 'apt history' or our internal history.
        return False # TODO: Implement full restore logic
