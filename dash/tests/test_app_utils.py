"""Tests for app utility functions."""

from datetime import datetime, timezone, timedelta

import pytest
from freezegun import freeze_time

from aaas_dashboard.app import (
    get_status_color,
    get_status_badge_class,
    get_task_card_class,
    format_datetime,
    format_duration,
)
from aaas_dashboard.client import TaskStatus


class TestGetStatusColor:
    """Test get_status_color function."""

    def test_get_status_color_pending(self):
        """Test color for pending status."""
        assert get_status_color(TaskStatus.PENDING) == "gray"

    def test_get_status_color_running(self):
        """Test color for running status."""
        assert get_status_color(TaskStatus.RUNNING) == "orange"

    def test_get_status_color_completed(self):
        """Test color for completed status."""
        assert get_status_color(TaskStatus.COMPLETED) == "green"

    def test_get_status_color_failed(self):
        """Test color for failed status."""
        assert get_status_color(TaskStatus.FAILED) == "red"

    def test_get_status_color_cancelled(self):
        """Test color for cancelled status."""
        assert get_status_color(TaskStatus.CANCELLED) == "purple"

    def test_get_status_color_cancelling(self):
        """Test color for cancelling status."""
        assert get_status_color(TaskStatus.CANCELLING) == "orange"

    def test_get_status_color_unknown(self):
        """Test default color for unknown status."""
        # Create a mock status not in the mapping
        class MockStatus:
            value = "unknown"
        
        assert get_status_color(MockStatus()) == "gray"


class TestGetStatusBadgeClass:
    """Test get_status_badge_class function."""

    def test_get_status_badge_class_pending(self):
        """Test CSS class for pending status."""
        assert get_status_badge_class(TaskStatus.PENDING) == "status-pending"

    def test_get_status_badge_class_running(self):
        """Test CSS class for running status."""
        assert get_status_badge_class(TaskStatus.RUNNING) == "status-running"

    def test_get_status_badge_class_completed(self):
        """Test CSS class for completed status."""
        assert get_status_badge_class(TaskStatus.COMPLETED) == "status-completed"

    def test_get_status_badge_class_failed(self):
        """Test CSS class for failed status."""
        assert get_status_badge_class(TaskStatus.FAILED) == "status-failed"

    def test_get_status_badge_class_cancelled(self):
        """Test CSS class for cancelled status."""
        assert get_status_badge_class(TaskStatus.CANCELLED) == "status-cancelled"

    def test_get_status_badge_class_cancelling(self):
        """Test CSS class for cancelling status."""
        assert get_status_badge_class(TaskStatus.CANCELLING) == "status-cancelling"


class TestGetTaskCardClass:
    """Test get_task_card_class function."""

    def test_get_task_card_class(self):
        """Test task card CSS class generation."""
        assert get_task_card_class(TaskStatus.PENDING) == "task-card pending"
        assert get_task_card_class(TaskStatus.RUNNING) == "task-card running"
        assert get_task_card_class(TaskStatus.COMPLETED) == "task-card completed"


class TestFormatDatetime:
    """Test format_datetime function."""

    def test_format_datetime_with_value(self):
        """Test formatting datetime with a value."""
        dt = datetime(2024, 1, 15, 14, 30, 45)
        
        result = format_datetime(dt)
        
        assert result == "2024-01-15 14:30:45"

    def test_format_datetime_with_none(self):
        """Test formatting datetime with None."""
        result = format_datetime(None)
        
        assert result == "-"

    def test_format_datetime_with_timezone(self):
        """Test formatting datetime with timezone info."""
        dt = datetime(2024, 1, 15, 14, 30, 45, tzinfo=timezone.utc)
        
        result = format_datetime(dt)
        
        # Should still format correctly (ignores timezone info)
        assert result == "2024-01-15 14:30:45"


class TestFormatDuration:
    """Test format_duration function."""

    @freeze_time("2024-01-15 12:00:00", tz_offset=0)
    def test_format_duration_hours_minutes_seconds(self):
        """Test formatting duration with hours, minutes, and seconds."""
        start = datetime(2024, 1, 15, 10, 30, 15, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        result = format_duration(start, end)
        
        assert result == "1h 29m 45s"

    @freeze_time("2024-01-15 12:00:00", tz_offset=0)
    def test_format_duration_minutes_seconds(self):
        """Test formatting duration with minutes and seconds."""
        start = datetime(2024, 1, 15, 11, 55, 30, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        result = format_duration(start, end)
        
        assert result == "4m 30s"

    @freeze_time("2024-01-15 12:00:00", tz_offset=0)
    def test_format_duration_seconds_only(self):
        """Test formatting duration with seconds only."""
        start = datetime(2024, 1, 15, 11, 59, 45, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        result = format_duration(start, end)
        
        assert result == "15s"

    def test_format_duration_with_none(self):
        """Test formatting duration with None start."""
        result = format_duration(None, datetime.now())
        
        assert result == "-"

    @freeze_time("2024-01-15 12:00:30", tz_offset=0)
    def test_format_duration_none_end(self):
        """Test formatting duration when end is None (uses current time)."""
        start = datetime(2024, 1, 15, 11, 59, 0, tzinfo=timezone.utc)
        
        result = format_duration(start, None)
        
        assert result == "1m 30s"

    def test_format_duration_with_timezone_naive_start(self):
        """Test formatting with timezone-naive start and timezone-aware end."""
        start = datetime(2024, 1, 15, 10, 0, 0)  # naive
        end = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)  # aware
        
        result = format_duration(start, end)
        
        # End timezone should be stripped
        assert result == "2h 0m 0s"

    def test_format_duration_with_timezone_aware_start(self):
        """Test formatting with timezone-aware start and timezone-naive end."""
        start = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)  # aware
        end = datetime(2024, 1, 15, 12, 0, 0)  # naive
        
        result = format_duration(start, end)
        
        # Start timezone should be stripped
        assert result == "2h 0m 0s"

    def test_format_duration_both_aware_same_timezone(self):
        """Test formatting when both datetimes have the same timezone."""
        start = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
        
        result = format_duration(start, end)
        
        assert result == "2h 30m 45s"

    def test_format_duration_both_naive(self):
        """Test formatting when both datetimes are timezone-naive."""
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 12, 30, 45)
        
        result = format_duration(start, end)
        
        assert result == "2h 30m 45s"

    def test_format_duration_negative(self):
        """Test formatting when end is before start (returns 0s due to divmod behavior)."""
        start = datetime(2024, 1, 15, 12, 0, 0)
        end = datetime(2024, 1, 15, 10, 0, 0)
        
        result = format_duration(start, end)
        
        # Negative durations result in 0s due to divmod with negative numbers
        assert result == "0s"


class TestFormatDurationEdgeCases:
    """Test format_duration edge cases."""

    def test_format_duration_exact_hour(self):
        """Test formatting duration of exactly one hour."""
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 11, 0, 0)
        
        result = format_duration(start, end)
        
        assert result == "1h 0m 0s"

    def test_format_duration_exact_minute(self):
        """Test formatting duration of exactly one minute."""
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 10, 1, 0)
        
        result = format_duration(start, end)
        
        assert result == "1m 0s"

    def test_format_duration_one_second(self):
        """Test formatting duration of exactly one second."""
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 10, 0, 1)
        
        result = format_duration(start, end)
        
        assert result == "1s"

    def test_format_duration_zero_seconds(self):
        """Test formatting duration of zero seconds."""
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 10, 0, 0)
        
        result = format_duration(start, end)
        
        assert result == "0s"

    def test_format_duration_large_hours(self):
        """Test formatting duration with large number of hours."""
        start = datetime(2024, 1, 15, 0, 0, 0)
        end = datetime(2024, 1, 16, 12, 30, 45)
        
        result = format_duration(start, end)
        
        assert result == "36h 30m 45s"
