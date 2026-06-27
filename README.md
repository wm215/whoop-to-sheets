# whoop-to-sheets

Cloud-hosted automation for the **Revamp** training/recovery Google Sheet.

## What it does

- **Morning Health Pull** — daily 7 AM ET. Pulls last night's WHOOP recovery, sleep duration, HRV, and resting heart rate; appends a row to the `WHOOP` tab. Powers the recovery hero card on the Dashboard.
- **Status Logger** — every 15 min. Reads `Dashboard!B15` (the workout-status dropdown). When it sees a non-default value (`✅ Completed`, `⏭ Skipped`, `🦴 Active recovery`, `🔧 Modified`), it upserts today's row into the hidden `_WorkoutLog` tab. The "Owed Workouts" counter on the Dashboard recalculates from that log.

Both run on GitHub Actions — no Mac required.

## Sheet

`1TxbgCTrtp1Owuqxpu2Hi7dVkPAUFQsNaaeKQqxWOQh4` — the only sheet this pipeline touches.

## Secrets (set via `gh secret set`)

- `WHOOP_CLIENT_ID`, `WHOOP_CLIENT_SECRET`, `WHOOP_REFRESH_TOKEN`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`

The Google OAuth refresh token must have `https://www.googleapis.com/auth/spreadsheets` scope.
If `morning-health` logs `invalid_grant`, run `python reauth_google.py` locally and update `GOOGLE_REFRESH_TOKEN`.

## Manual trigger

```bash
gh workflow run morning-health.yml
gh workflow run status-logger.yml
```

## Local run (debug)

Set the same env vars locally, then `python morning_health.py` or `python status_logger.py`.
