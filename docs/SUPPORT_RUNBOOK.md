# Support Runbook

Use this when the app behaves unexpectedly and you need a support package.

## Generate Support Bundle

```powershell
.\generate_support_bundle.cmd
```

Output is written under:

```text
support_bundles\
```

The bundle includes:

- environment metadata
- git commit/status if available
- JSON file validity summary
- sanitized copies of JSON files
- recent log tail

Recognized secrets are redacted where possible:

- `api_key`
- `password`
- `password_hash`

## What To Check Before Escalating

- Is the planner already open on another machine/session?
- Does `data\planner.lock` remain after all app windows are closed?
- Does `logs\system.log` contain recent errors?
- Are `data\schedule_draft.json` and `data\schedule_live.json` valid JSON?
- Does `backups\` contain recent schedule backups?
- Is the TV server running on the expected machine and port?

## What Not To Send

Avoid sending raw production files unless explicitly needed:

- `data\users.json`
- full `data\employees.json`
- full schedule files with personal data

Prefer the generated support bundle first.
