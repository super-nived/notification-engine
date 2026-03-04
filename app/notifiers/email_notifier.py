"""
Email notifier — sends alert events via SMTP.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.core.exceptions import NotifierError
from app.notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class EmailNotifier(BaseNotifier):
    """Sends an alert email via SMTP for every detected event.

    Args:
        smtp_host:      SMTP server hostname.
        smtp_port:      SMTP server port (typically 587 for STARTTLS).
        username:       SMTP login username.
        password:       SMTP login password.
        from_email:     Sender email address.
        to_email:       Recipient address or list of addresses.
        subject_prefix: Prefix prepended to all email subjects.
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        to_email: str | list[str],
        subject_prefix: str = "[Alert]",
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_email = [to_email] if isinstance(to_email, str) else to_email
        self.subject_prefix = subject_prefix

    def send(self, event: dict[str, Any]) -> None:
        """Send an alert email for the given event.

        Args:
            event: Event dict containing ``rule_name``, ``message``,
                   ``data``, and ``triggered_at``.

        Raises:
            NotifierError: If the SMTP connection or send fails.

        Returns:
            None
        """
        msg = self._build_message(event)
        self._smtp_send(msg)
        logger.info(
            "Email sent to %s for rule '%s'",
            self.to_email,
            event.get("rule_name"),
        )

    def _build_message(self, event: dict[str, Any]) -> MIMEMultipart:
        """Construct the MIME email message from an event dict.

        Args:
            event: Alert event dict.

        Returns:
            Populated ``MIMEMultipart`` message ready to send.
        """
        rule = event.get("rule_name", "unknown")
        message = event.get("message", "")
        data = event.get("data", {})
        triggered_at = event.get("triggered_at", "")

        subject = f"{self.subject_prefix} {rule} — {message}"
        body = (
            f"Rule:         {rule}\n"
            f"Triggered At: {triggered_at}\n"
            f"Message:      {message}\n\n"
            f"Data:\n{data}"
        )

        msg = MIMEMultipart()
        msg["From"] = self.from_email
        msg["To"] = ", ".join(self.to_email)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        return msg

    def _smtp_send(self, msg: MIMEMultipart) -> None:
        """Open an SMTP connection and send the message.

        Args:
            msg: Prepared MIME message to send.

        Raises:
            NotifierError: If the SMTP connection or send fails.
        """
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.from_email, self.to_email, msg.as_string())
        except smtplib.SMTPException as exc:
            raise NotifierError(
                "EmailNotifier", f"SMTP send failed: {exc}"
            ) from exc
