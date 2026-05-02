# Backup And Restore

The app intentionally uses local JSON persistence. Normal saves and publish operations already use atomic writes and local backups. This document covers extra operational safety.

## Local Backup Files

Runtime data lives beside the executable/project:

- `data\schedule_draft.json`
- `data\schedule_live.json`
- `data\employees.json`
- `data\ui_state.json`
- `data\audit_log.json`
- `data\users.json`
- `backups\schedule_backup_*.json`
- `backups\schedule_daily_*.json`

Do not edit these files while the planner is open.

## Optional External Backup

Run manually when you want a copy outside the app folder:

```powershell
.\external_backup.cmd "D:\Autoliv_Backups"
```

This creates a timestamped folder such as:

```text
D:\Autoliv_Backups\Autoliv_Backup_20260502_181500
```

Safety rules:

- Source files are never deleted.
- Existing app files are never modified.
- Existing external backup folders are not overwritten.
- JSON files are parsed and noted in the manifest.

Dry-run option:

```powershell
.\.venv\Scripts\python.exe tools\external_backup.py "external_backups" --dry-run
```

## Optional Scheduled External Backup

Register a daily Windows Task Scheduler backup only when the target folder is approved:

```powershell
.\register_external_backup_task.cmd "D:\Autoliv_Backups" "22:00"
```

Verify the task command without registering it:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\register_external_backup_task.ps1 -TargetFolder "D:\Autoliv_Backups" -Time "22:00" -WhatIf
```

The scheduled task calls the existing `external_backup.cmd` helper. It remains optional and never deletes source files.

## Restore From Built-In Schedule Backup

Preferred route:

1. Open the planner as admin.
2. Use the app's restore backup workflow.
3. Confirm the restored schedule in planner.
4. Publish again if the TV dashboard should use the restored data.

## Manual Emergency Restore

Use this only if the app cannot open.

1. Close planner and TV server.
2. Copy the current `data\` folder to a safe folder first.
3. Pick the newest valid backup from `backups\schedule_backup_*.json` or `backups\schedule_daily_*.json`.
4. Copy it over `data\schedule_draft.json`.
5. If TV must show the same restored schedule, copy it over `data\schedule_live.json`.
6. Start the planner and verify the week.

Never delete the `backups\` folder during restore.

## Restore Validation

After restore:

- Confirm JSON files open without parse errors using the app or support bundle.
- Confirm employee list is still present.
- Confirm planner opens the target week.
- Confirm locked/published state is expected.
- Confirm TV displays the intended published week.
