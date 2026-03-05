/**
 * Service Worker — Web Push Notification handler.
 *
 * Receives push events from the server and renders them as
 * structured OS notifications with action buttons.
 */

const APP_NAME   = "Rule Engine";
const ICON_URL   = "https://cdn-icons-png.flaticon.com/512/1828/1828843.png";
const BADGE_URL  = "https://cdn-icons-png.flaticon.com/512/1828/1828843.png";

// ── Push received ─────────────────────────────────────────────────────────────

self.addEventListener("push", function (event) {
  const data = _parsePushData(event);
  const options = _buildNotificationOptions(data);
  event.waitUntil(
    self.registration.showNotification(_buildTitle(data), options)
  );
});


// ── Notification clicked ──────────────────────────────────────────────────────

self.addEventListener("notificationclick", function (event) {
  event.notification.close();

  if (event.action === "dismiss") return;

  const url = (event.notification.data && event.notification.data.url)
    ? event.notification.data.url
    : "/dashboard";

  event.waitUntil(_focusOrOpenDashboard(url));
});


// ── Helpers ───────────────────────────────────────────────────────────────────

function _parsePushData(event) {
  try {
    return event.data ? event.data.json() : {};
  } catch (_) {
    return {
      title: APP_NAME,
      body: event.data ? event.data.text() : "An alert was triggered.",
    };
  }
}

function _buildTitle(data) {
  const rule = data.title || data.rule_name || APP_NAME;
  return "⚠️  " + _toTitleCase(rule);
}

function _buildNotificationOptions(data) {
  const body       = data.body        || "An alert was triggered.";
  const summary    = data.summary     || "";
  const triggeredAt = data.triggered_at
    ? _formatDate(data.triggered_at)
    : _formatDate(new Date().toISOString());

  // Body lines: message, optional summary, timestamp
  const bodyLines = [body];
  if (summary) bodyLines.push(summary);
  bodyLines.push("🕐 " + triggeredAt);

  const tag = "rule-alert-" + (data.rule_name || "engine")
    .toLowerCase()
    .replace(/\s+/g, "-");

  return {
    body:             bodyLines.join("\n"),
    icon:             ICON_URL,
    badge:            BADGE_URL,
    tag:              tag,
    renotify:         true,
    vibrate:          [200, 100, 200],
    requireInteraction: true,
    timestamp:        data.triggered_at
                        ? new Date(data.triggered_at).getTime()
                        : Date.now(),
    actions: [
      { action: "view",    title: "View Dashboard" },
      { action: "dismiss", title: "Dismiss"         },
    ],
    data: {
      url:          data.url || "/dashboard",
      rule_name:    data.rule_name || "",
      triggered_at: data.triggered_at || "",
    },
  };
}

function _focusOrOpenDashboard(url) {
  return clients
    .matchAll({ type: "window", includeUncontrolled: true })
    .then(function (clientList) {
      for (const client of clientList) {
        if (client.url.includes("/dashboard") && "focus" in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(url);
    });
}

function _formatDate(iso) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month:  "short",
      day:    "numeric",
      hour:   "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch (_) {
    return iso;
  }
}

function _toTitleCase(str) {
  return str
    .replace(/[-_]/g, " ")
    .replace(/\w\S*/g, w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());
}
