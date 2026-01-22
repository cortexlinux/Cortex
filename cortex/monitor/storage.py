"""
Storage Module for Cortex Monitor

Persists monitoring sessions to SQLite database.
Extends the existing installation_history.py schema.

Author: Cortex Linux Team
SPDX-License-Identifier: BUSL-1.1
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from cortex.monitor.sampler import PeakUsage, ResourceSample

logger = logging.getLogger(__name__)

# Default database path (same as installation_history.py)
DEFAULT_DB_PATH = "/var/lib/cortex/history.db"
USER_DB_PATH = Path.home() / ".cortex" / "history.db"


class MonitorStorage:
    """
    Persistent storage for monitoring sessions.

    Stores monitor sessions and individual samples in SQLite.
    Uses the same database as installation history for consistency.
    """

    def __init__(self, db_path: str | None = None):
        """
        Initialize monitor storage.

        Args:
            db_path: Optional custom database path
        """
        self.db_path = db_path or self._get_db_path()
        self._ensure_tables()

    def _get_db_path(self) -> str:
        """Get the database path, with fallback to user directory."""
        import os

        db_path = Path(DEFAULT_DB_PATH)

        # Check if system path is writable using os.access
        if db_path.parent.exists() and db_path.parent.is_dir():
            # Check if we can write to the directory (or to the file if it exists)
            if db_path.exists():
                if os.access(db_path, os.W_OK):
                    return str(db_path)
            elif os.access(db_path.parent, os.W_OK):
                return str(db_path)

        # Fall back to user directory
        USER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return str(USER_DB_PATH)

    def _ensure_tables(self) -> None:
        """Ensure required tables exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create monitor_sessions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS monitor_sessions (
                        session_id TEXT PRIMARY KEY,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        mode TEXT,
                        install_id TEXT,
                        interval_seconds REAL,
                        sample_count INTEGER DEFAULT 0,
                        peak_cpu REAL,
                        peak_ram_percent REAL,
                        peak_ram_gb REAL,
                        metadata TEXT
                    )
                """)

                # Create resource_metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS resource_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        cpu_percent REAL,
                        cpu_count INTEGER,
                        ram_used_gb REAL,
                        ram_total_gb REAL,
                        ram_percent REAL,
                        disk_used_gb REAL,
                        disk_total_gb REAL,
                        disk_percent REAL,
                        disk_read_rate REAL,
                        disk_write_rate REAL,
                        net_recv_rate REAL,
                        net_sent_rate REAL,
                        FOREIGN KEY (session_id) REFERENCES monitor_sessions(session_id)
                    )
                """)

                # Create index for faster queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_session
                    ON resource_metrics(session_id)
                """)

                conn.commit()
                logger.debug(f"Monitor tables initialized in {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize monitor tables: {e}")
            raise

    def create_session(
        self,
        mode: str = "standalone",
        install_id: str | None = None,
        interval: float = 1.0,
    ) -> str:
        """
        Create a new monitoring session.

        Args:
            mode: 'standalone' or 'install'
            install_id: Optional installation ID (for install mode)
            interval: Sampling interval in seconds

        Returns:
            Session ID (UUID)
        """
        session_id = str(uuid.uuid4())
        start_time = datetime.now().isoformat()

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO monitor_sessions
                    (session_id, start_time, mode, install_id, interval_seconds)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (session_id, start_time, mode, install_id, interval),
                )
                conn.commit()

            logger.debug(f"Created monitor session: {session_id}")
            return session_id

        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise

    def save_samples(
        self,
        session_id: str,
        samples: list[ResourceSample],
    ) -> int:
        """
        Save samples for a session.

        Args:
            session_id: Session ID
            samples: List of ResourceSample objects

        Returns:
            Number of samples saved
        """
        if not samples:
            return 0

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for sample in samples:
                    cursor.execute(
                        """
                        INSERT INTO resource_metrics
                        (session_id, timestamp, cpu_percent, cpu_count,
                         ram_used_gb, ram_total_gb, ram_percent,
                         disk_used_gb, disk_total_gb, disk_percent,
                         disk_read_rate, disk_write_rate,
                         net_recv_rate, net_sent_rate)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            session_id,
                            sample.timestamp,
                            sample.cpu_percent,
                            sample.cpu_count,
                            sample.ram_used_gb,
                            sample.ram_total_gb,
                            sample.ram_percent,
                            sample.disk_used_gb,
                            sample.disk_total_gb,
                            sample.disk_percent,
                            sample.disk_read_rate,
                            sample.disk_write_rate,
                            sample.net_recv_rate,
                            sample.net_sent_rate,
                        ),
                    )

                conn.commit()

            logger.debug(f"Saved {len(samples)} samples for session {session_id}")
            return len(samples)

        except Exception as e:
            logger.error(f"Failed to save samples: {e}")
            raise

    def finalize_session(
        self,
        session_id: str,
        peak: PeakUsage,
        sample_count: int,
        metadata: dict | None = None,
    ) -> None:
        """
        Finalize a monitoring session with peak usage and end time.

        Args:
            session_id: Session ID
            peak: Peak usage statistics
            sample_count: Total number of samples
            metadata: Optional metadata dict
        """
        end_time = datetime.now().isoformat()

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE monitor_sessions
                    SET end_time = ?,
                        sample_count = ?,
                        peak_cpu = ?,
                        peak_ram_percent = ?,
                        peak_ram_gb = ?,
                        metadata = ?
                    WHERE session_id = ?
                    """,
                    (
                        end_time,
                        sample_count,
                        peak.cpu_percent,
                        peak.ram_percent,
                        peak.ram_used_gb,
                        json.dumps(metadata) if metadata else None,
                        session_id,
                    ),
                )
                conn.commit()

            logger.debug(f"Finalized session {session_id}")

        except Exception as e:
            logger.error(f"Failed to finalize session: {e}")
            raise

    def get_session(self, session_id: str) -> dict | None:
        """
        Get a monitoring session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session dict or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM monitor_sessions WHERE session_id = ?",
                    (session_id,),
                )
                row = cursor.fetchone()

                if row:
                    return dict(row)
                return None

        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None

    def get_session_samples(self, session_id: str) -> list[ResourceSample]:
        """
        Get all samples for a session.

        Args:
            session_id: Session ID

        Returns:
            List of ResourceSample objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM resource_metrics
                    WHERE session_id = ?
                    ORDER BY timestamp
                    """,
                    (session_id,),
                )
                rows = cursor.fetchall()

                samples = []
                for row in rows:
                    samples.append(
                        ResourceSample(
                            timestamp=row["timestamp"],
                            cpu_percent=row["cpu_percent"],
                            cpu_count=row["cpu_count"],
                            ram_used_gb=row["ram_used_gb"],
                            ram_total_gb=row["ram_total_gb"],
                            ram_percent=row["ram_percent"],
                            disk_used_gb=row["disk_used_gb"],
                            disk_total_gb=row["disk_total_gb"],
                            disk_percent=row["disk_percent"],
                            disk_read_rate=row["disk_read_rate"],
                            disk_write_rate=row["disk_write_rate"],
                            net_recv_rate=row["net_recv_rate"],
                            net_sent_rate=row["net_sent_rate"],
                        )
                    )

                return samples

        except Exception as e:
            logger.error(f"Failed to get session samples: {e}")
            return []

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """
        List recent monitoring sessions.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session dicts
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM monitor_sessions
                    ORDER BY start_time DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a monitoring session and its samples.

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Delete samples first (foreign key)
                cursor.execute(
                    "DELETE FROM resource_metrics WHERE session_id = ?",
                    (session_id,),
                )

                # Delete session
                cursor.execute(
                    "DELETE FROM monitor_sessions WHERE session_id = ?",
                    (session_id,),
                )

                conn.commit()

            logger.info(f"Deleted session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False

    def cleanup_old_sessions(self, days: int = 30) -> int:
        """
        Remove sessions older than specified days.

        Args:
            days: Delete sessions older than this

        Returns:
            Number of sessions deleted
        """
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get session IDs to delete
                cursor.execute(
                    "SELECT session_id FROM monitor_sessions WHERE start_time < ?",
                    (cutoff,),
                )
                session_ids = [row[0] for row in cursor.fetchall()]

                if not session_ids:
                    return 0

                # Delete samples
                placeholders = ",".join("?" * len(session_ids))
                cursor.execute(
                    f"DELETE FROM resource_metrics WHERE session_id IN ({placeholders})",
                    session_ids,
                )

                # Delete sessions
                cursor.execute(
                    f"DELETE FROM monitor_sessions WHERE session_id IN ({placeholders})",
                    session_ids,
                )

                conn.commit()

            logger.info(f"Cleaned up {len(session_ids)} old sessions")
            return len(session_ids)

        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            return 0
