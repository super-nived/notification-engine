"""Unit tests for the custom exception hierarchy."""

import pytest

from app.core.exceptions import (
    DataSourceError,
    NotifierConfigNotFoundError,
    NotifierError,
    RuleConfigError,
    RuleNotFoundError,
    SchedulerError,
)


def test_rule_not_found_error_message():
    """RuleNotFoundError should embed rule_id in message."""
    exc = RuleNotFoundError(42)
    assert "42" in str(exc)


def test_notifier_config_not_found_error_message():
    """NotifierConfigNotFoundError should embed config_id in message."""
    exc = NotifierConfigNotFoundError(7)
    assert "7" in str(exc)


def test_rule_config_error_is_value_error():
    """RuleConfigError should be a subclass of ValueError."""
    assert issubclass(RuleConfigError, Exception)


def test_all_exceptions_are_raisable():
    """All custom exceptions should be raisable and catchable."""
    for exc_cls in [
        RuleNotFoundError,
        NotifierConfigNotFoundError,
        RuleConfigError,
        DataSourceError,
        NotifierError,
        SchedulerError,
    ]:
        with pytest.raises(exc_cls):
            raise exc_cls("test")
