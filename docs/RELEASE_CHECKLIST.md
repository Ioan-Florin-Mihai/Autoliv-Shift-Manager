# Release Checklist

Use this checklist for local Windows releases. The application runtime behavior is not changed by these steps.

## Before Build

- Confirm the working tree is clean or that intentional changes are understood:
  `git status`
- Close the running planner and TV server before replacing the executable.
- Confirm the current production folder has recent local backups in `backups/`.
- Optional: create an external copy:
  `external_backup.cmd "D:\Autoliv_Backups"`

## Build

```powershell
.\build_exe_onefile.cmd
```

Expected output:

- `dist\Autoliv Shift Manager.exe`
- `dist\data\schedule_draft.json`
- `dist\data\schedule_live.json`
- `dist\data\employees.json`
- `dist\data\ui_state.json`
- `dist\data\audit_log.json`

## Post-Build Verification

```powershell
.\verify_build.cmd
```

The verifier is read-only. It checks required files, JSON validity, EXE size, and that sensitive runtime files are not shipped.

Run the read-only production smoke check:

```powershell
.\production_smoke_check.cmd --skip-tv
```

For final station sign-off, use `docs/PRODUCTION_ACCEPTANCE_CHECKLIST.md`.

## Manual Smoke Test

- Start the built executable from `dist`.
- Log in with the expected local credentials.
- Open the planner screen.
- Open the current week.
- Confirm the employee list loads.
- Confirm publish controls are visible for admin.
- Start the TV server or kiosk mode if this release affects display behavior.
- Open `http://127.0.0.1:8000/tv` on the machine running the TV server.

## Update Target Station

Use the existing safe updater:

```powershell
.\update_portable_exe.cmd "dist\Autoliv Shift Manager.exe" "C:\Autoliv\Autoliv Shift Manager.exe"
```

The updater creates an executable backup and attempts restore if replacement fails.

## Rollback

- Stop the app.
- Restore the previous executable backup created by `update_portable_exe.cmd`.
- Do not delete `data/` or `backups/`.
- If data restore is required, follow `docs/BACKUP_AND_RESTORE.md`.
