"""
Standard API response wrapper.

All router functions must return via ``success()`` or ``error()``.
Never return raw dicts or lists directly from a router.
"""

from typing import Any


def success(data: Any = None, message: str = "OK") -> dict[str, Any]:
    """Build a standard success response envelope.

    Args:
        data:    The payload to include in the response.
        message: Human-readable status message.

    Returns:
        Dict with ``status``, ``message``, and ``data`` keys.
    """
    return {"status": "success", "message": message, "data": data}
