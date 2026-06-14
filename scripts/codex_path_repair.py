#!/usr/bin/env python3
"""
Repair Codex Desktop local project path metadata after moving a project.

Dry-run by default. Pass --apply to write changes.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
from typing import Any


METADATA_KEYS = {
    "cwd",
    "sandbox_policy",
    "writable_roots",
    "workspace_roots",
    "workspace_root",
    "active-workspace-roots",
    "electron-saved-workspace-roots",
    "project-order",
    "thread-workspace-root-hints",
    "thread-projectless-output-directories",
}


def default_codex_home() -> Path:
    home = Path.home()
    return home / ".codex"


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def path_variants(path: str) -> list[str]:
    """Return literal and escaped variants found in Codex state files."""
    variants = {path}
    if os.name == "nt":
        variants.add(path.replace("/", "\\"))
    variants.add(json.dumps(path)[1:-1])
    variants.add(json.dumps(json.dumps(path)[1:-1])[1:-1])
    # Some command/history fields can contain double-nested escaping.
    backslash = "\\"
    if backslash in path:
        for count in (2, 4, 8):
            variants.add(path.replace(backslash, backslash * count))
    return sorted(variants, key=len, reverse=True)


def replacement_pairs(old: str, new: str) -> list[tuple[str, str]]:
    old_vars = path_variants(old)
    pairs: list[tuple[str, str]] = []
    for old_var in old_vars:
        slash_count = 1
        i = old_var.find("\\")
        if i >= 0:
            slash_count = 0
            while i + slash_count < len(old_var) and old_var[i + slash_count] == "\\":
                slash_count += 1
        pairs.append((old_var, new.replace("\\", "\\" * max(1, slash_count))))
    # Config.toml project keys are often lower-case on Windows.
    pairs.append((old.lower(), new.lower()))
    return pairs


def replace_path_text(text: str, pairs: list[tuple[str, str]]) -> str:
    out = text
    for old, new in pairs:
        out = out.replace(old, new)
    return out


def backup_file(path: Path, codex_home: Path, backup_root: Path) -> Path:
    try:
        rel = path.relative_to(codex_home)
    except ValueError:
        rel = Path(path.name)
    dest = backup_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    return dest


def update_selected_json(value: Any, pairs: list[tuple[str, str]], key: str | None = None) -> tuple[Any, int]:
    """Recursively update strings only under metadata-like keys."""
    changes = 0
    if isinstance(value, dict):
        new_obj = {}
        for k, v in value.items():
            new_key = replace_path_text(k, pairs) if k in METADATA_KEYS or any(old in k for old, _ in pairs) else k
            should_update = k in METADATA_KEYS or key in METADATA_KEYS
            if should_update:
                new_v, c = update_all_strings(v, pairs)
            else:
                new_v, c = update_selected_json(v, pairs, k)
            if new_key != k:
                c += 1
            new_obj[new_key] = new_v
            changes += c
        return new_obj, changes
    if isinstance(value, list):
        new_list = []
        for item in value:
            if key in METADATA_KEYS:
                new_item, c = update_all_strings(item, pairs)
            else:
                new_item, c = update_selected_json(item, pairs, key)
            new_list.append(new_item)
            changes += c
        return new_list, changes
    if isinstance(value, str) and key in METADATA_KEYS:
        new_value = replace_path_text(value, pairs)
        return new_value, int(new_value != value)
    return value, 0


def update_all_strings(value: Any, pairs: list[tuple[str, str]]) -> tuple[Any, int]:
    changes = 0
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            nk = replace_path_text(k, pairs)
            nv, c = update_all_strings(v, pairs)
            out[nk] = nv
            changes += c + int(nk != k)
        return out, changes
    if isinstance(value, list):
        out = []
        for item in value:
            ni, c = update_all_strings(item, pairs)
            out.append(ni)
            changes += c
        return out, changes
    if isinstance(value, str):
        nv = replace_path_text(value, pairs)
        return nv, int(nv != value)
    return value, 0


def repair_sqlite(codex_home: Path, pairs: list[tuple[str, str]], apply: bool, backup_root: Path | None) -> dict[str, int]:
    db = codex_home / "state_5.sqlite"
    result = {
        "sqlite_exists": int(db.exists()),
        "sqlite_cwd_changes": 0,
        "sqlite_sandbox_policy_changes": 0,
        "remaining_sqlite_old_refs": 0,
    }
    if not db.exists():
        return result

    if apply and backup_root:
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(db) + suffix)
            if p.exists():
                backup_file(p, codex_home, backup_root)

    uri = f"file:{db}?mode={'rw' if apply else 'ro'}"
    con = sqlite3.connect(uri, uri=True, timeout=30)
    try:
        cur = con.cursor()
        cur.execute("SELECT id, cwd, sandbox_policy FROM threads")
        rows = cur.fetchall()
        for thread_id, cwd, sandbox_policy in rows:
            new_cwd = replace_path_text(cwd or "", pairs) if cwd is not None else None
            new_sandbox = replace_path_text(sandbox_policy or "", pairs) if sandbox_policy is not None else None
            if new_cwd != cwd:
                result["sqlite_cwd_changes"] += 1
                if apply:
                    cur.execute("UPDATE threads SET cwd=? WHERE id=?", (new_cwd, thread_id))
            if new_sandbox != sandbox_policy:
                result["sqlite_sandbox_policy_changes"] += 1
                if apply:
                    cur.execute("UPDATE threads SET sandbox_policy=? WHERE id=?", (new_sandbox, thread_id))
        if apply:
            con.commit()

        old_checks = [old for old, _ in pairs[:4]]
        remaining = 0
        cur.execute("SELECT cwd, sandbox_policy FROM threads")
        for cwd, sandbox_policy in cur.fetchall():
            blob = (cwd or "") + "\n" + (sandbox_policy or "")
            if any(old in blob for old in old_checks):
                remaining += 1
        result["remaining_sqlite_old_refs"] = remaining
    finally:
        con.close()
    return result


def repair_global_state(codex_home: Path, pairs: list[tuple[str, str]], apply: bool, backup_root: Path | None) -> dict[str, int]:
    path = codex_home / ".codex-global-state.json"
    result = {"global_exists": int(path.exists()), "global_changes": 0, "remaining_global_old_refs": 0}
    if not path.exists():
        return result

    data = json.loads(path.read_text(encoding="utf-8"))
    new_data = copy.deepcopy(data)

    for key in ("electron-saved-workspace-roots", "project-order", "active-workspace-roots"):
        if key in new_data:
            new_data[key], c = update_all_strings(new_data[key], pairs)
            result["global_changes"] += c

    for key in ("thread-workspace-root-hints", "thread-projectless-output-directories"):
        if key in new_data:
            new_data[key], c = update_all_strings(new_data[key], pairs)
            result["global_changes"] += c

    atom = new_data.get("electron-persisted-atom-state")
    if isinstance(atom, dict) and isinstance(atom.get("sidebar-collapsed-groups"), dict):
        atom["sidebar-collapsed-groups"], c = update_all_strings(atom["sidebar-collapsed-groups"], pairs)
        result["global_changes"] += c

    encoded = json.dumps(new_data, separators=(",", ":"), ensure_ascii=False)
    old_markers = [old for old, _ in pairs[:4]]
    relevant = json.dumps(
        {
            "roots": new_data.get("electron-saved-workspace-roots"),
            "order": new_data.get("project-order"),
            "active": new_data.get("active-workspace-roots"),
            "hints": new_data.get("thread-workspace-root-hints"),
        },
        ensure_ascii=False,
    )
    result["remaining_global_old_refs"] = int(any(old in relevant for old in old_markers))

    if apply and result["global_changes"]:
        if backup_root:
            backup_file(path, codex_home, backup_root)
        path.write_text(encoded, encoding="utf-8")
    return result


def repair_config(codex_home: Path, pairs: list[tuple[str, str]], apply: bool, backup_root: Path | None) -> dict[str, int]:
    path = codex_home / "config.toml"
    result = {"config_exists": int(path.exists()), "config_changes": 0}
    if not path.exists():
        return result
    text = path.read_text(encoding="utf-8")
    new_text = replace_path_text(text, pairs)
    result["config_changes"] = int(new_text != text)
    if apply and new_text != text:
        if backup_root:
            backup_file(path, codex_home, backup_root)
        path.write_text(new_text, encoding="utf-8")
    return result


def repair_process_manager(codex_home: Path, pairs: list[tuple[str, str]], apply: bool, backup_root: Path | None) -> dict[str, int]:
    path = codex_home / "process_manager" / "chat_processes.json"
    result = {"process_manager_exists": int(path.exists()), "process_manager_changes": 0}
    if not path.exists():
        return result
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return result
    new_data, changes = update_selected_json(data, pairs)
    result["process_manager_changes"] = changes
    if apply and changes:
        if backup_root:
            backup_file(path, codex_home, backup_root)
        path.write_text(json.dumps(new_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def repair_jsonl(codex_home: Path, pairs: list[tuple[str, str]], apply: bool, backup_root: Path | None) -> dict[str, int]:
    result = {"jsonl_files_seen": 0, "jsonl_files_changed": 0, "remaining_jsonl_metadata_old_refs": 0}
    roots = [codex_home / "sessions", codex_home / "archived_sessions"]
    old_markers = [old for old, _ in pairs[:4]]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.jsonl"):
            result["jsonl_files_seen"] += 1
            changed = False
            new_lines: list[str] = []
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines:
                if not line.strip():
                    new_lines.append(line)
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    new_lines.append(line)
                    continue
                new_event, c = update_selected_json(event, pairs)
                if c:
                    changed = True
                    new_lines.append(json.dumps(new_event, separators=(",", ":"), ensure_ascii=False))
                else:
                    new_lines.append(line)

                # Verification: metadata only, not normal message content.
                metadata_probe = {}
                if isinstance(new_event, dict):
                    payload = new_event.get("payload")
                    if isinstance(payload, dict):
                        for k in METADATA_KEYS:
                            if k in payload:
                                metadata_probe[k] = payload[k]
                    if "cwd" in new_event:
                        metadata_probe["cwd"] = new_event["cwd"]
                if any(old in json.dumps(metadata_probe, ensure_ascii=False) for old in old_markers):
                    result["remaining_jsonl_metadata_old_refs"] += 1

            if changed:
                result["jsonl_files_changed"] += 1
                if apply:
                    if backup_root:
                        backup_file(path, codex_home, backup_root)
                    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair local Codex project path metadata.")
    parser.add_argument("--old", required=True, help="Old absolute project path.")
    parser.add_argument("--new", required=True, help="New absolute project path.")
    parser.add_argument("--codex-home", default=str(default_codex_home()), help="Path to .codex directory.")
    parser.add_argument("--apply", action="store_true", help="Write changes. Default is dry-run.")
    args = parser.parse_args()

    old = args.old.rstrip("\\/")
    new = args.new.rstrip("\\/")
    codex_home = Path(args.codex_home).expanduser()

    if old == new:
        print("Old and new paths are identical; nothing to do.", file=sys.stderr)
        return 2
    if not codex_home.exists():
        print(f"Codex home does not exist: {codex_home}", file=sys.stderr)
        return 2

    pairs = replacement_pairs(old, new)
    backup_root = None
    if args.apply:
        backup_root = codex_home / "path-repair-backups" / timestamp()
        backup_root.mkdir(parents=True, exist_ok=True)

    print("mode:", "APPLY" if args.apply else "DRY-RUN")
    print("codex_home:", codex_home)
    print("old:", old)
    print("new:", new)
    if backup_root:
        print("backup_root:", backup_root)

    results: dict[str, int] = {}
    for fn in (repair_sqlite, repair_global_state, repair_config, repair_process_manager, repair_jsonl):
        results.update(fn(codex_home, pairs, args.apply, backup_root))

    print("\nResults")
    for key in sorted(results):
        print(f"{key}: {results[key]}")

    if not args.apply:
        print("\nDry run only. Re-run with --apply to write changes.")
    else:
        print("\nDone. Reopen Codex after verifying the counts above.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

