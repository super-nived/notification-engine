"""
APScheduler setup — loads rules from the DB and registers cron jobs.

The DB is the single source of truth at runtime. Config.yaml is only
used during initial seeding. When users edit rule params via the API,
the scheduler reloads that rule with the updated configuration.
"""

import json
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.exceptions import RuleConfigError, SchedulerError
from app.core.settings import settings
from app.db.engine import SessionLocal
from app.db import repositories as repo
from app.engine.registry import DATASOURCE_REGISTRY, NOTIFIER_REGISTRY, RULE_REGISTRY
from app.engine.runner import run_rule

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()


# ── Public API ────────────────────────────────────────────────────────────────


def start_scheduler() -> None:
    """Load all enabled rules from the DB and start APScheduler.

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
    """Remove and re-register a single rule job from the DB.

    Called by the rules service after a rule's params or schedule
    have been updated via the API.

    Args:
        rule_name: Unique name of the rule to reload.

    Returns:
        None
    """
    _remove_job(rule_name)
    db = SessionLocal()
    try:
        rule_row = repo.get_rule_by_name(db, rule_name)
        if rule_row and rule_row.enabled:
            _register_job(rule_row)
    finally:
        db.close()


def get_scheduler() -> BackgroundScheduler:
    """Return the global APScheduler instance for inspection.

    Returns:
        The module-level ``BackgroundScheduler``.
    """
    return _scheduler


# ── Internal helpers ──────────────────────────────────────────────────────────


def _load_all_rules() -> None:
    """Load all enabled rules from the DB and register their jobs.

    Returns:
        None
    """
    db = SessionLocal()
    try:
        rules = repo.get_enabled_rules(db)
        for rule_row in rules:
            try:
                _register_job(rule_row)
            except (RuleConfigError, SchedulerError) as exc:
                logger.error("Skipping rule '%s': %s", rule_row.name, exc)
    finally:
        db.close()


def _register_job(rule_row: object) -> None:
    """Build a rule instance from a DB row and add it to APScheduler.

    Args:
        rule_row: ``RuleModel`` instance from the database.

    Raises:
        RuleConfigError: If the rule class or datasource is unknown.
        SchedulerError:  If the cron expression is invalid.

    Returns:
        None
    """
    rule_instance = _build_rule_instance(rule_row)
    trigger = _build_trigger(rule_row.name, rule_row.schedule)

    _scheduler.add_job(
        run_rule,
        trigger=trigger,
        args=[rule_instance, SessionLocal()],
        id=rule_row.name,
        replace_existing=True,
        name=rule_row.name,
    )
    logger.info("Registered rule '%s' @ %s", rule_row.name, rule_row.schedule)


def _build_rule_instance(rule_row: object) -> object:
    """Instantiate a rule class from a DB row.

    Args:
        rule_row: ``RuleModel`` instance containing class name, params,
                  and notifier configs.

    Returns:
        Instantiated rule ready to be scheduled.

    Raises:
        RuleConfigError: If the rule class or datasource type is unknown.
    """
    rule_cls = RULE_REGISTRY.get(rule_row.rule_class)
    if not rule_cls:
        raise RuleConfigError(
            f"Rule class '{rule_row.rule_class}' not in registry."
        )

    params = json.loads(rule_row.params_json or "{}")
    datasource = _build_datasource(params)
    notifiers = _build_notifiers(rule_row.notifiers)

    rule_params = {
        k: v for k, v in params.items()
        if k not in ("datasource_type", "url", "admin_email", "admin_password")
    }
    return rule_cls(datasource=datasource, notifiers=notifiers, **rule_params)


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


def _build_notifiers(notifier_rows: list) -> list:
    """Build notifier instances from ``NotifierConfigModel`` rows.

    Args:
        notifier_rows: List of ``NotifierConfigModel`` ORM instances.

    Returns:
        List of instantiated notifier objects. Unknown types are skipped.
    """
    notifiers = []
    for row in notifier_rows:
        cls = NOTIFIER_REGISTRY.get(row.notifier_type)
        if not cls:
            logger.warning("Unknown notifier type '%s', skipping.", row.notifier_type)
            continue
        cfg = json.loads(row.config_json or "{}")
        notifiers.append(_instantiate_notifier(cls, row.notifier_type, cfg))
    return notifiers


def _instantiate_notifier(cls: type, n_type: str, cfg: dict) -> object:
    """Instantiate a single notifier from its class and config dict.

    Args:
        cls:    Notifier class from the registry.
        n_type: Notifier type key string.
        cfg:    Config dict from ``NotifierConfigModel.config_json``.

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
