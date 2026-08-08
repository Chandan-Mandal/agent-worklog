"""Interactive setup wizard: worklog setup"""

import json
import os
from pathlib import Path

from . import config as config_store
from . import sheets

BANNER = """
============================================
  worklog-agent setup
============================================
This wizard configures your integrations.
You can re-run `worklog setup` anytime.
"""

GOOGLE_HELP = """
--- Google Sheets (required) ---
worklog-agent writes to Google Sheets using a service account.

One-time setup (~5 min):
  1. Go to https://console.cloud.google.com/ and create (or pick) a project
  2. Enable the "Google Sheets API" and "Google Drive API"
     https://console.cloud.google.com/apis/library
  3. Create a Service Account (IAM & Admin > Service Accounts)
  4. Create a JSON key for it and download the file
"""


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def _ask_yes_no(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    value = input(f"{prompt} ({hint}): ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes")


def run() -> None:
    print(BANNER)
    config = config_store.load()

    _setup_google(config)
    _setup_slack(config)
    _setup_jira(config)

    config_store.save(config)
    print(f"\nConfig saved to {config_store.CONFIG_PATH}")
    _print_summary(config)


def _setup_google(config: dict) -> None:
    print(GOOGLE_HELP)
    google = config.setdefault("google", {})

    # 1. Credentials
    while True:
        creds_path = _ask("Path to your service account JSON key", google.get("credentials_path", ""))
        creds_path = os.path.expanduser(creds_path)
        if not creds_path:
            print("  A credentials file is required to continue.")
            continue
        if not Path(creds_path).exists():
            print(f"  File not found: {creds_path}")
            continue
        try:
            with open(creds_path) as f:
                sa_email = json.load(f).get("client_email", "")
            client = sheets.get_client(creds_path)
        except Exception as e:  # noqa: BLE001
            print(f"  Could not load credentials: {e}")
            continue
        google["credentials_path"] = creds_path
        print(f"  OK — authenticated as service account: {sa_email}")
        break

    # 2. Sheet: connect and (optionally) initialize
    # Note: Google no longer lets service accounts own Drive files, so the
    # sheet must live in YOUR Drive and be shared with the service account.
    if google.get("sheet_id"):
        print(f"\nCurrently configured sheet: {google.get('sheet_url', google['sheet_id'])}")
        if not _ask_yes_no("Keep using this sheet?", default=True):
            google.pop("sheet_id", None)
            google.pop("sheet_url", None)

    if not google.get("sheet_id"):
        print(
            f"\n  Now connect a Google Sheet (2 clicks in your browser):\n"
            f"    1. Create a sheet at https://sheets.new (or open an existing one)\n"
            f"    2. Share it as Editor with:\n"
            f"       {sa_email}\n"
        )
        while True:
            raw = _ask("Paste the sheet URL (or just its spreadsheet ID)")
            google["sheet_id"] = _extract_sheet_id(raw)
            try:
                spreadsheet = sheets.open_sheet(client, google["sheet_id"])
                google["sheet_url"] = spreadsheet.url
                print(f"  OK — access verified: {spreadsheet.title}")
                break
            except Exception as e:  # noqa: BLE001
                print(f"  Could not open the sheet ({e}).\n  Check that it is shared with {sa_email} and try again.")

        if _ask_yes_no("Initialize month/week tracker tabs (current month through December)?", default=True):
            from datetime import date

            from . import template

            today = date.today()
            print("  Building month tabs with week blocks, headers, and dropdowns...")
            created = template.build_range(spreadsheet, (today.year, today.month), (today.year, 12))
            print(f"  Done! Created: {', '.join(created) if created else '(tabs already existed)'}")


def _extract_sheet_id(value: str) -> str:
    """Accept a full Google Sheets URL or a bare spreadsheet ID."""
    if "/spreadsheets/d/" in value:
        return value.split("/spreadsheets/d/")[1].split("/")[0]
    return value.strip()


def _setup_slack(config: dict) -> None:
    print("\n--- Slack (optional, for standup updates) ---")
    slack = config.setdefault("slack", {})
    if not _ask_yes_no("Configure Slack now?", default=bool(slack.get("webhook_url"))):
        return
    slack["webhook_url"] = _ask("Slack incoming webhook URL (or bot token later)", slack.get("webhook_url", ""))
    slack["channel"] = _ask("Channel name (e.g. #geekbot-standup)", slack.get("channel", ""))
    print("  Saved. (Posting to Slack lands in an upcoming version.)")


def _setup_jira(config: dict) -> None:
    print("\n--- Jira (optional) ---")
    jira = config.setdefault("jira", {})
    if not _ask_yes_no("Configure Jira now?", default=bool(jira.get("base_url"))):
        return
    jira["base_url"] = _ask("Jira base URL (e.g. https://yourco.atlassian.net)", jira.get("base_url", ""))
    jira["email"] = _ask("Jira account email", jira.get("email", ""))
    jira["api_token"] = _ask("Jira API token", jira.get("api_token", ""))
    print("  Saved. (Jira sync lands in an upcoming version.)")


def _print_summary(config: dict) -> None:
    google = config.get("google", {})
    print("\n=== Setup complete ===")
    print(f"  Sheet: {google.get('sheet_url', '(not set)')}")
    print(f"  Slack: {'configured' if config.get('slack', {}).get('webhook_url') else 'skipped'}")
    print(f"  Jira:  {'configured' if config.get('jira', {}).get('base_url') else 'skipped'}")
    print("\nTry it:")
    print('  worklog log --task "Built the worklog agent" --tag agent-worklog --hours 2 --priority High --timelog "11AM - 1PM"')
