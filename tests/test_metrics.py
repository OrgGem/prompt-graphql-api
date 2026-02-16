# tests/test_metrics.py
"""Tests for monitoring/metrics.py — RequestMetrics."""

import time
import pytest
from pgql.monitoring.metrics import RequestMetrics


class TestRequestMetrics:
    """Tests for the RequestMetrics tracker."""

    def setup_method(self):
        self.metrics = RequestMetrics(max_history=50, max_errors=20)

    def test_initial_state(self):
        """Freshly created metrics should be all zeros."""
        assert self.metrics.total_requests == 0
        assert self.metrics.successful_requests == 0
        assert self.metrics.failed_requests == 0
        assert self.metrics.success_rate == 1.0
        assert self.metrics.average_response_time == 0.0

    def test_record_successful_request(self):
        self.metrics.record_request("start_thread", 0.5, True)
        assert self.metrics.total_requests == 1
        assert self.metrics.successful_requests == 1
        assert self.metrics.failed_requests == 0
        assert self.metrics.success_rate == 1.0

    def test_record_failed_request(self):
        self.metrics.record_request("start_thread", 0.3, False, "Timeout")
        assert self.metrics.total_requests == 1
        assert self.metrics.successful_requests == 0
        assert self.metrics.failed_requests == 1
        assert self.metrics.success_rate == 0.0

    def test_mixed_requests(self):
        self.metrics.record_request("start_thread", 0.1, True)
        self.metrics.record_request("continue_thread", 0.2, True)
        self.metrics.record_request("get_thread_status", 0.3, False, "Error")
        assert self.metrics.total_requests == 3
        assert self.metrics.successful_requests == 2
        assert self.metrics.failed_requests == 1
        assert self.metrics.success_rate == pytest.approx(2 / 3, rel=1e-3)

    def test_average_response_time(self):
        self.metrics.record_request("tool_a", 0.1, True)
        self.metrics.record_request("tool_b", 0.3, True)
        self.metrics.record_request("tool_c", 0.2, True)
        assert self.metrics.average_response_time == pytest.approx(0.2, rel=1e-3)

    def test_per_tool_counters(self):
        self.metrics.record_request("start_thread", 0.1, True)
        self.metrics.record_request("start_thread", 0.2, True)
        self.metrics.record_request("query_hasura_ce", 0.3, False, "Err")
        assert self.metrics.requests_by_tool["start_thread"] == 2
        assert self.metrics.requests_by_tool["query_hasura_ce"] == 1
        assert self.metrics.errors_by_tool["query_hasura_ce"] == 1
        assert self.metrics.errors_by_tool.get("start_thread", 0) == 0

    def test_request_history(self):
        self.metrics.record_request("tool_a", 0.1, True)
        self.metrics.record_request("tool_b", 0.2, False, "Fail")
        history = self.metrics.get_recent_requests(10)
        assert len(history) == 2
        assert history[0]["tool"] == "tool_a"
        assert history[0]["success"] is True
        assert history[1]["tool"] == "tool_b"
        assert history[1]["success"] is False

    def test_error_log(self):
        self.metrics.record_request("tool_a", 0.1, True)
        self.metrics.record_request("tool_b", 0.2, False, "Failure msg")
        errors = self.metrics.get_recent_errors(10)
        assert len(errors) == 1
        assert errors[0]["tool"] == "tool_b"
        assert errors[0]["error"] == "Failure msg"

    def test_history_bounded(self):
        """History should not exceed max_history."""
        for i in range(60):
            self.metrics.record_request(f"tool_{i}", 0.01, True)
        assert len(self.metrics.request_history) == 50  # max_history=50

    def test_get_summary(self):
        self.metrics.record_request("tool_a", 0.1, True)
        self.metrics.record_request("tool_a", 0.3, False, "Err")
        summary = self.metrics.get_summary()
        assert summary["total_requests"] == 2
        assert summary["successful_requests"] == 1
        assert summary["failed_requests"] == 1
        assert "tool_a" in summary["tools"]
        assert summary["tools"]["tool_a"]["total"] == 2
        assert summary["tools"]["tool_a"]["errors"] == 1

    def test_reset(self):
        self.metrics.record_request("tool_a", 0.1, True)
        self.metrics.record_request("tool_b", 0.2, False, "Err")
        self.metrics.reset()
        assert self.metrics.total_requests == 0
        assert self.metrics.successful_requests == 0
        assert self.metrics.failed_requests == 0
        assert len(self.metrics.request_history) == 0
        assert len(self.metrics.error_log) == 0

    def test_uptime(self):
        """Uptime should be positive."""
        time.sleep(0.05)
        assert self.metrics.uptime_seconds > 0

    def test_metadata_in_history(self):
        self.metrics.record_request("tool_a", 0.1, True, metadata={"key": "val"})
        history = self.metrics.get_recent_requests(1)
        assert history[0]["metadata"] == {"key": "val"}

    def test_duration_ms_in_history(self):
        self.metrics.record_request("tool_a", 0.123, True)
        history = self.metrics.get_recent_requests(1)
        assert history[0]["duration_ms"] == pytest.approx(123.0, rel=1e-1)
