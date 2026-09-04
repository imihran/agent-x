#!/usr/bin/env python3
"""toolkit — demonstration tool-layer CLI over a local JSON store.

Implements the agent tool contract:
  * JSON on stdout for success AND error; exit 0/1
  * errors carry retryable (bool) and hint (str)
  * writes are marked "⚠️ WRITE" in help line one and READ BACK to verify
  * `discover` emits the machine-readable surface inventory
  * `authcheck` proves the store READ transport with a real read — it never
    writes (read-only allowlists admit it, so a write would falsify them)

Store location: $TOOLKIT_STORE or ~/.agent-toolkit/store.json
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

STORE = Path(os.environ.get("TOOLKIT_STORE", "")) if os.environ.get(
    "TOOLKIT_STORE") else Path.home() / ".agent-toolkit" / "store.json"


def ok(payload: dict) -> int:
    print(json.dumps({"ok": True, **payload}, indent=2, sort_keys=True))
    return 0


def err(message: str, *, retryable: bool, hint: str) -> int:
    print(json.dumps({"ok": False, "error": message, "retryable": retryable,
                      "hint": hint}, indent=2, sort_keys=True))
    return 1


class StoreError(Exception):
    """Store unreadable or corrupt — reported as contract JSON, never a
    traceback (14.3: JSON on stdout for success AND error)."""


def load_store() -> dict:
    if not STORE.is_file():
        return {"items": {}}
    try:
        store = json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StoreError(f"store unreadable: {exc}") from exc
    if not isinstance(store.get("items"), dict):
        raise StoreError("store has no 'items' object — corrupt or foreign file")
    return store


def save_store(store: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STORE)  # atomic replace (os.replace semantics on all platforms)


def read_back(item_id: str) -> dict | None:
    """Re-read the store from disk and return the item — the write-verify step.
    Claiming success from the in-memory dict would be claiming durability
    from an attempt."""
    return load_store()["items"].get(item_id)


# ── subcommands ──────────────────────────────────────────────────────────

def cmd_list(_: argparse.Namespace) -> int:
    """List all items in the store."""
    return ok({"items": list(load_store()["items"].values())})


def cmd_get(args: argparse.Namespace) -> int:
    """Get one item by id."""
    item = load_store()["items"].get(args.id)
    if item is None:
        return err(f"no item with id {args.id}", retryable=False,
                   hint="run `toolkit list` to see valid ids")
    return ok({"item": item})


def cmd_search(args: argparse.Namespace) -> int:
    """Search items by substring on name."""
    hits = [i for i in load_store()["items"].values()
            if args.query.lower() in i["name"].lower()]
    return ok({"items": hits, "count": len(hits)})


def cmd_create(args: argparse.Namespace) -> int:
    """⚠️ WRITE — create an item, then read back to verify it persisted."""
    store = load_store()
    item_id = uuid.uuid4().hex[:12]
    store["items"][item_id] = {"id": item_id, "name": args.name,
                               "value": args.value}
    try:
        save_store(store)
    except OSError as exc:
        return err(f"store write failed: {exc}", retryable=False,
                   hint="check permissions on the store path — writes get "
                        "one attempt (14.4); do not blind-retry")
    verified = read_back(item_id)
    if verified is None:
        return err("write did not persist (read-back returned nothing)",
                   retryable=False,
                   hint="the store may be shadowed by TOOLKIT_STORE — check it")
    return ok({"item": verified, "verified": "read-back"})


def cmd_update(args: argparse.Namespace) -> int:
    """⚠️ WRITE — update an item's value, then read back to verify."""
    store = load_store()
    if args.id not in store["items"]:
        return err(f"no item with id {args.id}", retryable=False,
                   hint="run `toolkit list` to see valid ids")
    store["items"][args.id]["value"] = args.value
    try:
        save_store(store)
    except OSError as exc:
        return err(f"store write failed: {exc}", retryable=False,
                   hint="check permissions on the store path")
    verified = read_back(args.id)
    if verified is None or verified["value"] != args.value:
        return err("write did not persist (read-back mismatch)",
                   retryable=False, hint="inspect the store file directly")
    return ok({"item": verified, "verified": "read-back"})


def cmd_delete(args: argparse.Namespace) -> int:
    """⚠️ WRITE — delete an item, then read back to verify it is gone."""
    store = load_store()
    if args.id not in store["items"]:
        return err(f"no item with id {args.id}", retryable=False,
                   hint="already absent — nothing to delete")
    del store["items"][args.id]
    try:
        save_store(store)
    except OSError as exc:
        return err(f"store write failed: {exc}", retryable=False,
                   hint="check permissions on the store path")
    if read_back(args.id) is not None:
        return err("delete did not persist (read-back still present)",
                   retryable=False, hint="inspect the store file directly")
    return ok({"deleted": args.id, "verified": "read-back"})


def cmd_discover(_: argparse.Namespace) -> int:
    """Emit the surface inventory. Any subcommand reachable from this CLI is
    registered here — an unregistered group is invisible to the caller."""
    parser = build_parser()
    sub = next(a for a in parser._actions
               if isinstance(a, argparse._SubParsersAction))
    inventory = []
    for name, p in sorted(sub.choices.items()):
        fn = COMMANDS.get(name)
        if fn is None:
            return err(f"subcommand '{name}' is on the parser but has no "
                       "handler in COMMANDS — the two surfaces drifted",
                       retryable=False,
                       hint="register the handler; an unregistered group is "
                            "invisible or broken to callers")
        inventory.append({
            "command": name,
            "usage": p.format_usage().strip(),
            "help": (fn.__doc__ or "").strip().splitlines()[0],
            "write": "⚠️ WRITE" in (fn.__doc__ or ""),
        })
    return ok({"surface": inventory})


def cmd_authcheck(_: argparse.Namespace) -> int:
    """Prove the store READ transport with a real read (open and parse).

    Read-only BY DESIGN (P8): a probe that writes would make every
    "read-only" allowlist that admits it a lie. The write path is proven
    by the first real write's read-back verify (14.3), never by a probe —
    so this command honestly reports the write path as unproven.
    """
    try:
        items = load_store()["items"]
    except StoreError as exc:
        return err(f"store transport UNPROVEN: {exc}", retryable=False,
                   hint="inspect the store file directly")
    return ok({"transport": "read-proven",
               "write_path": "unproven until first verified write",
               "store": str(STORE), "items": len(items)})


COMMANDS = {
    "list": cmd_list, "get": cmd_get, "search": cmd_search,
    "create": cmd_create, "update": cmd_update, "delete": cmd_delete,
    "discover": cmd_discover, "authcheck": cmd_authcheck,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="toolkit", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all items")
    p = sub.add_parser("get", help="Get one item by id")
    p.add_argument("--id", required=True)
    p = sub.add_parser("search", help="Search items by name substring")
    p.add_argument("--query", required=True)
    p = sub.add_parser("create", help="⚠️ WRITE — create an item (read-back verified)")
    p.add_argument("--name", required=True)
    p.add_argument("--value", type=int, required=True)
    p = sub.add_parser("update", help="⚠️ WRITE — update an item (read-back verified)")
    p.add_argument("--id", required=True)
    p.add_argument("--value", type=int, required=True)
    p = sub.add_parser("delete", help="⚠️ WRITE — delete an item (read-back verified)")
    p.add_argument("--id", required=True)
    sub.add_parser("discover", help="Emit the surface inventory (machine-readable)")
    sub.add_parser("authcheck", help="Prove the store READ transport (read-only probe, never writes)")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return COMMANDS[args.command](args)
    except StoreError as exc:
        return err(str(exc), retryable=False,
                   hint=f"inspect the store file at {STORE}")


if __name__ == "__main__":
    sys.exit(main())
