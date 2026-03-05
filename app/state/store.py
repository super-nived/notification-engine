"""
Generic rule state store backed by the PocketBase ``state`` JSON field.

Each rule gets its own ``RuleStateStore`` instance keyed by rule name.
Rules can persist arbitrary key/value data between runs without
touching files, SQLite, or any per-rule storage code.

Usage::

    store = RuleStateStore("my_rule_name")
    last_seen = store.get("last_seen")           # None if not set
    store.set("last_seen", "2024-01-01T00:00Z")  # persisted immediately
    store.delete("last_seen")                    # remove a key
    store.clear()                                # wipe all state for this rule
"""

import json
import logging
from typing import Any

from app.db import pb_repositories as pb

logger = logging.getLogger(__name__)


class RuleStateStore:
    """Key/value state store for a single rule, backed by PocketBase.

    State is stored as a JSON object in the ``state`` field of the
    corresponding ``ASWNDUBAI_rules`` record. Reads are cached in-process
    and writes are persisted to PocketBase immediately.

    Args:
        rule_name: Unique name of the rule this store belongs to.
    """

    def __init__(self, rule_name: str) -> None:
        self._rule_name = rule_name
        self._cache: dict[str, Any] | None = None  # None = not yet loaded

    # ── Internal helpers ────────────────────────────────────────────────────

    def _load(self) -> dict[str, Any]:
        """Load state from PocketBase into the in-process cache.

        Returns:
            Current state dict (may be empty).
        """
        if self._cache is not None:
            return self._cache
        try:
            self._cache = pb.get_rule_state(self._rule_name)
        except Exception as exc:
            logger.error(
                "RuleStateStore[%s]: failed to load state: %s",
                self._rule_name,
                exc,
            )
            self._cache = {}
        return self._cache

    def _save(self) -> None:
        """Persist the in-process cache back to PocketBase.

        Errors are logged but do not raise — a failed save means the next
        run will re-detect and re-alert, which is safer than crashing.
        """
        try:
            pb.update_rule_state(self._rule_name, self._cache or {})
        except Exception as exc:
            logger.error(
                "RuleStateStore[%s]: failed to save state: %s",
                self._rule_name,
                exc,
            )

    # ── Public API ──────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for ``key``, or ``default`` if not set.

        Args:
            key:     State key string.
            default: Value to return when the key is absent.

        Returns:
            Stored value or ``default``.
        """
        return self._load().get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set ``key`` to ``value`` and persist immediately.

        Args:
            key:   State key string.
            value: JSON-serialisable value to store.

        Returns:
            None
        """
        state = self._load()
        state[key] = value
        self._save()

    def delete(self, key: str) -> None:
        """Remove ``key`` from state and persist.

        A no-op if the key does not exist.

        Args:
            key: State key to remove.

        Returns:
            None
        """
        state = self._load()
        if key in state:
            del state[key]
            self._save()

    def clear(self) -> None:
        """Wipe all state for this rule and persist.

        Returns:
            None
        """
        self._cache = {}
        self._save()

    def invalidate_cache(self) -> None:
        """Force a fresh load from PocketBase on the next access.

        Useful if state may have been modified externally.

        Returns:
            None
        """
        self._cache = None
