#!/usr/bin/env python3
"""Daily WHOOP → Sheets morning pull.

Runs in GitHub Actions (cron: 11:00 UTC ≈ 7 AM ET) — pulls latest WHOOP recovery
+ sleep, appends a row to the Revamp sheet's WHOOP tab.

WHOOP rotates refresh tokens on every refresh and immediately invalidates the
old one, so we persist the rotated RT into a hidden `_Tokens` tab in the Sheet
(read at start of run, write back at end). Static GitHub Secrets won't survive
a single rotation.

Credentials from environment:
- WHOOP_CLIENT_ID, WHOOP_CLIENT_SECRET   (do not rotate; safe in Secrets)
- GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN  (Google RTs
  generally don't rotate; static Secret is fine)
"""
from __future__ import annotations
import os
from datetime import date

import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

WHOOP_BASE  = "https://api.prod.whoop.com/developer"
WHOOP_TOKEN = "https://api.prod.whoop.com/oauth/oauth2/token"
SHEET_ID    = "1TxbgCTrtp1Owuqxpu2Hi7dVkPAUFQsNaaeKQqxWOQh4"
TAB_WHOOP   = "WHOOP"
TAB_TOKENS  = "_Tokens"


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


def read_whoop_rt(svc) -> str:
    res = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{TAB_TOKENS}'!A:B"
    ).execute().get("values", [])
    for row in res[1:]:
        if row and row[0] == "whoop":
            return row[1] if len(row) > 1 else ""
    raise RuntimeError("no whoop refresh_token row in _Tokens tab")


def write_whoop_rt(svc, rt: str) -> None:
    res = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{TAB_TOKENS}'!A:B"
    ).execute().get("values", [])
    for i, row in enumerate(res[1:], start=2):
        if row and row[0] == "whoop":
            svc.spreadsheets().values().update(
                spreadsheetId=SHEET_ID,
                range=f"'{TAB_TOKENS}'!A{i}:B{i}",
                valueInputOption="RAW",
                body={"values": [["whoop", rt]]},
            ).execute()
            return
    raise RuntimeError("no whoop row to update in _Tokens tab")


def whoop_refresh(refresh_token: str) -> dict:
    """Returns the full token response. Caller MUST persist the new
    refresh_token before the next refresh attempt or the chain breaks."""
    r = httpx.post(
        WHOOP_TOKEN,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id":     os.environ["WHOOP_CLIENT_ID"],
            "client_secret": os.environ["WHOOP_CLIENT_SECRET"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def whoop_get(endpoint: str, token: str, params: dict | None = None) -> dict:
    r = httpx.get(
        f"{WHOOP_BASE}{endpoint}",
        params=params or {},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def latest(payload: dict) -> dict:
    records = payload.get("records", [])
    if not records:
        raise RuntimeError(f"no records: {payload}")
    return records[0]


def main() -> None:
    svc = sheets_service()

    # 1. Read current refresh token from the Sheet
    old_rt = read_whoop_rt(svc)

    # 2. Refresh — get fresh access_token + new refresh_token
    tokens = whoop_refresh(old_rt)
    access_token = tokens["access_token"]
    new_rt = tokens.get("refresh_token") or old_rt  # fall back if not rotated

    # 3. Persist new refresh_token IMMEDIATELY (before any other failure point)
    if new_rt != old_rt:
        write_whoop_rt(svc, new_rt)

    # 4. Pull recovery + sleep
    recovery = latest(whoop_get("/v2/recovery", access_token, {"limit": 1}))
    sleep    = latest(whoop_get("/v2/activity/sleep", access_token, {"limit": 1}))

    rec = recovery.get("score") or {}
    slp = sleep.get("score") or {}
    stage = slp.get("stage_summary") or {}

    in_bed = stage.get("total_in_bed_time_milli") or 0
    awake  = stage.get("total_awake_time_milli")  or 0
    sleep_ms = in_bed - awake

    today = date.today().isoformat()
    row = [
        today,
        round(sleep_ms / 3_600_000, 1) if sleep_ms > 0 else "",
        round(rec.get("hrv_rmssd_milli") or 0, 1) or "",
        round(rec.get("resting_heart_rate") or 0, 1) or "",
        rec.get("recovery_score") or "",
    ]

    # Idempotent upsert: if today's row already exists, update it; else append.
    existing = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{TAB_WHOOP}'!A:E"
    ).execute().get("values", [])
    update_row = None
    for i, r in enumerate(existing[1:], start=2):
        if r and r[0] == today:
            update_row = i
            break

    if update_row:
        svc.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'{TAB_WHOOP}'!A{update_row}:E{update_row}",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()
        print(f"updated row {update_row}: {row}")
    else:
        svc.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range=f"'{TAB_WHOOP}'!A:E",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
        print(f"appended: {row}")


if __name__ == "__main__":
    main()
