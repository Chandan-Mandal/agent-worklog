"""Single-tab month/week template engine for the worklog tracker.

Everything lives in one worksheet (TAB_NAME). Month sections are stacked
vertically, each made of week blocks:

    MONTH - AUG,2026                                TOTAL HRS  <sum>

    WEEK 1 (1-2)
    DATE  DAY  TASK_TAG  SUBTASK  PRIORITY  TIMELOG  TIMESPENT  ASSIGNED_AT  ASSIGNED_BY
    ...data rows...

    WEEK 2 (3-9)
    ...

    MONTH - SEP,2026
    ...

When the month changes, the previous month's section can be moved to an
"Archive" tab (formatting and values preserved).
"""

import calendar
import re
from datetime import date, datetime, timedelta

import gspread

TAB_NAME = "Worklog"
ARCHIVE_TAB = "Archive"

HEADERS = [
    "DATE",
    "DAY",
    "TASK_TAG",
    "SUBTASK",
    "TYPE",
    "PRIORITY",
    "WORKPLACE",
    "TIMELOG",
    "TIMESPENT",
    "ASSIGNED_AT",
    "ASSIGNED_BY",
    "NOTES",
]
N_COLS = len(HEADERS)
LAST_COL = "L"
ROWS_PER_WEEK = 8
PRIORITY_OPTIONS = ["High", "Medium", "Low"]
WORKPLACE_OPTIONS = ["Home", "Office", "Leave"]
TYPE_OPTIONS = ["DEV", "DELIVERY", "OPS", "AD-HOC", "MEETING", "LEARNING"]

(
    COL_DATE,
    COL_DAY,
    COL_TAG,
    COL_SUBTASK,
    COL_TYPE,
    COL_PRIORITY,
    COL_WORKPLACE,
    COL_TIMELOG,
    COL_TIMESPENT,
    COL_ASSIGNED_AT,
    COL_ASSIGNED_BY,
    COL_NOTES,
) = range(N_COLS)

DARK = {"red": 0.15, "green": 0.19, "blue": 0.28}
ACCENT = {"red": 0.27, "green": 0.34, "blue": 0.47}
WHITE = {"red": 1, "green": 1, "blue": 1}

# Day-of-week row colors: classic Excel/Sheets blue (Accent-1 tints),
# most intense on Monday fading to Friday
DAY_COLORS = {
    "Mon": {"red": 0.557, "green": 0.667, "blue": 0.859},  # 8EAADB
    "Tue": {"red": 0.631, "green": 0.722, "blue": 0.882},  # A1B8E1
    "Wed": {"red": 0.706, "green": 0.776, "blue": 0.906},  # B4C6E7
    "Thu": {"red": 0.780, "green": 0.831, "blue": 0.929},  # C7D4ED
    "Fri": {"red": 0.851, "green": 0.886, "blue": 0.953},  # D9E2F3
}
WEEKEND_COLOR = {"red": 0.85, "green": 0.85, "blue": 0.85}
LEAVE_COLOR = {"red": 1.0, "green": 0.9, "blue": 0.5}

MONTH_LABEL_RE = re.compile(r"^MONTH - ([A-Z]{3}),(\d{4})$")
WEEK_LABEL_RE = re.compile(r"^WEEK (\d+) \((\d{1,2}) ([A-Za-z]{3}) - (\d{1,2}) ([A-Za-z]{3})\)$")

_MONTH_NUM = {calendar.month_abbr[i].upper(): i for i in range(1, 13)}


def month_label(year: int, month: int) -> str:
    return f"MONTH - {calendar.month_abbr[month].upper()},{year}"


def month_title(year: int, month: int) -> str:
    return f"{calendar.month_abbr[month].upper()} {year}"


def parse_month_title(title: str):
    """'AUG 2026' -> (2026, 8), else None."""
    parts = title.strip().upper().split()
    if len(parts) == 2 and parts[0] in _MONTH_NUM and parts[1].isdigit():
        return int(parts[1]), _MONTH_NUM[parts[0]]
    return None


def weeks_of_month(year: int, month: int) -> list:
    """Full Mon-Sun weeks belonging to the month, as (monday, sunday) dates.

    A week belongs to the month containing its Thursday (ISO 8601 style), so
    every week is complete and each week belongs to exactly one month.
    """
    first = date(year, month, 1)
    monday = first - timedelta(days=first.weekday())
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    weeks = []
    while True:
        thursday = monday + timedelta(days=3)
        if (thursday.year, thursday.month) == (year, month):
            weeks.append((monday, monday + timedelta(days=6)))
        elif thursday > last_day:
            break
        monday += timedelta(days=7)
    return weeks


def week_label(monday: date, sunday: date) -> str:
    week_no = monday.isocalendar()[1]
    return f"WEEK {week_no} ({monday.day} {calendar.month_abbr[monday.month]} - {sunday.day} {calendar.month_abbr[sunday.month]})"


def parse_date(value: str) -> date:
    if not value or value == "today":
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


# ---------------------------------------------------------------- worksheet

def get_tracker_ws(spreadsheet: gspread.Spreadsheet) -> gspread.Worksheet:
    try:
        return spreadsheet.worksheet(TAB_NAME)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=TAB_NAME, rows=400, cols=N_COLS)
        spreadsheet.batch_update({"requests": _column_requests(ws.id) + day_color_requests(ws.id)})
        return ws


def day_color_requests(sheet_id: int) -> list:
    """Conditional formatting: rows colored by day of week, weekends grey,
    leave days yellow. Rule order matters — first match wins.

    DATE/DAY/WORKPLACE are blanked on repeat rows of a day group, so the
    formulas look up the nearest non-blank value above; $D<>"" (SUBTASK)
    limits coloring to rows that hold actual entries."""
    day_col = chr(ord("A") + COL_DAY)
    wp = chr(ord("A") + COL_WORKPLACE)
    task = chr(ord("A") + COL_SUBTASK)
    eff_day = f'IFERROR(LOOKUP(2,1/(${day_col}$1:${day_col}1<>""),${day_col}$1:${day_col}1),"")'
    eff_wp = f'IFERROR(LOOKUP(2,1/(${wp}$1:${wp}1<>""),${wp}$1:${wp}1),"")'
    rules = [
        (f'=AND(${task}1<>"", {eff_wp}="Leave")', LEAVE_COLOR),
        (f'=AND(${task}1<>"", OR({eff_day}="Sat",{eff_day}="Sun"))', WEEKEND_COLOR),
    ]
    rules += [(f'=AND(${task}1<>"", {eff_day}="{day}")', color) for day, color in DAY_COLORS.items()]
    return [
        {
            "addConditionalFormatRule": {
                "index": i,
                "rule": {
                    "ranges": [{"sheetId": sheet_id, "startColumnIndex": 0, "endColumnIndex": N_COLS}],
                    "booleanRule": {
                        "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": formula}]},
                        "format": {"backgroundColor": color},
                    },
                },
            }
        }
        for i, (formula, color) in enumerate(rules)
    ]


# ---------------------------------------------------------------- parsing

def parse_sections(ws: gspread.Worksheet):
    """Parse month sections and their week blocks. Rows are 1-based.

    Returns (sections, all_values). Section: {year, month, title_row, blocks}.
    Block: {week, start, end, label_row, data_start, data_end} (inclusive).
    """
    all_values = ws.get_all_values()
    sections = []
    markers = []  # rows of every MONTH/WEEK label, for computing block extents
    for idx, row in enumerate(all_values, start=1):
        cell = (row[0] if row else "").strip()
        m = MONTH_LABEL_RE.match(cell)
        if m:
            sections.append({"year": int(m.group(2)), "month": _MONTH_NUM[m.group(1)], "title_row": idx, "blocks": []})
            markers.append(idx)
            continue
        w = WEEK_LABEL_RE.match(cell)
        if w and sections:
            sections[-1]["blocks"].append({
                "week": int(w.group(1)),
                "_start_raw": (int(w.group(2)), w.group(3).capitalize()),
                "_end_raw": (int(w.group(4)), w.group(5).capitalize()),
                "label_row": idx,
            })
            markers.append(idx)

    for section in sections:
        year, month = section["year"], section["month"]
        for block in section["blocks"]:
            sd, sm_name = block.pop("_start_raw")
            ed, em_name = block.pop("_end_raw")
            sm, em = _MONTH_NUM[sm_name.upper()], _MONTH_NUM[em_name.upper()]
            sy = year - 1 if (month == 1 and sm == 12) else year
            ey = year + 1 if (month == 12 and em == 1) else year
            block["start_date"] = date(sy, sm, sd)
            block["end_date"] = date(ey, em, ed)
            block["data_start"] = block["label_row"] + 2
            next_marker = next((m for m in markers if m > block["label_row"]), None)
            if next_marker:
                block["data_end"] = next_marker - 2  # skip separator row
            else:
                block["data_end"] = max(len(all_values), block["data_start"] + ROWS_PER_WEEK - 1)
    return sections, all_values


def latest_section(sections: list):
    return max(sections, key=lambda s: (s["year"], s["month"]), default=None)


def _find_section(sections: list, year: int, month: int):
    return next((s for s in sections if s["year"] == year and s["month"] == month), None)


def _locate_block(sections: list, entry_date: date):
    """Find the (section, block) whose week covers entry_date."""
    for section in sections:
        for block in section["blocks"]:
            if block["start_date"] <= entry_date <= block["end_date"]:
                return section, block
    return None


def _find_entry_row(all_values: list, block: dict, entry_date: date, subtask: str):
    """Find a data row in the block matching date + subtask. Returns (row, values) or None."""
    display_date = entry_date.strftime("%d-%b-%Y")
    for r in range(block["data_start"], min(block["data_end"], len(all_values)) + 1):
        row_values = all_values[r - 1]
        if len(row_values) > COL_SUBTASK and row_values[COL_DATE].strip() == display_date \
                and row_values[COL_SUBTASK].strip().casefold() == subtask.strip().casefold():
            return r, row_values
    return None


def _row_is_empty(all_values: list, row: int) -> bool:
    if row > len(all_values):
        return True
    return not any(cell.strip() for cell in all_values[row - 1])


# ---------------------------------------------------------------- creation

def append_month_section(spreadsheet: gspread.Spreadsheet, year: int, month: int) -> str:
    """Append a month section to the tracker tab. Returns its title, e.g. 'AUG 2026'."""
    ws = get_tracker_ws(spreadsheet)
    sections, all_values = parse_sections(ws)
    if _find_section(sections, year, month):
        return month_title(year, month)

    last = latest_section(sections)
    last_content_row = max(
        (i for i, row in enumerate(all_values, start=1) if any(c.strip() for c in row)),
        default=0,
    )
    if last and last["blocks"]:
        start = max(last["blocks"][-1]["data_end"], last_content_row) + 3  # separator + one blank gap
    elif last_content_row:
        start = last_content_row + 2
    else:
        start = 1

    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    total_formula = (
        f'=SUMIFS(I:I,A:A,">="&DATE({year},{month},1),A:A,"<"&DATE({nxt.year},{nxt.month},1))'
    )
    grid = [
        [month_label(year, month)] + [""] * (N_COLS - 3) + ["TOTAL HRS", total_formula],
        [""] * N_COLS,
    ]
    label_offsets = []  # 0-based offsets within grid
    week_numbers = []
    for monday, sunday in weeks_of_month(year, month):
        label_offsets.append(len(grid))
        week_numbers.append(monday.isocalendar()[1])
        grid.append([week_label(monday, sunday)] + [""] * (N_COLS - 1))
        grid.append(list(HEADERS))
        grid.extend([[""] * N_COLS for _ in range(ROWS_PER_WEEK)])
        grid.append([""] * N_COLS)  # separator

    end = start + len(grid) - 1
    if end > ws.row_count:
        ws.add_rows(end - ws.row_count + 20)
    ws.update(values=grid, range_name=f"A{start}:{LAST_COL}{end}", value_input_option="USER_ENTERED")

    requests = [_month_title_format_request(ws.id, start - 1)]
    for week_no, offset in zip(week_numbers, label_offsets):
        label_row = start - 1 + offset  # 0-based
        requests.extend(_block_format_requests(ws.id, label_row, ROWS_PER_WEEK))
        requests.append(_table_request(ws.id, table_name(year, month, week_no), label_row + 1, label_row + 2 + ROWS_PER_WEEK))
    spreadsheet.batch_update({"requests": requests})
    return month_title(year, month)


def build_range(spreadsheet: gspread.Spreadsheet, start: tuple, end: tuple) -> list:
    """Append month sections from (year, month) start through end inclusive."""
    created = []
    y, m = start
    while (y, m) <= end:
        created.append(append_month_section(spreadsheet, y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return created


# ---------------------------------------------------------------- formatting

def _month_title_format_request(sheet_id: int, row: int) -> dict:
    return {
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": row, "endRowIndex": row + 1, "startColumnIndex": 0, "endColumnIndex": N_COLS},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": DARK,
                    "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 12},
                    "verticalAlignment": "MIDDLE",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)",
        }
    }


def _column_requests(sheet_id: int) -> list:
    def num_fmt(col, fmt_type, pattern):
        return {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startColumnIndex": col, "endColumnIndex": col + 1},
                "cell": {"userEnteredFormat": {"numberFormat": {"type": fmt_type, "pattern": pattern}}},
                "fields": "userEnteredFormat.numberFormat",
            }
        }

    def width(col, px):
        return {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": col, "endIndex": col + 1},
                "properties": {"pixelSize": px},
                "fields": "pixelSize",
            }
        }

    return [
        num_fmt(COL_DATE, "DATE", "dd-mmm-yyyy"),
        num_fmt(COL_ASSIGNED_AT, "DATE", "dd-mmm-yyyy"),
        num_fmt(COL_TIMESPENT, "NUMBER", "0.0#"),
        width(COL_DATE, 110),
        width(COL_DAY, 60),
        width(COL_TAG, 130),
        width(COL_SUBTASK, 320),
        width(COL_TYPE, 110),
        width(COL_PRIORITY, 95),
        width(COL_WORKPLACE, 100),
        width(COL_TIMELOG, 170),
        width(COL_TIMESPENT, 100),
        width(COL_ASSIGNED_AT, 110),
        width(COL_ASSIGNED_BY, 120),
        width(COL_NOTES, 240),
    ]


def _block_format_requests(sheet_id: int, label_row: int, n_data_rows: int) -> list:
    """Formatting for one week block. label_row is 0-based."""
    header_row = label_row + 1
    data_start = label_row + 2
    data_end = data_start + n_data_rows  # exclusive
    return [
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": label_row, "endRowIndex": header_row, "startColumnIndex": 0, "endColumnIndex": N_COLS},
                "cell": {"userEnteredFormat": {"backgroundColor": ACCENT, "textFormat": {"foregroundColor": WHITE, "bold": True}}},
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": header_row, "endRowIndex": data_start, "startColumnIndex": 0, "endColumnIndex": N_COLS},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.9, "green": 0.92, "blue": 0.95},
                        "textFormat": {"bold": True, "fontSize": 9},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        },
        _dropdown_request(sheet_id, data_start, data_end, COL_TYPE, TYPE_OPTIONS),
        _dropdown_request(sheet_id, data_start, data_end, COL_PRIORITY, PRIORITY_OPTIONS),
        _dropdown_request(sheet_id, data_start, data_end, COL_WORKPLACE, WORKPLACE_OPTIONS),
    ]


def _dropdown_request(sheet_id: int, start_row: int, end_row: int, col: int, options: list) -> dict:
    return {
        "setDataValidation": {
            "range": {"sheetId": sheet_id, "startRowIndex": start_row, "endRowIndex": end_row, "startColumnIndex": col, "endColumnIndex": col + 1},
            "rule": {
                "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": o} for o in options]},
                "showCustomUi": True,
                "strict": True,
            },
        }
    }


def table_name(year: int, month: int, week: int) -> str:
    return f"{calendar.month_abbr[month].upper()}{year}_W{week}"


def _table_request(sheet_id: int, name: str, header_row: int, data_end: int) -> dict:
    """Turn a week block into a Sheets Table (per-column filter chips).

    header_row is the 0-based row of the DATE..NOTES header; data_end is the
    0-based exclusive end row of the block's data.
    """
    return {
        "addTable": {
            "table": {
                "name": name,
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": header_row,
                    "endRowIndex": data_end,
                    "startColumnIndex": 0,
                    "endColumnIndex": N_COLS,
                },
            }
        }
    }


# ---------------------------------------------------------------- operations

def insert_entry(
    spreadsheet: gspread.Spreadsheet,
    entry_date: date,
    task_tag: str = "",
    subtask: str = "",
    work_type: str = "",
    priority: str = "",
    workplace: str = "",
    timelog: str = "",
    timespent=None,
    assigned_at: str = "",
    assigned_by: str = "",
    notes: str = "",
    ascending: bool = True,
) -> str:
    """Insert a row into the right month section + week block. Returns the section title.

    If a row with the same date + subtask already exists in the block, the new
    timelog is appended to it (e.g. "1PM - 2PM, 5PM - 7PM") and hours are added.
    """
    ws = get_tracker_ws(spreadsheet)
    sections, all_values = parse_sections(ws)
    located = _locate_block(sections, entry_date)
    if located is None:
        # the week belongs to the month containing its Thursday
        thursday = entry_date - timedelta(days=entry_date.weekday()) + timedelta(days=3)
        append_month_section(spreadsheet, thursday.year, thursday.month)
        sections, all_values = parse_sections(ws)
        located = _locate_block(sections, entry_date)
    if located is None:
        raise SystemExit(f"No week block covers {entry_date.isoformat()}.")
    section, block = located

    # Restore grouped fields (DATE/DAY/WORKPLACE) so matching and sorting see full rows
    _ungroup_block(ws, block, all_values)

    # Merge into an existing row for the same date + subtask (multi-session work)
    if subtask:
        existing = _find_entry_row(all_values, block, entry_date, subtask)
        if existing is not None:
            row, current = existing
            merged = list(current) + [""] * (N_COLS - len(current))
            if timelog:
                existing_logs = [t.strip() for t in merged[COL_TIMELOG].split(",") if t.strip()]
                if timelog.strip() not in existing_logs:
                    merged[COL_TIMELOG] = f"{merged[COL_TIMELOG]}, {timelog}" if merged[COL_TIMELOG].strip() else timelog
            if timespent is not None:
                try:
                    prev = float(merged[COL_TIMESPENT]) if merged[COL_TIMESPENT].strip() else 0.0
                except ValueError:
                    prev = 0.0
                merged[COL_TIMESPENT] = prev + timespent
            for col, value in [
                (COL_TAG, task_tag), (COL_TYPE, work_type), (COL_PRIORITY, priority),
                (COL_WORKPLACE, workplace), (COL_ASSIGNED_AT, assigned_at), (COL_ASSIGNED_BY, assigned_by),
            ]:
                if value and not str(merged[col]).strip():
                    merged[col] = value
            if notes:
                merged[COL_NOTES] = f"{merged[COL_NOTES]}; {notes}" if str(merged[COL_NOTES]).strip() else notes
            ws.update(values=[merged[:N_COLS]], range_name=f"A{row}:{LAST_COL}{row}", value_input_option="USER_ENTERED")
            _regroup_block(ws, block)
            return month_title(section["year"], section["month"])

    row = next(
        (r for r in range(block["data_start"], block["data_end"] + 1) if _row_is_empty(all_values, r)),
        None,
    )
    if row is None:  # block full — grow it by one row
        row = block["data_end"] + 1
        spreadsheet.batch_update({
            "requests": [{
                "insertDimension": {
                    "range": {"sheetId": ws.id, "dimension": "ROWS", "startIndex": row - 1, "endIndex": row},
                    "inheritFromBefore": True,
                }
            }]
        })
        block["data_end"] = row

    values = [[
        entry_date.isoformat(),
        entry_date.strftime("%a"),
        task_tag,
        subtask,
        work_type,
        priority,
        workplace,
        timelog,
        timespent if timespent is not None else "",
        assigned_at,
        assigned_by,
        notes,
    ]]
    ws.update(values=values, range_name=f"A{row}:{LAST_COL}{row}", value_input_option="USER_ENTERED")
    _sort_block(spreadsheet, ws, block, ascending)
    _regroup_block(ws, block)
    return month_title(section["year"], section["month"])


def sort_blocks(spreadsheet: gspread.Spreadsheet, month: str = None, ascending: bool = True) -> int:
    """Sort week blocks by DATE. month like 'AUG 2026' limits to one section."""
    ws = get_tracker_ws(spreadsheet)
    sections, all_values = parse_sections(ws)
    if month:
        parsed = parse_month_title(month)
        if not parsed:
            raise SystemExit(f"Could not parse month '{month}'. Expected e.g. 'AUG 2026'.")
        sections = [s for s in sections if (s["year"], s["month"]) == parsed]
    n = 0
    for section in sections:
        for block in section["blocks"]:
            _ungroup_block(ws, block, all_values)
            _sort_block(spreadsheet, ws, block, ascending)
            _regroup_block(ws, block)
            n += 1
    return n


def _block_rows(ws: gspread.Worksheet, block: dict) -> list:
    """Fetch the block's data rows, padded to full width/height."""
    data = ws.get(f"A{block['data_start']}:{LAST_COL}{block['data_end']}") or []
    rows = [list(r) + [""] * (N_COLS - len(r)) for r in data]
    n = block["data_end"] - block["data_start"] + 1
    rows += [[""] * N_COLS for _ in range(n - len(rows))]
    return rows


def _write_block(ws: gspread.Worksheet, block: dict, rows: list) -> None:
    ws.update(
        values=rows,
        range_name=f"A{block['data_start']}:{LAST_COL}{block['data_end']}",
        value_input_option="USER_ENTERED",
    )


def _ungroup_block(ws: gspread.Worksheet, block: dict, all_values: list) -> None:
    """Fill DATE/DAY/WORKPLACE down over repeat rows so sorting and matching
    work on complete data. Patches all_values in place."""
    current = None
    changed = False
    rows = []
    for r in range(block["data_start"], block["data_end"] + 1):
        row = list(all_values[r - 1]) if r <= len(all_values) else []
        row += [""] * (N_COLS - len(row))
        if row[COL_DATE].strip():
            current = row
        elif current and any(str(c).strip() for c in row):
            row[COL_DATE] = current[COL_DATE]
            row[COL_DAY] = current[COL_DAY]
            if not row[COL_WORKPLACE].strip():
                row[COL_WORKPLACE] = current[COL_WORKPLACE]
            changed = True
        rows.append(row)
        if r <= len(all_values):
            all_values[r - 1] = row
        else:
            all_values.extend([[]] * (r - len(all_values) - 1) + [row])
    if changed:
        _write_block(ws, block, rows)


def _regroup_block(ws: gspread.Worksheet, block: dict) -> None:
    """Group rows by day: the first row of each day carries DATE, DAY,
    WORKPLACE and the day's total hours; repeat rows of the same day are left
    blank in those columns. Assumes the block is sorted (same dates adjacent)."""
    rows = _block_rows(ws, block)
    n = len(rows)
    i = 0
    while i < n:
        day = rows[i][COL_DATE].strip()
        if not day:
            i += 1
            continue
        j = i
        total = 0.0
        while j < n and rows[j][COL_DATE].strip() == day:
            value = str(rows[j][COL_TIMESPENT]).strip()
            if value:
                try:
                    total += float(value)
                except ValueError:
                    pass
            if j > i:  # repeat row of the same day — blank grouped fields
                rows[j][COL_DATE] = ""
                rows[j][COL_DAY] = ""
                rows[j][COL_WORKPLACE] = ""
                rows[j][COL_TIMESPENT] = ""
            j += 1
        rows[i][COL_TIMESPENT] = total if total else ""
        i = j

    _write_block(ws, block, rows)


def _sort_block(spreadsheet: gspread.Spreadsheet, ws: gspread.Worksheet, block: dict, ascending: bool) -> None:
    spreadsheet.batch_update({
        "requests": [{
            "sortRange": {
                "range": {
                    "sheetId": ws.id,
                    "startRowIndex": block["data_start"] - 1,
                    "endRowIndex": block["data_end"],
                    "startColumnIndex": 0,
                    "endColumnIndex": N_COLS,
                },
                "sortSpecs": [{"dimensionIndex": COL_DATE, "sortOrder": "ASCENDING" if ascending else "DESCENDING"}],
            }
        }]
    })


def add_next_week(spreadsheet: gspread.Spreadsheet) -> str:
    """Append the next week block to the latest month section."""
    ws = get_tracker_ws(spreadsheet)
    sections, _ = parse_sections(ws)
    section = latest_section(sections)
    if section is None:
        raise SystemExit("No month sections found. Run: worklog template")

    weeks = weeks_of_month(section["year"], section["month"])
    if len(section["blocks"]) >= len(weeks):
        return f"'{month_title(section['year'], section['month'])}' already has all {len(weeks)} weeks. Use: worklog add-next-month"

    i = len(section["blocks"]) + 1
    monday, sunday = weeks[i - 1]
    label = week_label(monday, sunday)
    start = section["blocks"][-1]["data_end"] + 2 if section["blocks"] else section["title_row"] + 2
    grid = [[label] + [""] * (N_COLS - 1), list(HEADERS)]
    grid.extend([[""] * N_COLS for _ in range(ROWS_PER_WEEK)])
    end = start + len(grid) - 1
    if end > ws.row_count:
        ws.add_rows(end - ws.row_count + 20)
    ws.update(values=grid, range_name=f"A{start}:{LAST_COL}{end}")
    requests = _block_format_requests(ws.id, start - 1, ROWS_PER_WEEK)
    requests.append(_table_request(ws.id, table_name(section["year"], section["month"], monday.isocalendar()[1]), start, start + 1 + ROWS_PER_WEEK))
    spreadsheet.batch_update({"requests": requests})
    return f"Added {label} to '{month_title(section['year'], section['month'])}'"


def add_next_month(spreadsheet: gspread.Spreadsheet, archive_previous: bool = True) -> str:
    """Append the next month section; optionally move the previous one to the Archive tab."""
    ws = get_tracker_ws(spreadsheet)
    sections, _ = parse_sections(ws)
    section = latest_section(sections)
    if section is None:
        today = date.today()
        return f"Created '{append_month_section(spreadsheet, today.year, today.month)}'"

    year, month = section["year"], section["month"]
    year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    message = f"Created '{append_month_section(spreadsheet, year, month)}'"
    if archive_previous:
        archive_month(spreadsheet, section["year"], section["month"])
        message += f"; archived '{month_title(section['year'], section['month'])}' to '{ARCHIVE_TAB}' tab"
    return message


def archive_month(spreadsheet: gspread.Spreadsheet, year: int, month: int) -> None:
    """Move a month section (values + formatting) to the Archive tab."""
    ws = get_tracker_ws(spreadsheet)
    sections, all_values = parse_sections(ws)
    section = _find_section(sections, year, month)
    if section is None:
        raise SystemExit(f"Section '{month_title(year, month)}' not found in '{TAB_NAME}'.")

    try:
        archive_ws = spreadsheet.worksheet(ARCHIVE_TAB)
    except gspread.WorksheetNotFound:
        archive_ws = spreadsheet.add_worksheet(title=ARCHIVE_TAB, rows=400, cols=N_COLS)
        spreadsheet.batch_update({"requests": _column_requests(archive_ws.id)})

    src_start = section["title_row"] - 1  # 0-based, inclusive
    src_end = section["blocks"][-1]["data_end"] + 1 if section["blocks"] else section["title_row"] + 1  # 0-based, exclusive (incl. separator)
    n_rows = src_end - src_start

    dest_values = archive_ws.get_all_values()
    dest_start = len(dest_values) + 1 if dest_values else 0  # 0-based, one blank gap
    if dest_start + n_rows > archive_ws.row_count:
        archive_ws.add_rows(dest_start + n_rows - archive_ws.row_count + 20)

    spreadsheet.batch_update({
        "requests": [
            {
                "copyPaste": {
                    "source": {"sheetId": ws.id, "startRowIndex": src_start, "endRowIndex": src_end, "startColumnIndex": 0, "endColumnIndex": N_COLS},
                    "destination": {"sheetId": archive_ws.id, "startRowIndex": dest_start, "endRowIndex": dest_start + n_rows, "startColumnIndex": 0, "endColumnIndex": N_COLS},
                    "pasteType": "PASTE_NORMAL",
                }
            },
            {
                "deleteDimension": {
                    "range": {"sheetId": ws.id, "dimension": "ROWS", "startIndex": src_start, "endIndex": src_end}
                }
            },
        ]
    })
