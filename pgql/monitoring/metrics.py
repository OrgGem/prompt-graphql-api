# pgql/monitoring/metrics.py
"""Request metrics tracking for monitoring and dashboard."""

import time
import logging
from collections import defaultdict, deque
from threading import Lock
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger("promptql_metrics")


class RequestMetrics:
    """Track request metrics for monitoring and dashboard display."""

    def __init__(self, max_history: int = 1000, max_errors: int = 100):
        self._lock = Lock()
        self._start_time = time.time()

        # Counters
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

        # Per-tool counters
        self.requests_by_tool: Dict[str, int] = defaultdict(int)
        self.errors_by_tool: Dict[str, int] = defaultdict(int)

        # Timing
        self._response_times: List[float] = []
        self._response_times_by_tool: Dict[str, List[float]] = defaultdict(list)

        # History (bounded deques)
        self.request_history: deque = deque(maxlen=max_history)
        self.error_log: deque = deque(maxlen=max_errors)

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
                times = self._response_times_by_tool.get(tool, [])
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
        """Reset all metrics."""
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


# Global instance
request_metrics = RequestMetrics()
