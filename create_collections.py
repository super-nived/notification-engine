"""
Standalone script to create / migrate notification-engine collections in PocketBase.

Operations:
  - CREATE ASWNDUBAI_datasources  (new collection for saved connections)
  - PATCH  ASWNDUBAI_rules        (add structured condition fields if missing)
  - CREATE ASWNDUBAI_notifier_configs   (skip if exists)
  - CREATE ASWNDUBAI_execution_logs     (skip if exists)

Run:
    python3 create_collections.py
"""

import sys
import requests

# ── Config ─────────────────────────────────────────────────────────────────────
PB_URL         = "https://pb.dev.industryapps.net/OCCDUBAI"
ADMIN_EMAIL    = "abhi-s@industryapps.net"
ADMIN_PASSWORD = "Linux@1994"

# PocketBase field helpers with correct options format
_TEXT = lambda name, required=False, unique=False: {
    "name": name, "type": "text", "required": required, "unique": unique,
    "options": {"min": None, "max": None, "pattern": ""},
}
_JSON = lambda name: {
    "name": name, "type": "json", "required": False, "unique": False,
    "options": {"maxSize": 2000000},
}
_BOOL = lambda name: {"name": name, "type": "bool",   "required": False, "unique": False, "options": {}}
_NUM  = lambda name: {"name": name, "type": "number", "required": False, "unique": False, "options": {}}

# ── Collections to CREATE (skipped if already exists) ──────────────────────────
NEW_COLLECTIONS = [
    {
        "name": "ASWNDUBAI_datasources",
        "type": "base",
        "schema": [
            _TEXT("name", required=True, unique=True),
            _TEXT("type", required=True),
            _JSON("config"),
        ],
        "listRule": None, "viewRule": None,
        "createRule": None, "updateRule": None, "deleteRule": None,
    },
    {
        "name": "ASWNDUBAI_rules",
        "type": "base",
        "schema": [
            _TEXT("name",        required=True, unique=True),
            _TEXT("rule_class"),
            _TEXT("schedule",    required=True),
            _TEXT("description"),
            _BOOL("enabled"),
            _JSON("params_json"),
            _TEXT("last_run_at"),
            _TEXT("last_status"),
            _JSON("state"),
            _TEXT("datasource_id"),
            _TEXT("collection_name"),
            _TEXT("condition_type"),
            _TEXT("condition_field"),
            _TEXT("condition_op"),
            _TEXT("condition_value"),
            _JSON("condition_extra"),
        ],
        "listRule": None, "viewRule": None,
        "createRule": None, "updateRule": None, "deleteRule": None,
    },
    {
        "name": "ASWNDUBAI_notifier_configs",
        "type": "base",
        "schema": [
            _TEXT("rule_id",       required=True),
            _TEXT("notifier_type", required=True),
            _TEXT("config_json"),
        ],
        "listRule": None, "viewRule": None,
        "createRule": None, "updateRule": None, "deleteRule": None,
    },
    {
        "name": "ASWNDUBAI_execution_logs",
        "type": "base",
        "schema": [
            _TEXT("rule_name",  required=True),
            _TEXT("started_at"),
            _TEXT("finished_at"),
            _TEXT("status"),
            _NUM("events_count"),
            _TEXT("error"),
        ],
        "listRule": None, "viewRule": None,
        "createRule": None, "updateRule": None, "deleteRule": None,
    },
]

# ── Fields to add to ASWNDUBAI_rules if the collection already exists ──────────
RULES_NEW_FIELDS = [
    _TEXT("datasource_id"),
    _TEXT("collection_name"),
    _TEXT("condition_type"),
    _TEXT("condition_field"),
    _TEXT("condition_op"),
    _TEXT("condition_value"),
    _JSON("condition_extra"),
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


# ── Helpers ─────────────────────────────────────────────────────────────────────

def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get_collection(token: str, name: str) -> dict | None:
    """Return the collection dict if it exists, else None."""
    resp = requests.get(
        f"{PB_URL}/api/collections/{name}",
        headers=headers(token),
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def create_collection(token: str, collection: dict) -> None:
    name = collection["name"]
    existing = get_collection(token, name)

    if existing:
        if name == "ASWNDUBAI_rules":
            _patch_rules_schema(token, existing)
        else:
            print(f"  SKIP: '{name}' already exists")
        return

    resp = requests.post(
        f"{PB_URL}/api/collections",
        headers=headers(token),
        json=collection,
        timeout=10,
    )
    if resp.ok:
        print(f"  OK: Created '{name}'")
    else:
        print(f"  ERROR: '{name}' — {resp.status_code} {resp.text}")


def _patch_rules_schema(token: str, existing: dict) -> None:
    """Add any missing condition fields to the existing ASWNDUBAI_rules collection."""
    current_names = {f["name"] for f in existing.get("schema", [])}
    missing = [f for f in RULES_NEW_FIELDS if f["name"] not in current_names]

    if not missing:
        print("  SKIP: 'ASWNDUBAI_rules' already has all condition fields")
        return

    updated_schema = existing["schema"] + missing
    resp = requests.patch(
        f"{PB_URL}/api/collections/{existing['id']}",
        headers=headers(token),
        json={"schema": updated_schema},
        timeout=10,
    )
    if resp.ok:
        added = [f["name"] for f in missing]
        print(f"  OK: Patched 'ASWNDUBAI_rules' — added fields: {added}")
    else:
        print(f"  ERROR: Patch 'ASWNDUBAI_rules' — {resp.status_code} {resp.text}")


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    token = authenticate()
    print("Setting up collections...")
    for col in NEW_COLLECTIONS:
        create_collection(token, col)
    print("\nDone.")


if __name__ == "__main__":
    main()
