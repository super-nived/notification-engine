"""
Registry maps for rules, notifiers, and data sources.

When you add a new rule, notifier, or datasource:
1. Import the class below under the correct registry section.
2. Add an entry to the corresponding dict.

The scheduler and service layer look up classes by their string key.
"""

from app.datasources.mongodb import MongoDataSource
from app.datasources.pocketbase import PocketBaseDataSource
from app.datasources.sqlserver import SqlServerDataSource
from app.notifiers.desktop_notifier import DesktopNotifier
from app.notifiers.email_notifier import EmailNotifier
from app.notifiers.log_notifier import LogNotifier
from app.notifiers.webhook_notifier import WebhookNotifier
from app.rule_definitions.downtime_rule import DowntimeRule
from app.rule_definitions.example_rule import ExampleRule
from app.rule_definitions.oee_rule import OEERule

# ── Rules ─────────────────────────────────────────────────────────────────────
# Key must match the ``rule_class`` value stored in ``RuleModel``.

RULE_REGISTRY: dict[str, type] = {
    "DowntimeRule": DowntimeRule,
    "OEERule": OEERule,
    "ExampleRule": ExampleRule,
    # "MachineStopRule": MachineStopRule,   ← register new rules here
}

# ── Notifiers ─────────────────────────────────────────────────────────────────
# Key must match the ``notifier_type`` value stored in ``NotifierConfigModel``.

NOTIFIER_REGISTRY: dict[str, type] = {
    "log": LogNotifier,
    "email": EmailNotifier,
    "webhook": WebhookNotifier,
    "desktop": DesktopNotifier,
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
