"""
Standalone script to create notification-engine collections in PocketBase.

Collections created:
  - ASWNDUBAI_rules
  - ASWNDUBAI_notifier_configs
  - ASWNDUBAI_execution_logs

Run:
    python create_collections.py
"""

import sys
import requests

# ── Config ─────────────────────────────────────────────────────────────────────
PB_URL         = "https://pb.dev.industryapps.net/ASWN"
ADMIN_EMAIL    = "abhi-s@industryapps.net"
ADMIN_PASSWORD = "Linux@1994"

COLLECTIONS = [
    {
        "name": "ASWNDUBAI_rules",
        "type": "base",
        "schema": [
            {"name": "name",        "type": "text", "required": True,  "unique": True,  "options": {}},
            {"name": "rule_class",  "type": "text", "required": True,  "unique": False, "options": {}},
            {"name": "schedule",    "type": "text", "required": True,  "unique": False, "options": {}},
            {"name": "description", "type": "text", "required": False, "unique": False, "options": {}},
            {"name": "enabled",     "type": "bool", "required": False, "unique": False, "options": {}},
            {"name": "params_json", "type": "json", "required": False, "unique": False, "options": {}},
            {"name": "last_run_at", "type": "text", "required": False, "unique": False, "options": {}},
            {"name": "last_status", "type": "text", "required": False, "unique": False, "options": {}},
            {"name": "state",       "type": "json", "required": False, "unique": False, "options": {}},
        ],
        "listRule":   None,
        "viewRule":   None,
        "createRule": None,
        "updateRule": None,
        "deleteRule": None,
    },
    {
        "name": "ASWNDUBAI_notifier_configs",
        "type": "base",
        "schema": [
            {"name": "rule_id",       "type": "text", "required": True,  "unique": False, "options": {}},
            {"name": "notifier_type", "type": "text", "required": True,  "unique": False, "options": {}},
            {"name": "config_json",   "type": "text", "required": False, "unique": False, "options": {}},
        ],
        "listRule":   None,
        "viewRule":   None,
        "createRule": None,
        "updateRule": None,
        "deleteRule": None,
    },
    {
        "name": "ASWNDUBAI_execution_logs",
        "type": "base",
        "schema": [
            {"name": "rule_name",    "type": "text",   "required": True,  "unique": False, "options": {}},
            {"name": "started_at",   "type": "text",   "required": False, "unique": False, "options": {}},
            {"name": "finished_at",  "type": "text",   "required": False, "unique": False, "options": {}},
            {"name": "status",       "type": "text",   "required": False, "unique": False, "options": {}},
            {"name": "events_count", "type": "number", "required": False, "unique": False, "options": {}},
            {"name": "error",        "type": "text",   "required": False, "unique": False, "options": {}},
        ],
        "listRule":   None,
        "viewRule":   None,
        "createRule": None,
        "updateRule": None,
        "deleteRule": None,
    },
]


# ── Auth ────────────────────────────────────────────────────────────────────────

def authenticate() -> str:
    print("Authenticating with PocketBase...")
    resp = requests.post(
        f"{PB_URL}/api/admins/auth-with-password",
        json={"identity": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=10,
    )
    if not resp.ok:
        print(f"  ERROR: Auth failed — {resp.status_code} {resp.text}")
        sys.exit(1)
    token = resp.json()["token"]
    print("  OK: Authenticated.\n")
    return token


# ── Create collections ──────────────────────────────────────────────────────────

def create_collection(token: str, collection: dict) -> None:
    name = collection["name"]
    resp = requests.post(
        f"{PB_URL}/api/collections",
        headers={"Authorization": f"Bearer {token}"},
        json=collection,
        timeout=10,
    )
    if resp.status_code == 200 or resp.status_code == 201:
        print(f"  OK: Created '{name}'")
    elif resp.status_code == 400 and "already exists" in resp.text:
        print(f"  SKIP: '{name}' already exists")
    else:
        print(f"  ERROR: '{name}' — {resp.status_code} {resp.text}")


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    token = authenticate()
    print("Creating collections...")
    for col in COLLECTIONS:
        create_collection(token, col)
    print("\nDone.")


if __name__ == "__main__":
    main()
