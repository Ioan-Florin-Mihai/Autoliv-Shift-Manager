# Production Acceptance Checklist

Use this checklist on the final production PC and TV setup before considering a release accepted.

## Build Folder

- Run `verify_build.cmd`.
- Run `production_smoke_check.cmd --skip-tv`.
- Confirm `dist\Autoliv Shift Manager.exe` exists.
- Confirm `dist\data\users.json` is not present in the release folder.
- Confirm `dist\data\planner.lock` and `dist\logs\system.log` are not present in the release folder.

## Planner PC

- Start the EXE from the intended production folder.
- Log in with the expected internal credentials.
- Confirm the planner opens without errors.
- Open the current week.
- Confirm employees load.
- Confirm existing local backups are visible or present under `backups\`.
- Do not change schedule data during acceptance unless the operator/admin explicitly approves it.

## Backup And Support

- Run an external backup to the approved target folder:
  `external_backup.cmd "D:\Autoliv_Backups"`
- Confirm a timestamped backup folder was created.
- Run `generate_support_bundle.cmd`.
- Confirm a zip file appears under `support_bundles\`.

## TV Setup

- Start the TV server or kiosk mode using the normal station procedure.
- Open `http://127.0.0.1:8000/health` on the TV server machine.
- Open `http://127.0.0.1:8000/tv` locally.
- Open `http://<LAN_IP>:8000/tv` from a TV/client device.
- Confirm the TV page shows the expected published week.

## Final Sign-Off

- Confirm planner, backup, support bundle, and TV checks passed.
- Confirm rollback executable backup exists if an update was performed.
- Record release version, date, and operator/admin who accepted the release.
