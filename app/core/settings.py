"""
Application settings loaded from environment variables via pydantic-settings.

All configuration values are centralised here. No other module reads
``os.environ`` or ``.env`` directly — they import ``settings`` from here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from the ``.env`` file.

    Attributes:
        APP_NAME:   Human-readable application name.
        APP_ENV:    Runtime environment (``development`` / ``production``).
        APP_PORT:   Port for the uvicorn server.
        DB_PATH:    File path for the internal SQLite database.
        PB_URL:     Base URL of the PocketBase instance.
        PB_ADMIN_EMAIL:     PocketBase admin email.
        PB_ADMIN_PASSWORD:  PocketBase admin password.
        SQLSERVER_CONNECTION_STRING: pyodbc connection string for SQL Server.
        MONGO_URI:  MongoDB connection URI.
        MONGO_DB:   MongoDB database name.
        SMTP_HOST:  SMTP server hostname.
        SMTP_PORT:  SMTP server port.
        SMTP_USER:  SMTP login username.
        SMTP_PASSWORD: SMTP login password.
        ALERT_FROM_EMAIL: Sender address for alert emails.
        ALERT_TO_EMAIL:   Default recipient for alert emails.
        WEBHOOK_URL: Default webhook URL for alert POSTs.
        STATE_DIR:  Directory where rule state files are stored.
        LOG_DIR:    Directory where alert log files are written.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "Notification Rule Engine"
    APP_ENV: str = "development"
    APP_PORT: int = 8000

    # Internal DB
    DB_PATH: str = "./engine.db"

    # PocketBase
    PB_URL: str = ""
    PB_ADMIN_EMAIL: str = ""
    PB_ADMIN_PASSWORD: str = ""

    # SQL Server (optional)
    SQLSERVER_CONNECTION_STRING: str = ""

    # MongoDB (optional)
    MONGO_URI: str = ""
    MONGO_DB: str = ""

    # Email / SMTP (optional)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: bool = True
    EMAIL_FROM: str = ""
    EMAIL_TO: str = ""

    # Webhook (optional)
    WEBHOOK_URL: str = ""

    # Paths
    STATE_DIR: str = "./state"
    LOG_DIR: str = "./logs"


settings = Settings()
