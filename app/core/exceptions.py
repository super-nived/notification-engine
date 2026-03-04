"""
Custom exception classes for the Notification Rule Engine.

All application-level errors are defined here. Never raise bare
``Exception`` — always raise one of these so handlers can map them
to the correct HTTP status code and log message.
"""


class RuleNotFoundError(Exception):
    """Raised when a requested rule does not exist in the database.

    Args:
        rule_id: The ID that was looked up and not found.
    """

    def __init__(self, rule_id: int) -> None:
        super().__init__(f"Rule with id={rule_id} not found.")
        self.rule_id = rule_id


class RuleConfigError(Exception):
    """Raised when a rule configuration is invalid.

    Examples: unknown rule class name, missing required parameter.

    Args:
        message: Human-readable description of what is wrong.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class DataSourceError(Exception):
    """Raised when a data source connection or fetch operation fails.

    Args:
        source: Name of the datasource (e.g. ``pocketbase``).
        message: Description of the failure.
    """

    def __init__(self, source: str, message: str) -> None:
        super().__init__(f"DataSource '{source}' error: {message}")
        self.source = source


class NotifierError(Exception):
    """Raised when a notifier fails to deliver an alert.

    Args:
        notifier: Class name of the failing notifier.
        message: Description of the failure.
    """

    def __init__(self, notifier: str, message: str) -> None:
        super().__init__(f"Notifier '{notifier}' error: {message}")
        self.notifier = notifier


class NotifierConfigNotFoundError(Exception):
    """Raised when a notifier config record does not exist.

    Args:
        config_id: The notifier config ID that was not found.
    """

    def __init__(self, config_id: int) -> None:
        super().__init__(f"NotifierConfig with id={config_id} not found.")
        self.config_id = config_id


class SchedulerError(Exception):
    """Raised when the APScheduler fails to register or reload a job.

    Args:
        rule_name: Name of the rule being scheduled.
        message: Description of the failure.
    """

    def __init__(self, rule_name: str, message: str) -> None:
        super().__init__(f"Scheduler error for rule '{rule_name}': {message}")
        self.rule_name = rule_name
