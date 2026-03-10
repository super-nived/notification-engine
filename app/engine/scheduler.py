"""
APScheduler setup — loads rules from PocketBase and registers cron jobs.

PocketBase is the single source of truth at runtime. When users edit rule
params or notifier configs via the API, the scheduler reloads that rule
with the updated configuration.
"""

import json
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.exceptions import RuleConfigError, SchedulerError
from app.core.settings import settings
from app.db import pb_repositories as pb
# pb.get_datasource_by_id is used in _build_engine_instance
from app.engine.registry import DATASOURCE_REGISTRY, NOTIFIER_REGISTRY, RULE_REGISTRY
from app.engine.runner import run_rule

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()


# ── Public API ────────────────────────────────────────────────────────────────


def start_scheduler() -> None:
    """Load all enabled rules from PocketBase and start APScheduler.

    Returns:
        None
    """
    _load_all_rules()
    _scheduler.start()
    logger.info("Scheduler started with %d job(s)", len(_scheduler.get_jobs()))


def stop_scheduler() -> None:
    """Shut down APScheduler without waiting for running jobs.

    Returns:
        None
    """
    _scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


def reload_rule(rule_name: str) -> None:
    """Remove and re-register a single rule job from PocketBase.

    Called by the rules service after a rule's params or schedule
    have been updated via the API.

    Args:
        rule_name: Unique name of the rule to reload.

    Returns:
        None
    """
    _remove_job(rule_name)
    try:
        rule = pb.get_rule_by_name(rule_name)
        if rule and rule.get("enabled"):
            _register_job(rule)
    except Exception as exc:
        logger.error("Failed to reload rule '%s': %s", rule_name, exc)


def get_scheduler() -> BackgroundScheduler:
    """Return the global APScheduler instance for inspection.

    Returns:
        The module-level ``BackgroundScheduler``.
    """
    return _scheduler


# ── Internal helpers ──────────────────────────────────────────────────────────


def _load_all_rules() -> None:
    """Load all enabled rules from PocketBase and register their jobs.

    Returns:
        None
    """
    try:
        rules = pb.get_enabled_rules()
    except Exception as exc:
        logger.error("Failed to load rules from PocketBase: %s", exc)
        return

    for rule in rules:
        try:
            _register_job(rule)
        except (RuleConfigError, SchedulerError) as exc:
            logger.error("Skipping rule '%s': %s", rule.get("name"), exc)


def _register_job(rule: dict) -> None:
    """Build a rule instance from a PocketBase domain dict and schedule it.

    Args:
        rule: Rule domain dict from ``pb_repositories``.

    Raises:
        RuleConfigError: If the rule class or datasource is unknown.
        SchedulerError:  If the cron expression is invalid.

    Returns:
        None
    """
    rule_instance = _build_rule_instance(rule)
    trigger = _build_trigger(rule["name"], rule["schedule"])

    _scheduler.add_job(
        run_rule,
        trigger=trigger,
        args=[rule_instance],
        id=rule["name"],
        replace_existing=True,
        name=rule["name"],
    )
    logger.info("Registered rule '%s' @ %s", rule["name"], rule["schedule"])


def _build_rule_instance(rule: dict) -> object:
    """Instantiate a rule from a domain dict.

    Supports two modes:
    - Structured (Grafana model): ``datasource_id`` is set — builds a
      ``RuleEngine`` instance from the structured condition fields.
    - Legacy class-based: ``rule_class`` is set — instantiates the
      registered Python class with ``params_json`` as keyword args.

    Args:
        rule: Rule domain dict from ``pb_repositories``.

    Returns:
        Instantiated rule ready to be scheduled.

    Raises:
        RuleConfigError: If the class / datasource type is unknown.
    """
    notifier_configs = pb.get_notifiers_for_rule(rule["id"])
    notifiers = _build_notifiers(notifier_configs)

    # ── Structured mode ───────────────────────────────────────────────────────
    if rule.get("datasource_id"):
        return _build_engine_instance(rule, notifiers)

    # ── Legacy class-based mode ───────────────────────────────────────────────
    rule_cls = RULE_REGISTRY.get(rule.get("rule_class", ""))
    if not rule_cls:
        raise RuleConfigError(
            f"Rule class '{rule.get('rule_class')}' not in registry."
        )

    params = rule.get("params_json") or {}
    datasource = _build_datasource(params)

    rule_params = {
        k: v for k, v in params.items()
        if k not in (
            "datasource_type", "url", "admin_email", "admin_password",
            "state_file",
        )
    }
    instance = rule_cls(datasource=datasource, notifiers=notifiers, **rule_params)
    # Override the class-level name with the PocketBase record name so that
    # execution logs and last_run_at updates use the correct rule identifier.
    instance.name = rule["name"]
    return instance


def _build_engine_instance(rule: dict, notifiers: list) -> object:
    """Build a RuleEngine instance from a structured rule domain dict.

    Args:
        rule:      Rule domain dict with datasource_id and condition fields.
        notifiers: Pre-built list of notifier instances.

    Returns:
        Configured ``RuleEngine`` instance.

    Raises:
        RuleConfigError: If the datasource is not found or type unknown.
    """
    from app.engine.rule_engine import RuleEngine

    datasource_record = pb.get_datasource_by_id(rule["datasource_id"])
    if not datasource_record:
        raise RuleConfigError(
            f"Datasource id '{rule['datasource_id']}' not found for rule '{rule['name']}'."
        )

    from app.features.datasources.service import _build_connector
    datasource = _build_connector(datasource_record)

    instance = RuleEngine(
        datasource=datasource,
        notifiers=notifiers,
        collection_name=rule.get("collection_name", ""),
        condition_type=rule.get("condition_type", "new_record"),
        condition_field=rule.get("condition_field", ""),
        condition_op=rule.get("condition_op", "eq"),
        condition_value=rule.get("condition_value", ""),
        condition_extra=rule.get("condition_extra") or {},
    )
    instance.name = rule["name"]
    return instance


def _build_datasource(params: dict) -> object:
    """Build a datasource instance from rule params.

    Args:
        params: Rule params dict containing ``datasource_type`` and
                any connection credentials.

    Returns:
        Instantiated datasource object.

    Raises:
        RuleConfigError: If the datasource type is not registered.
    """
    ds_type = params.get("datasource_type", "pocketbase")
    cls = DATASOURCE_REGISTRY.get(ds_type)
    if not cls:
        raise RuleConfigError(f"Datasource type '{ds_type}' not in registry.")

    if ds_type == "pocketbase":
        return cls(
            url=params.get("url", settings.PB_URL),
            admin_email=params.get("admin_email", settings.PB_ADMIN_EMAIL),
            admin_password=params.get("admin_password", settings.PB_ADMIN_PASSWORD),
        )
    if ds_type == "sqlserver":
        return cls(
            connection_string=params.get(
                "connection_string", settings.SQLSERVER_CONNECTION_STRING
            )
        )
    if ds_type == "mongodb":
        return cls(
            uri=params.get("uri", settings.MONGO_URI),
            database=params.get("database", settings.MONGO_DB),
        )
    raise RuleConfigError(f"No builder defined for datasource '{ds_type}'.")


def _build_notifiers(notifier_configs: list[dict]) -> list:
    """Build notifier instances from domain config dicts.

    Args:
        notifier_configs: List of notifier config domain dicts.

    Returns:
        List of instantiated notifier objects. Unknown types are skipped.
    """
    notifiers = []
    for config in notifier_configs:
        n_type = config.get("notifier_type", "")
        cls = NOTIFIER_REGISTRY.get(n_type)
        if not cls:
            logger.warning("Unknown notifier type '%s', skipping.", n_type)
            continue
        cfg = json.loads(config.get("config_json") or "{}")
        notifiers.append(_instantiate_notifier(cls, n_type, cfg))
    return notifiers


def _instantiate_notifier(cls: type, n_type: str, cfg: dict) -> object:
    """Instantiate a single notifier from its class and config dict.

    Args:
        cls:    Notifier class from the registry.
        n_type: Notifier type key string.
        cfg:    Config dict parsed from ``config_json``.

    Returns:
        Instantiated notifier object.
    """
    if n_type == "log":
        return cls(path=cfg.get("path", f"{settings.LOG_DIR}/alerts.log"))
    if n_type == "email":
        return cls(
            smtp_host=cfg.get("smtp_host", settings.SMTP_HOST),
            smtp_port=cfg.get("smtp_port", settings.SMTP_PORT),
            username=cfg.get("username", settings.SMTP_USER),
            password=cfg.get("password", settings.SMTP_PASSWORD),
            from_email=cfg.get("from_email", settings.EMAIL_FROM),
            to_email=cfg.get("to") or cfg.get("to_email") or settings.EMAIL_TO,
            subject_prefix=cfg.get("subject_prefix", "[Alert]"),
        )
    if n_type == "webhook":
        return cls(url=cfg.get("url", settings.WEBHOOK_URL))
    if n_type == "desktop":
        return cls(timeout_ms=cfg.get("timeout_ms", 5000))
    if n_type == "websocket":
        return cls()
    if n_type == "nats":
        return cls(
            url=cfg.get("url", "nats://localhost:4222"),
            subject=cfg.get("subject", "alerts.notification_engine"),
        )
    return cls(**cfg)


def _build_trigger(rule_name: str, schedule: str) -> CronTrigger:
    """Parse a cron expression into an APScheduler CronTrigger.

    Args:
        rule_name: Used in the error message if parsing fails.
        schedule:  Cron expression string, e.g. ``* * * * *``.

    Returns:
        ``CronTrigger`` instance.

    Raises:
        SchedulerError: If the cron expression is invalid.
    """
    try:
        return CronTrigger.from_crontab(schedule)
    except Exception as exc:
        raise SchedulerError(
            rule_name, f"Invalid cron expression '{schedule}': {exc}"
        ) from exc


def _remove_job(rule_name: str) -> None:
    """Remove a scheduled job by rule name if it exists.

    Args:
        rule_name: Job ID to remove (equals rule name).

    Returns:
        None
    """
    job = _scheduler.get_job(rule_name)
    if job:
        job.remove()
        logger.info("Removed scheduled job for rule '%s'", rule_name)
