# Codex Project Path Repair

Repair local Codex Desktop project chat history after moving or renaming project folders.

This fixes the common case where Codex project chats disappear, detach from a project, or vanish from the sidebar after moving a project out of OneDrive, iCloud Drive, Dropbox, or another synced folder.

## What It Fixes

Codex stores project paths in more than one place:

- `state_5.sqlite`, especially `threads.cwd`
- `state_5.sqlite`, especially `threads.sandbox_policy`
- `.codex-global-state.json`
- `config.toml`
- `sessions/**/*.jsonl`
- `archived_sessions/**/*.jsonl`
- `process_manager/chat_processes.json`

Updating only the visible folder path is not enough. When Codex opens an old thread, it can rehydrate stale workspace metadata from SQLite or rollout JSONL files. If those still point at the old folder, the sidebar can lose the project association.

## Safety

The repair script is dry-run by default.

It only writes changes when you pass `--apply`.

When applying, it creates backups before modifying files:

```text
<codex-home>/path-repair-backups/<timestamp>/
```

## Quick Start

1. Quit Codex completely.
2. Open PowerShell or Terminal.
3. Use the wizard or run a dry run first.

### Easiest Windows Option

Double-click:

```text
Start-Repair-Windows.cmd
```

or run:

```powershell
.\scripts\Repair-CodexProjectPath.ps1 -Wizard
```

The wizard asks for the old folder and new folder, runs a dry-run scan, then asks you to type `YES` before applying changes.

### Direct Commands

Windows example:

```powershell
python .\scripts\codex_path_repair.py `
  --old "C:\Users\YOURNAME\OneDrive\Desktop\Codex Projects\MyProject" `
  --new "C:\Users\YOURNAME\Desktop\Codex Projects\MyProject"
```

Apply after reviewing the dry-run output:

```powershell
python .\scripts\codex_path_repair.py `
  --old "C:\Users\YOURNAME\OneDrive\Desktop\Codex Projects\MyProject" `
  --new "C:\Users\YOURNAME\Desktop\Codex Projects\MyProject" `
  --apply
```

PowerShell wrapper:

```powershell
.\scripts\Repair-CodexProjectPath.ps1 `
  -OldPath "C:\Users\YOURNAME\OneDrive\Desktop\Codex Projects\MyProject" `
  -NewPath "C:\Users\YOURNAME\Desktop\Codex Projects\MyProject" `
  -Apply
```

macOS/Linux example:

```bash
python3 scripts/codex_path_repair.py \
  --old "/Users/me/Library/Mobile Documents/com~apple~CloudDocs/Codex Projects/MyProject" \
  --new "/Users/me/Codex Projects/MyProject" \
  --apply
```

4. Reopen Codex.

## OneDrive Migration Examples

Desktop project:

```text
Old: C:\Users\NAME\OneDrive\Desktop\Codex Projects\PROJECT
New: C:\Users\NAME\Desktop\Codex Projects\PROJECT
```

Documents project:

```text
Old: C:\Users\NAME\OneDrive\Documents\PROJECT
New: C:\Users\NAME\Documents\PROJECT
```

## What The Script Changes

The script updates path metadata in:

- SQLite `threads.cwd`
- SQLite `threads.sandbox_policy`
- global saved workspace roots
- global project order
- global active workspace roots
- thread workspace hints
- project output directory hints
- sidebar collapsed project group keys
- trusted project entries in `config.toml`
- JSONL session metadata fields such as `cwd`, `sandbox_policy`, and `writable_roots`
- process manager `cwd` values

It avoids rewriting normal chat text where practical. In JSONL files, it parses each event and only updates likely metadata fields, not arbitrary message content.

## Dependencies

The repair engine requires Python 3, but uses only the standard library. No `pip install` is needed.

Used standard-library modules:

- `sqlite3`
- `json`
- `pathlib`
- `shutil`
- `argparse`

The PowerShell wrapper is provided for Windows users, but a complete PowerShell-only repair is not realistic without an external SQLite provider because Codex stores thread/project metadata in `state_5.sqlite`.

## GitHub Pages

This repo includes a landing page in `docs/index.html`.

The included workflow at `.github/workflows/pages.yml` deploys the `docs/` folder with GitHub Actions.

The public page URL will usually be:

```text
https://YOUR_USERNAME.github.io/codex-project-path-repair/
```

If GitHub asks you to enable Pages manually:

1. Open the repository settings.
2. Go to **Pages**.
3. Set source to **GitHub Actions**.
4. Run the **Deploy GitHub Pages** workflow.

## Verify

After applying, the script prints verification counts. These should be zero:

```text
remaining_sqlite_old_refs: 0
remaining_global_old_refs: 0
remaining_jsonl_metadata_old_refs: 0
```

Some old path text may remain inside normal chat messages. That is expected and does not usually affect project visibility.

## Important Notes

- Quit Codex before applying. If Codex is running, it may rewrite stale state from memory.
- This is for local Codex Desktop state. It does not repair cloud-synced OpenAI account data.
- Treat backups as sensitive. Codex sessions can contain prompts, code, logs, and secrets.
