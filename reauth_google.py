#!/usr/bin/env python3
"""Re-auth Google for the cloud cron.

Runs the OAuth flow locally, then prints the new refresh_token so you can
paste it into the repo's GOOGLE_REFRESH_TOKEN GitHub secret.
"""
import json
import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDS = os.path.expanduser("~/gmail_credentials.json")

if not os.path.exists(CREDS):
    sys.exit(f"missing {CREDS}")

flow = InstalledAppFlow.from_client_secrets_file(CREDS, SCOPES)
creds = flow.run_local_server(port=0)

with open(CREDS) as f:
    cfg = json.load(f)
key = "installed" if "installed" in cfg else "web"
print()
print("=" * 60)
print("PASTE THESE INTO https://github.com/wm215/whoop-to-sheets/settings/secrets/actions")
print("=" * 60)
print(f"GOOGLE_CLIENT_ID       = {cfg[key]['client_id']}")
print(f"GOOGLE_CLIENT_SECRET   = {cfg[key]['client_secret']}")
print(f"GOOGLE_REFRESH_TOKEN   = {creds.refresh_token}")
print("=" * 60)
