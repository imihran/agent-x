"""Task 9 — Toolkit CLI contract tests (README Section 14.7 / 14.8).

Exercises the tool-layer output contract: JSON on stdout for success and
error, exit codes 0/1, retryable+hint on every error, read-back
verification on every write, `discover` surface completeness against the
live parser/COMMANDS, and `authcheck`'s read-only guarantee.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLKIT_PY = ROOT / "tool" / "toolkit" / "toolkit.py"


def run_cli(store: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "TOOLKIT_STORE": str(store)}
    return subprocess.run(
        [sys.executable, str(TOOLKIT_PY), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def load_toolkit_module():
    """Fresh module instance for white-box tests that monkeypatch read_back."""
    spec = importlib.util.spec_from_file_location("toolkit_under_test", TOOLKIT_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── JSON-on-stdout / exit-code contract ──────────────────────────────────

def test_list_success_is_json_on_stdout_with_exit_zero(tmp_path):
    store = tmp_path / "store.json"
    result = run_cli(store, "list")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["items"] == []


def test_get_missing_id_is_json_error_with_exit_one_retryable_and_hint(tmp_path):
    store = tmp_path / "store.json"
    result = run_cli(store, "get", "--id", "nonexistent")
    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert isinstance(payload["retryable"], bool)
    assert isinstance(payload["hint"], str) and payload["hint"]
    assert "error" in payload


# ── create/update/delete read-back verification ──────────────────────────

def test_create_persists_and_is_verified_by_read_back(tmp_path):
    store = tmp_path / "store.json"
    result = run_cli(store, "create", "--name", "widget", "--value", "1")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["verified"] == "read-back"
    item_id = payload["item"]["id"]

    fetched = json.loads(run_cli(store, "get", "--id", item_id).stdout)
    assert fetched["item"]["name"] == "widget"
    assert fetched["item"]["value"] == 1


def test_update_persists_new_value_and_is_verified_by_read_back(tmp_path):
    store = tmp_path / "store.json"
    created = json.loads(
        run_cli(store, "create", "--name", "widget", "--value", "1").stdout
    )
    item_id = created["item"]["id"]

    result = run_cli(store, "update", "--id", item_id, "--value", "42")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["verified"] == "read-back"
    assert payload["item"]["value"] == 42

    fetched = json.loads(run_cli(store, "get", "--id", item_id).stdout)
    assert fetched["item"]["value"] == 42


def test_delete_removes_item_and_is_verified_by_read_back(tmp_path):
    store = tmp_path / "store.json"
    created = json.loads(
        run_cli(store, "create", "--name", "widget", "--value", "1").stdout
    )
    item_id = created["item"]["id"]

    result = run_cli(store, "delete", "--id", item_id)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["deleted"] == item_id
    assert payload["verified"] == "read-back"

    fetched = json.loads(run_cli(store, "get", "--id", item_id).stdout)
    assert fetched["ok"] is False


# ── write failure must report failure, never success ─────────────────────

def test_create_reports_failure_when_store_path_is_blocked(tmp_path):
    """The store's parent path is a plain file, so save_store's mkdir fails
    and the write must report failure — simulated broken persistence."""
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")
    store = blocker / "store.json"

    result = run_cli(store, "create", "--name", "widget", "--value", "1")
    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert isinstance(payload["retryable"], bool)
    assert isinstance(payload["hint"], str) and payload["hint"]


@pytest.mark.parametrize("command_name", ["create", "update", "delete"])
def test_write_reports_failure_when_read_back_is_shadowed(
    tmp_path, monkeypatch, capsys, command_name
):
    """White-box: force read_back to disagree with what was just written,
    simulating a shadowed store, and confirm the write reports failure
    rather than claiming success from the in-memory attempt alone."""
    module = load_toolkit_module()
    module.STORE = tmp_path / "store.json"

    if command_name == "create":
        monkeypatch.setattr(module, "read_back", lambda item_id: None)
        exit_code = module.cmd_create(Namespace(name="widget", value=1))
    elif command_name == "update":
        module.save_store(
            {"items": {"abc": {"id": "abc", "name": "widget", "value": 1}}}
        )
        monkeypatch.setattr(
            module,
            "read_back",
            lambda item_id: {"id": "abc", "name": "widget", "value": 1},
        )
        exit_code = module.cmd_update(Namespace(id="abc", value=42))
    else:
        module.save_store(
            {"items": {"abc": {"id": "abc", "name": "widget", "value": 1}}}
        )
        monkeypatch.setattr(
            module,
            "read_back",
            lambda item_id: {"id": "abc", "name": "widget", "value": 1},
        )
        exit_code = module.cmd_delete(Namespace(id="abc"))

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["ok"] is False
    assert isinstance(payload["retryable"], bool)
    assert isinstance(payload["hint"], str) and payload["hint"]


# ── discover completeness ────────────────────────────────────────────────

def test_discover_surface_matches_parser_and_commands(tmp_path):
    store = tmp_path / "store.json"
    result = run_cli(store, "discover")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    surface = {entry["command"]: entry for entry in payload["surface"]}

    module = load_toolkit_module()
    parser = module.build_parser()
    sub = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    parser_commands = set(sub.choices)

    assert set(surface) == parser_commands
    assert set(surface) == set(module.COMMANDS)

    expected_writes = {"create", "update", "delete"}
    for name, entry in surface.items():
        assert entry["write"] == (name in expected_writes)


# ── authcheck is read-only ────────────────────────────────────────────────

def test_authcheck_does_not_modify_store_bytes(tmp_path):
    store = tmp_path / "store.json"
    run_cli(store, "create", "--name", "widget", "--value", "1")
    before = store.read_bytes()

    result = run_cli(store, "authcheck")
    payload = json.loads(result.stdout)

    after = store.read_bytes()
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["transport"] == "read-proven"
    assert after == before
