#!/usr/bin/env python3
"""Dashboard status logger — cloud version.

Polls Dashboard!B15 every 15 min via GitHub Actions cron. Upserts today's row
in _WorkoutLog so the Owed counter on Dashboard stays accurate.

Stateless: uses _WorkoutLog itself as truth ("did today's row change?").

Credentials from env: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN.
"""
import os
from datetime import date

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SHEET_ID = "1TxbgCTrtp1Owuqxpu2Hi7dVkPAUFQsNaaeKQqxWOQh4"
SKIP_VALUES = {"", "⏳ Not done yet"}


def sheets_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def main() -> None:
    svc = sheets_service()

    res = svc.spreadsheets().values().batchGet(
        spreadsheetId=SHEET_ID,
        ranges=["'Dashboard'!B15", "'Dashboard'!B13"],
    ).execute()

    def first(vr):
        v = vr.get("values") or [[""]]
        return (v[0] or [""])[0] if v else ""

    status_val = first(res["valueRanges"][0])
    planned    = first(res["valueRanges"][1])

    if status_val in SKIP_VALUES:
        print(f"no-op: status={status_val!r}")
        return

    today = date.today().isoformat()

    log = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="'_WorkoutLog'!A:D"
    ).execute().get("values", [])

    update_row = None
    existing_status = None
    for i, row in enumerate(log[1:], start=2):
        if row and row[0] == today:
            update_row = i
            existing_status = row[2] if len(row) > 2 else None
            break

    if existing_status == status_val:
        print(f"already current: {today} {status_val!r}")
        return

    payload = [[today, planned, status_val, ""]]
    if update_row:
        svc.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'_WorkoutLog'!A{update_row}:D{update_row}",
            valueInputOption="RAW",
            body={"values": payload},
        ).execute()
        print(f"updated row {update_row}: {payload[0]}")
    else:
        svc.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range="'_WorkoutLog'!A:D",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": payload},
        ).execute()
        print(f"appended: {payload[0]}")


if __name__ == "__main__":
    main()
