"""
Email template builder — renders alert events as clean HTML emails.

Single responsibility: this module converts an event dict into
a user-friendly HTML string and a plain-text fallback. It knows
nothing about SMTP, connections, or delivery — only presentation.

Hidden internal fields (``id``, ``created``, ``updated``, etc.)
are excluded so users only see meaningful alert information.
"""

from datetime import datetime
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────────

# Keys excluded from the data table — internal / technical fields
_HIDDEN_KEYS = frozenset({
    "id", "created", "updated",
    "collectionId", "collectionName", "expand",
})

# Human-friendly labels for common data field keys
_FIELD_LABELS: dict[str, str] = {
    "machine_name":  "Machine",
    "machine_id":    "Machine ID",
    "reason_code":   "Reason",
    "start_date":    "Start Time",
    "end_date":      "End Time",
    "duration":      "Duration",
    "oee":           "OEE (%)",
    "shift":         "Shift",
    "job_status":    "Job Status",
    "isScheduled":   "Scheduled",
    "jobStatus":     "Job Status",
    "displayName":   "Display Name",
    "status":        "Status",
}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _label(key: str) -> str:
    """Return a human-friendly label for a data field key.

    Looks up ``_FIELD_LABELS`` first; falls back to title-casing
    with underscores and hyphens replaced by spaces.

    Args:
        key: Raw field key string from the event data dict.

    Returns:
        Formatted label string suitable for display.
    """
    if key in _FIELD_LABELS:
        return _FIELD_LABELS[key]
    return key.replace("_", " ").replace("-", " ").title()


def _format_value(value: Any) -> str:
    """Format a single data value for display.

    Converts ``None`` to a dash, booleans to Yes/No, and
    everything else to its string representation.

    Args:
        value: Raw value from the event data dict.

    Returns:
        User-friendly string representation.
    """
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _format_timestamp(triggered_at: str) -> str:
    """Parse an ISO-8601 timestamp into a readable display string.

    Args:
        triggered_at: ISO-8601 timestamp string from the event.

    Returns:
        Formatted string like ``"Mar 10, 2026 at 02:30 PM UTC"``,
        or the raw string if parsing fails.
    """
    if not triggered_at:
        return "—"
    try:
        dt = datetime.fromisoformat(triggered_at.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y at %I:%M %p UTC")
    except (ValueError, TypeError):
        return triggered_at


def _visible_fields(data: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract user-relevant field pairs from the event data dict.

    Filters out internal keys defined in ``_HIDDEN_KEYS`` and
    returns (label, formatted_value) tuples.

    Args:
        data: Raw data dict from the event.

    Returns:
        List of (label, value) string tuples.
    """
    if not isinstance(data, dict):
        return []
    return [
        (_label(k), _format_value(v))
        for k, v in data.items()
        if k not in _HIDDEN_KEYS
    ]


# ── Public API ───────────────────────────────────────────────────────────────


def build_plain_text(event: dict[str, Any]) -> str:
    """Build a plain-text email body from an event dict.

    Used as the fallback for email clients that do not render HTML.

    Args:
        event: Alert event dict with ``rule_name``, ``message``,
               ``data``, and ``triggered_at``.

    Returns:
        Multi-line plain-text string.
    """
    message = event.get("message", "")
    data = event.get("data", {})
    time_str = _format_timestamp(event.get("triggered_at", ""))

    lines = [message, ""]
    for label, value in _visible_fields(data):
        lines.append(f"  {label}: {value}")
    lines.append("")
    lines.append(f"Time: {time_str}")
    lines.append("")
    lines.append("— Notification Rule Engine")
    return "\n".join(lines)


def build_html(event: dict[str, Any]) -> str:
    """Build a professional HTML email body from an event dict.

    Renders a clean, responsive email template with:
    - Orange header bar with rule name
    - Alert message in a highlighted block
    - Data fields as a readable two-column table
    - Timestamp footer

    No raw JSON, no technical field names, no internal IDs.

    Args:
        event: Alert event dict with ``rule_name``, ``message``,
               ``data``, and ``triggered_at``.

    Returns:
        Complete HTML document string ready for ``MIMEText``.
    """
    rule = event.get("rule_name", "Alert")
    message = event.get("message", "")
    data = event.get("data", {})
    time_str = _format_timestamp(event.get("triggered_at", ""))

    # ── Data rows ────────────────────────────────────────────────────
    data_rows = ""
    fields = _visible_fields(data)
    for label, value in fields:
        data_rows += (
            "<tr>"
            '<td style="padding:10px 16px;font-size:13px;color:#6b7280;'
            "border-bottom:1px solid #f0f0f0;white-space:nowrap;"
            f'font-weight:500">{label}</td>'
            '<td style="padding:10px 16px;font-size:13px;color:#1e2535;'
            f'border-bottom:1px solid #f0f0f0">{value}</td>'
            "</tr>"
        )

    data_table = ""
    if data_rows:
        data_table = (
            '<table width="100%" cellpadding="0" cellspacing="0" '
            'style="border:1px solid #e5e7eb;border-radius:8px;'
            'overflow:hidden;border-collapse:separate;margin-top:20px">'
            f"<tbody>{data_rows}</tbody></table>"
        )

    # ── Full HTML ────────────────────────────────────────────────────
    return (
        "<!DOCTYPE html>"
        "<html><head>"
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        "</head>"
        '<body style="margin:0;padding:0;background:#f5f6fa;'
        "font-family:'Segoe UI',Arial,Helvetica,sans-serif\">"
        '<table width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#f5f6fa;padding:32px 0"><tr><td align="center">'

        # Card container
        '<table width="560" cellpadding="0" cellspacing="0" '
        'style="background:#ffffff;border-radius:12px;overflow:hidden;'
        'box-shadow:0 2px 8px rgba(0,0,0,0.06)">'

        # ── Header ──────────────────────────────────────────────────
        "<tr><td style=\"background:#e15a2d;padding:24px 32px\">"
        '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        "<td>"
        '<div style="font-size:18px;font-weight:700;color:#ffffff;'
        'letter-spacing:0.3px">Alert Notification</div>'
        '<div style="font-size:12px;color:rgba(255,255,255,0.80);'
        f'margin-top:4px">{_esc(rule)}</div>'
        "</td>"
        '<td align="right" style="vertical-align:top">'
        '<div style="background:rgba(255,255,255,0.20);border-radius:20px;'
        "padding:5px 14px;font-size:11px;color:#ffffff;font-weight:600;"
        'display:inline-block">New Alert</div>'
        "</td>"
        "</tr></table>"
        "</td></tr>"

        # ── Body ────────────────────────────────────────────────────
        '<tr><td style="padding:28px 32px 16px">'

        # Alert message block
        '<div style="background:#fef3f0;border-left:4px solid #e15a2d;'
        'border-radius:0 8px 8px 0;padding:14px 18px;margin-bottom:4px">'
        '<div style="font-size:14px;color:#1e2535;line-height:1.6;'
        f'font-weight:500">{_esc(message)}</div>'
        "</div>"

        # Data table
        f"{data_table}"

        "</td></tr>"

        # ── Footer ──────────────────────────────────────────────────
        '<tr><td style="padding:0 32px 28px">'
        '<table width="100%" cellpadding="0" cellspacing="0" '
        'style="border-top:1px solid #f0f0f0;padding-top:16px"><tr>'
        '<td style="font-size:11px;color:#9ca3af;line-height:1.6">'
        f"Triggered on {_esc(time_str)}</td>"
        '<td align="right" style="font-size:11px;color:#9ca3af">'
        "Notification Rule Engine</td>"
        "</tr></table>"
        "</td></tr>"

        "</table>"  # end card

        # Unsubscribe hint
        '<div style="text-align:center;margin-top:20px;font-size:11px;'
        'color:#9ca3af;line-height:1.5">'
        "This is an automated alert from your Notification Rule Engine.<br>"
        "To stop receiving these, disable the rule or remove the email notifier."
        "</div>"

        "</td></tr></table>"
        "</body></html>"
    )


def _esc(text: str) -> str:
    """Escape HTML special characters to prevent injection.

    Args:
        text: Raw string to escape.

    Returns:
        HTML-safe string with ``&``, ``<``, ``>`` replaced.
    """
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
