"""Google Sheets client helpers."""

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_client(credentials_path: str) -> gspread.Client:
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return gspread.authorize(creds)


def open_sheet(client: gspread.Client, sheet_id: str) -> gspread.Spreadsheet:
    return client.open_by_key(sheet_id)


def open_configured(config: dict) -> gspread.Spreadsheet:
    client = get_client(config["google"]["credentials_path"])
    return open_sheet(client, config["google"]["sheet_id"])
