# Codex Project Path Repair

Repair Codex Desktop project chats after a project folder is moved or renamed.

This is for the situation where your old Codex conversations still exist, but the Codex app no longer shows them under the right project after moving the project out of OneDrive, iCloud Drive, Dropbox, Google Drive, or another folder.

## What It Does

Codex stores project paths in several local files, not just one setting. This tool replaces an old absolute project path with the new absolute path across the local Codex state that controls project visibility.

It checks and repairs:

- `state_5.sqlite`, especially `threads.cwd`
- `.codex-global-state.json`
- `config.toml`
- `sessions/**/*.jsonl`
- `archived_sessions/**/*.jsonl`
- `process_manager/chat_processes.json`

It avoids rewriting normal chat text where practical. It focuses on metadata fields such as `cwd`, `sandbox_policy`, and writable roots.

## Safety

- Dry-run is the default.
- Nothing is changed unless you pass `--apply` or confirm in the wizard.
- Backups are created before files are modified.

```text
<codex-home>/path-repair-backups/<timestamp>/
```

Quit Codex before applying a repair. If Codex is still running, it may write old state back from memory.

## Quick Start

1. Quit Codex completely.
2. Run the Windows wizard.
3. Enter the old project folder and the new project folder.
4. Review the dry-run result.
5. Type `YES` only when you are ready to apply changes.

### Windows Wizard

Double-click:

```text
Start-Repair-Windows.cmd
```

or run:

```powershell
.\scripts\Repair-CodexProjectPath.ps1 -Wizard
```

## Direct Commands

Dry run:

```powershell
python .\scripts\codex_path_repair.py `
  --old "C:\Users\YOURNAME\OneDrive\Desktop\Codex Projects\MyProject" `
  --new "C:\Users\YOURNAME\Desktop\Codex Projects\MyProject"
```

Apply:

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

macOS or Linux:

```bash
python3 scripts/codex_path_repair.py \
  --old "/Users/me/Library/Mobile Documents/com~apple~CloudDocs/Codex Projects/MyProject" \
  --new "/Users/me/Codex Projects/MyProject" \
  --apply
```

## Common Path Moves

```text
Old: C:\Users\NAME\OneDrive\Desktop\Codex Projects\PROJECT
New: C:\Users\NAME\Desktop\Codex Projects\PROJECT

Old: C:\Users\NAME\OneDrive\Documents\PROJECT
New: C:\Users\NAME\Documents\PROJECT
```

## Dependencies

Python 3 is required. No packages need to be installed.

The PowerShell wrapper is only a launcher. The repair engine is Python because Codex stores important project metadata in SQLite, and Python includes SQLite support in the standard library.

## Project Website

This repository includes a static landing page at `docs/index.html`.

For GitHub Pages, use the simple branch publisher:

1. Open the repository on GitHub.
2. Go to **Settings**.
3. Go to **Pages**.
4. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
5. Select branch `main` and folder `/docs`.
6. Save.

No GitHub Actions workflow is needed for this static site.

## Verify

After applying, the script prints verification counts. These should be `0`:

```text
remaining_sqlite_old_refs: 0
remaining_global_old_refs: 0
remaining_jsonl_metadata_old_refs: 0
```

Some old path text may remain inside normal chat messages. That is expected and does not usually affect project visibility.

## Notes

- This is for local Codex Desktop state. It does not repair cloud-synced OpenAI account data.
- Treat backups as sensitive. Codex sessions can contain prompts, code, logs, and secrets.
