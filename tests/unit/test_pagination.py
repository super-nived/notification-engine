"""Unit tests for the pagination utility."""

from app.utils.pagination import paginate


def test_first_page():
    """paginate() should return the first page correctly."""
    items = list(range(10))
    result = paginate(items, page=1, size=3)
    assert result["items"] == [0, 1, 2]
    assert result["page"] == 1
    assert result["size"] == 3
    assert result["total"] == 10


def test_last_partial_page():
    """paginate() should return a partial last page."""
    items = list(range(10))
    result = paginate(items, page=4, size=3)
    assert result["items"] == [9]


def test_beyond_last_page():
    """paginate() should return empty items for out-of-range page."""
    items = list(range(5))
    result = paginate(items, page=99, size=10)
    assert result["items"] == []
    assert result["total"] == 5


def test_empty_list():
    """paginate() should handle empty input gracefully."""
    result = paginate([], page=1, size=10)
    assert result["items"] == []
    assert result["total"] == 0
