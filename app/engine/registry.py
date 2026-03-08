"""
Registry maps for rules, notifiers, and data sources.

Built-in rules are registered statically below.
Uploaded rules are registered dynamically via ``register_rule_class()``.

The scheduler and service layer look up classes by their string key.
"""

import importlib.util
import inspect
import logging
from pathlib import Path

from app.datasources.mongodb import MongoDataSource
from app.datasources.pocketbase import PocketBaseDataSource
from app.datasources.sqlserver import SqlServerDataSource
from app.notifiers.desktop_notifier import DesktopNotifier
from app.notifiers.email_notifier import EmailNotifier
from app.notifiers.log_notifier import LogNotifier
from app.notifiers.webhook_notifier import WebhookNotifier
from app.notifiers.websocket_notifier import WebSocketNotifier
from app.rule_definitions.downtime_rule import DowntimeRule
from app.rule_definitions.example_rule import ExampleRule
from app.rule_definitions.oee_rule import OEERule

logger = logging.getLogger(__name__)

# ── Rules ─────────────────────────────────────────────────────────────────────

RULE_REGISTRY: dict[str, type] = {
    "DowntimeRule": DowntimeRule,
    "OEERule": OEERule,
    "ExampleRule": ExampleRule,
}


def register_rule_class(class_name: str, cls: type) -> None:
    """Add or replace a rule class in the registry at runtime.

    Args:
        class_name: The key used in ``rule_class`` field (e.g. ``MyRule``).
        cls:        The rule class to register.

    Returns:
        None
    """
    RULE_REGISTRY[class_name] = cls
    logger.info("Registered rule class '%s' in registry.", class_name)


def load_uploaded_rules() -> None:
    """Scan ``app/rule_definitions/`` for uploaded rule files and register them.

    Called once at startup so that previously uploaded rules survive restarts.
    Built-in rules (already imported above) are skipped.

    Returns:
        None
    """
    from app.rule_definitions.base_rule import BaseRule

    rules_dir = Path(__file__).parent.parent / "rule_definitions"
    builtin = {
        "base_rule.py", "downtime_rule.py", "oee_rule.py",
        "example_rule.py", "__init__.py",
    }

    for path in sorted(rules_dir.glob("*.py")):
        if path.name in builtin:
            continue
        try:
            spec = importlib.util.spec_from_file_location(path.stem, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for attr_name in dir(module):
                cls = getattr(module, attr_name)
                if (
                    inspect.isclass(cls)
                    and issubclass(cls, BaseRule)
                    and cls is not BaseRule
                    and attr_name not in RULE_REGISTRY
                ):
                    register_rule_class(attr_name, cls)
        except Exception as exc:
            logger.error(
                "Failed to load uploaded rule '%s': %s", path.name, exc
            )

# ── Notifiers ─────────────────────────────────────────────────────────────────
# Key must match the ``notifier_type`` value stored in ``NotifierConfigModel``.

NOTIFIER_REGISTRY: dict[str, type] = {
    "log": LogNotifier,
    "email": EmailNotifier,
    "webhook": WebhookNotifier,
    "desktop": DesktopNotifier,
    "websocket": WebSocketNotifier,
    # "sms": SmsNotifier,                   ← register new notifiers here
}

# ── DataSources ───────────────────────────────────────────────────────────────
# Key must match the ``type`` value in the datasource config JSON.

DATASOURCE_REGISTRY: dict[str, type] = {
    "pocketbase": PocketBaseDataSource,
    "sqlserver": SqlServerDataSource,
    "mongodb": MongoDataSource,
    # "redis": RedisDataSource,             ← register new datasources here
}
