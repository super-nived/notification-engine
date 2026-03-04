"""
Pagination helper for list endpoints.

Use ``paginate()`` to slice any list based on ``page`` and ``size``
query parameters before returning it from a router.
"""

from typing import Any


def paginate(
    items: list[Any],
    page: int = 1,
    size: int = 50,
) -> dict[str, Any]:
    """Slice a list and return it with pagination metadata.

    Args:
        items: Full list of items to paginate.
        page:  1-based page number.
        size:  Number of items per page.

    Returns:
        Dict with keys:
            items (list): The sliced page of items.
            total (int):  Total item count before slicing.
            page  (int):  Current page number.
            size  (int):  Page size used.
            pages (int):  Total number of pages.
    """
    total = len(items)
    pages = max(1, -(-total // size))  # ceiling division
    start = (page - 1) * size
    end = start + size
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }
