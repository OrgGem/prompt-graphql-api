# pgql/monitoring/metrics.py
"""Request metrics tracking with SQLite persistence.

Metrics survive container restarts by periodically saving counters
to a SQLite database. Timing data uses bounded deques to prevent
memory leaks.
"""

import json
import os
import sqlite3
import time
import logging
import threading
from collections import defaultdict, deque
from threading import Lock
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("promptql_metrics")

# Default persistence interval (seconds)
_SAVE_INTERVAL = 60

# Max items in timing deques
_MAX_RESPONSE_TIMES = 1000
_MAX_RESPONSE_TIMES_PER_TOOL = 500


class RequestMetrics:
    """Track request metrics with SQLite persistence.

    Persisted on save: counters (total, success, fail), per-tool counters.
    Ephemeral (not persisted): timing deques, request history, error log.
    """

    def __init__(
        self,
        max_history: int = 1000,
        max_errors: int = 100,
        data_dir: Optional[str] = None,
        save_interval: int = _SAVE_INTERVAL,
    ):
        self._lock = Lock()
        self._start_time = time.time()

        # Counters
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

        # Per-tool counters
        self.requests_by_tool: Dict[str, int] = defaultdict(int)
        self.errors_by_tool: Dict[str, int] = defaultdict(int)

        # Timing — bounded deques to prevent memory leaks
        self._response_times: deque = deque(maxlen=_MAX_RESPONSE_TIMES)
        self._response_times_by_tool: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=_MAX_RESPONSE_TIMES_PER_TOOL)
        )

        # History (bounded deques)
        self.request_history: deque = deque(maxlen=max_history)
        self.error_log: deque = deque(maxlen=max_errors)

        # SQLite persistence
        self._db_path = self._resolve_db_path(data_dir)
        self._logs_dir = self._resolve_logs_dir(data_dir)
        self._init_db()
        self._load_snapshot()
        
        # Log write health tracking
        self._log_write_failures = 0

        # Background save timer
        self._save_interval = save_interval
        self._timer: Optional[threading.Timer] = None
        self._start_auto_save()

    @staticmethod
    def _resolve_db_path(data_dir: Optional[str]) -> str:
        """Resolve the metrics database path."""
        if data_dir:
            d = Path(data_dir)
        else:
            d = Path(os.getenv("PGQL_DATA_DIR", "/app/data"))
        d.mkdir(parents=True, exist_ok=True)
        return str(d / "metrics.db")

    @staticmethod
    def _resolve_logs_dir(data_dir: Optional[str]) -> Path:
        """Resolve the logs directory path."""
        if data_dir:
            base = Path(data_dir)
        else:
            base = Path(os.getenv("PGQL_DATA_DIR", "/app/data"))
        logs_dir = base / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir

    def _init_db(self):
        """Create the metrics table if it doesn't exist."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics_snapshot (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_requests INTEGER DEFAULT 0,
                    successful_requests INTEGER DEFAULT 0,
                    failed_requests INTEGER DEFAULT 0,
                    requests_by_tool TEXT DEFAULT '{}',
                    errors_by_tool TEXT DEFAULT '{}',
                    saved_at TEXT
                )
            """)
            conn.commit()
            conn.close()
            logger.debug(f"Metrics DB initialized at {self._db_path}")
        except sqlite3.Error as e:
            logger.warning(f"Could not init metrics DB: {e}")

    def _load_snapshot(self):
        """Load persisted counters from SQLite on startup."""
        try:
            conn = sqlite3.connect(self._db_path)
            row = conn.execute(
                "SELECT total_requests, successful_requests, failed_requests, "
                "requests_by_tool, errors_by_tool, saved_at FROM metrics_snapshot WHERE id = 1"
            ).fetchone()
            conn.close()

            if row:
                self.total_requests = row[0]
                self.successful_requests = row[1]
                self.failed_requests = row[2]
                # Restore per-tool counters
                rbt = json.loads(row[3]) if row[3] else {}
                ebt = json.loads(row[4]) if row[4] else {}
                self.requests_by_tool = defaultdict(int, rbt)
                self.errors_by_tool = defaultdict(int, ebt)
                logger.info(
                    f"Restored metrics from {row[5]}: "
                    f"{self.total_requests} total, {self.successful_requests} ok, {self.failed_requests} err"
                )
        except (sqlite3.Error, json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Could not load metrics snapshot: {e}")

    def _save_snapshot(self):
        """Persist current counters to SQLite."""
        try:
            with self._lock:
                rbt_json = json.dumps(dict(self.requests_by_tool))
                ebt_json = json.dumps(dict(self.errors_by_tool))
                now = datetime.now(timezone.utc).isoformat()
                snapshot = (
                    self.total_requests, self.successful_requests, self.failed_requests,
                    rbt_json, ebt_json, now,
                )
            # Write outside lock to avoid holding lock during I/O
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO metrics_snapshot "
                    "(id, total_requests, successful_requests, failed_requests, "
                    "requests_by_tool, errors_by_tool, saved_at) VALUES (1, ?, ?, ?, ?, ?, ?)",
                    snapshot,
                )
                conn.commit()
            finally:
                conn.close()
            logger.debug(f"Metrics snapshot saved ({snapshot[0]} total)")
        except sqlite3.Error as e:
            logger.warning(f"Could not save metrics snapshot: {e}")

    def _write_to_daily_log(self, entry: Dict[str, Any]) -> None:
        """Append request entry to daily log file (JSON lines format)."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = self._logs_dir / f"requests-{date_str}.jsonl"
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def get_daily_log(self, date_str: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read log entries from a specific date.
        
        Args:
            date_str: Date in YYYY-MM-DD format
            limit: Optional max number of entries to return (most recent first)
        
        Returns:
            List of log entries
        """
        log_file = self._logs_dir / f"requests-{date_str}.jsonl"
        
        if not log_file.exists():
            return []
        
        entries = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        
        # Return most recent first
        entries.reverse()
        
        if limit:
            entries = entries[:limit]
        
        return entries
    
    def list_available_log_dates(self) -> List[str]:
        """List all dates that have log files."""
        dates = []
        for log_file in self._logs_dir.glob("requests-*.jsonl"):
            # Extract date from filename: requests-2026-02-17.jsonl
            name = log_file.stem  # removes .jsonl
            date_part = name.replace("requests-", "")
            dates.append(date_part)
        return sorted(dates, reverse=True)  # Most recent first


    def _start_auto_save(self):
        """Start background timer for periodic saves."""
        def _tick():
            self._save_snapshot()
            # Re-schedule (daemon timer so it won't block shutdown)
            self._timer = threading.Timer(self._save_interval, _tick)
            self._timer.daemon = True
            self._timer.start()

        self._timer = threading.Timer(self._save_interval, _tick)
        self._timer.daemon = True
        self._timer.start()

    def record_request(
        self,
        tool_name: str,
        duration: float,
        success: bool,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a completed request."""
        with self._lock:
            self.total_requests += 1
            self.requests_by_tool[tool_name] += 1
            self._response_times.append(duration)
            self._response_times_by_tool[tool_name].append(duration)

            if success:
                self.successful_requests += 1
            else:
                self.failed_requests += 1
                self.errors_by_tool[tool_name] += 1

            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool": tool_name,
                "duration_ms": round(duration * 1000, 2),
                "success": success,
                "error": error_message,
            }
            if metadata:
                entry["metadata"] = metadata

            self.request_history.append(entry)

            # Write to daily log file with health tracking
            try:
                self._write_to_daily_log(entry)
                self._log_write_failures = 0  # Reset on success
            except (IOError, OSError) as e:
                self._log_write_failures += 1
                logger.warning(f"Failed to write to daily log: {e}")
                if self._log_write_failures >= 10:
                    logger.error(
                        f"CRITICAL: Log writing has failed {self._log_write_failures} times consecutively. "
                        "Check disk space and file permissions."
                    )
            except Exception as e:
                logger.error(f"Unexpected error writing daily log: {e}", exc_info=True)

            if not success and error_message:
                self.error_log.append({
                    "timestamp": entry["timestamp"],
                    "tool": tool_name,
                    "error": error_message,
                })

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._start_time

    @property
    def average_response_time(self) -> float:
        if not self._response_times:
            return 0.0
        return sum(self._response_times) / len(self._response_times)

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    def get_summary(self) -> Dict[str, Any]:
        """Get a full metrics summary."""
        with self._lock:
            # Per-tool breakdown
            tool_stats = {}
            for tool, count in self.requests_by_tool.items():
                times = self._response_times_by_tool.get(tool, deque())
                tool_stats[tool] = {
                    "total": count,
                    "errors": self.errors_by_tool.get(tool, 0),
                    "avg_duration_ms": round(
                        (sum(times) / len(times) * 1000) if times else 0, 2
                    ),
                }

            return {
                "uptime_seconds": round(self.uptime_seconds, 1),
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "success_rate": round(self.success_rate, 4),
                "avg_response_time_ms": round(self.average_response_time * 1000, 2),
                "tools": tool_stats,
            }

    def get_recent_requests(self, limit: int = 50) -> List[Dict]:
        """Get most recent request history entries."""
        with self._lock:
            items = list(self.request_history)
            return items[-limit:]

    def get_recent_errors(self, limit: int = 20) -> List[Dict]:
        """Get most recent errors."""
        with self._lock:
            items = list(self.error_log)
            return items[-limit:]

    def reset(self) -> None:
        """Reset all metrics (both in-memory and persisted)."""
        with self._lock:
            self.total_requests = 0
            self.successful_requests = 0
            self.failed_requests = 0
            self.requests_by_tool.clear()
            self.errors_by_tool.clear()
            self._response_times.clear()
            self._response_times_by_tool.clear()
            self.request_history.clear()
            self.error_log.clear()
            self._start_time = time.time()
            logger.info("Metrics reset")
        # Persist the reset
        self._save_snapshot()

    def shutdown(self):
        """Save final snapshot and cancel timer."""
        if self._timer:
            self._timer.cancel()
        self._save_snapshot()
        logger.info("Metrics shutdown — final snapshot saved")


# Global instance
request_metrics = RequestMetrics()
