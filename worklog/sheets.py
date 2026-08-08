"""Google Sheets integration: create and write to the base worklog tracker."""

from datetime import date

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

TAB_NAME = "Worklog"
HEADER_ROW = 3  # 1-indexed row where column headers live
FIRST_DATA_ROW = HEADER_ROW + 1

HEADERS = [
    "Date",
    "Task",
    "Priority",
    "Workplace",
    "Time Range",
    "Total Hours",
    "Assigned On",
    "Notes",
]

PRIORITY_OPTIONS = ["High", "Medium", "Low"]
WORKPLACE_OPTIONS = ["Home", "Office", "Sick", "Casual"]

# Column indexes (0-based)
COL_DATE, COL_TASK, COL_PRIORITY, COL_WORKPLACE, COL_TIME, COL_HOURS, COL_ASSIGNED, COL_NOTES = range(8)

DARK = {"red": 0.15, "green": 0.19, "blue": 0.28}
LIGHT_BAND = {"red": 0.95, "green": 0.96, "blue": 0.98}
WHITE = {"red": 1, "green": 1, "blue": 1}


def get_client(credentials_path: str) -> gspread.Client:
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return gspread.authorize(creds)


def init_tracker_tab(spreadsheet: gspread.Spreadsheet) -> str:
    """Initialize the formatted tracker layout in the spreadsheet.

    Uses the TAB_NAME worksheet if it exists and is empty; otherwise creates a
    fresh tab (TAB_NAME, TAB_NAME 2, ...) so existing data is never touched.
    Returns the tab name used.

    Note: service accounts cannot own Drive files (Google removed their storage
    quota), so the spreadsheet itself must be created by the user and shared
    with the service account.
    """
    existing = {ws.title for ws in spreadsheet.worksheets()}
    name = TAB_NAME
    counter = 2
    while name in existing:
        ws = spreadsheet.worksheet(name)
        if not ws.get_all_values():  # empty tab — safe to use
            break
        name = f"{TAB_NAME} {counter}"
        counter += 1
    else:
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=len(HEADERS))

    _init_tracker_sheet(spreadsheet, ws)
    return name


def open_sheet(client: gspread.Client, sheet_id: str) -> gspread.Spreadsheet:
    return client.open_by_key(sheet_id)


def _init_tracker_sheet(spreadsheet: gspread.Spreadsheet, ws: gspread.Worksheet) -> None:
    sheet_id = ws.id

    # --- Values: scorecard + headers ---
    ws.update(
        values=[["Total Hours Logged", f"=SUM(F{FIRST_DATA_ROW}:F)"]],
        range_name="A1:B1",
        value_input_option="USER_ENTERED",
    )
    ws.update(values=[HEADERS], range_name=f"A{HEADER_ROW}:H{HEADER_ROW}")

    requests = [
        # Freeze through the header row
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": HEADER_ROW}},
                "fields": "gridProperties.frozenRowCount",
            }
        },
        # Scorecard styling
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 2},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": DARK,
                        "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 12},
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)",
            }
        },
        # Header row styling
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": HEADER_ROW - 1,
                    "endRowIndex": HEADER_ROW,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(HEADERS),
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": DARK,
                        "textFormat": {"foregroundColor": WHITE, "bold": True},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        },
        # Alternating row colors for the data range
        {
            "addBanding": {
                "bandedRange": {
                    "range": {"sheetId": sheet_id, "startRowIndex": HEADER_ROW, "startColumnIndex": 0, "endColumnIndex": len(HEADERS)},
                    "rowProperties": {"firstBandColor": WHITE, "secondBandColor": LIGHT_BAND},
                }
            }
        },
        # Dropdowns: Priority
        _validation_request(sheet_id, COL_PRIORITY, PRIORITY_OPTIONS),
        # Dropdowns: Workplace
        _validation_request(sheet_id, COL_WORKPLACE, WORKPLACE_OPTIONS),
        # Date formatting for Date + Assigned On
        _number_format_request(sheet_id, COL_DATE, "DATE", "dd-mmm-yyyy"),
        _number_format_request(sheet_id, COL_ASSIGNED, "DATE", "dd-mmm-yyyy"),
        # Hours numeric format
        _number_format_request(sheet_id, COL_HOURS, "NUMBER", "0.0#"),
        # Column widths
        _col_width_request(sheet_id, COL_DATE, 110),
        _col_width_request(sheet_id, COL_TASK, 340),
        _col_width_request(sheet_id, COL_PRIORITY, 100),
        _col_width_request(sheet_id, COL_WORKPLACE, 110),
        _col_width_request(sheet_id, COL_TIME, 130),
        _col_width_request(sheet_id, COL_HOURS, 100),
        _col_width_request(sheet_id, COL_ASSIGNED, 110),
        _col_width_request(sheet_id, COL_NOTES, 260),
    ]
    spreadsheet.batch_update({"requests": requests})


def _validation_request(sheet_id: int, col: int, options: list) -> dict:
    return {
        "setDataValidation": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": HEADER_ROW,
                "startColumnIndex": col,
                "endColumnIndex": col + 1,
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [{"userEnteredValue": o} for o in options],
                },
                "showCustomUi": True,
                "strict": True,
            },
        }
    }


def _number_format_request(sheet_id: int, col: int, fmt_type: str, pattern: str) -> dict:
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": HEADER_ROW,
                "startColumnIndex": col,
                "endColumnIndex": col + 1,
            },
            "cell": {"userEnteredFormat": {"numberFormat": {"type": fmt_type, "pattern": pattern}}},
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def _col_width_request(sheet_id: int, col: int, pixels: int) -> dict:
    return {
        "updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": col, "endIndex": col + 1},
            "properties": {"pixelSize": pixels},
            "fields": "pixelSize",
        }
    }


def append_entry(
    config: dict,
    task: str,
    hours: float = None,
    priority: str = "",
    workplace: str = "",
    time_range: str = "",
    entry_date: str = None,
    assigned_on: str = "",
    notes: str = "",
) -> None:
    """Append a single worklog row to the tracker."""
    client = get_client(config["google"]["credentials_path"])
    spreadsheet = open_sheet(client, config["google"]["sheet_id"])
    ws = spreadsheet.worksheet(config["google"].get("tab", TAB_NAME))
    row = [
        entry_date or date.today().isoformat(),
        task,
        priority,
        workplace,
        time_range,
        hours if hours is not None else "",
        assigned_on,
        notes,
    ]
    ws.append_row(row, value_input_option="USER_ENTERED", table_range=f"A{HEADER_ROW}")
