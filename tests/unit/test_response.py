"""Unit tests for the response utility."""

from app.utils.response import success


def test_success_with_data_and_message():
    """success() should return envelope with data and message."""
    result = success(data={"key": "value"}, message="Done")
    assert result["status"] == "success"
    assert result["data"] == {"key": "value"}
    assert result["message"] == "Done"


def test_success_default_message():
    """success() should default message to empty string."""
    result = success(data=[1, 2, 3])
    assert result["message"] == ""


def test_success_none_data():
    """success() should allow None as data."""
    result = success()
    assert result["data"] is None
