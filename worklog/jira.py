"""Jira integration: sync your assigned issues into a TASKLOG tab."""

import requests

from . import template

TASKLOG_TAB = "Tasklog"
DEFAULT_JQL = "assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC"

HEADERS = ["KEY", "SUMMARY", "STATUS", "PRIORITY", "TYPE", "PROJECT", "REPORTER", "CREATED", "DUE", "UPDATED", "LINK"]
N_COLS = len(HEADERS)
LAST_COL = "K"

DARK = {"red": 0.15, "green": 0.19, "blue": 0.28}
WHITE = {"red": 1, "green": 1, "blue": 1}


def _auth(config: dict):
    jira = config.get("jira", {})
    if not jira.get("base_url") or not jira.get("api_token"):
        raise SystemExit("Jira is not configured. Run: worklog setup")
    return jira["base_url"].rstrip("/"), (jira["email"], jira["api_token"])


def fetch_issues(config: dict, jql: str = None) -> list:
    base, auth = _auth(config)
    jql = jql or config.get("jira", {}).get("jql", DEFAULT_JQL)
    issues, next_token = [], None
    while True:
        params = {
            "jql": jql,
            "maxResults": 100,
            "fields": "summary,status,priority,issuetype,project,reporter,created,duedate,updated",
        }
        if next_token:
            params["nextPageToken"] = next_token
        r = requests.get(f"{base}/rest/api/3/search/jql", auth=auth, params=params, timeout=30)
        r.raise_for_status()
        payload = r.json()
        issues.extend(payload.get("issues", []))
        next_token = payload.get("nextPageToken")
        if not next_token or payload.get("isLast", True):
            break
    return issues


def _issue_row(issue: dict, base: str) -> list:
    f = issue["fields"]

    def get(field, *path):
        value = f.get(field)
        for key in path:
            if not value:
                return ""
            value = value.get(key)
        return value or ""

    return [
        issue["key"],
        get("summary") if isinstance(f.get("summary"), str) else f.get("summary") or "",
        get("status", "name"),
        get("priority", "name"),
        get("issuetype", "name"),
        get("project", "name"),
        get("reporter", "displayName"),
        (f.get("created") or "")[:10],
        f.get("duedate") or "",
        (f.get("updated") or "")[:10],
        f"{base}/browse/{issue['key']}",
    ]


def get_tasklog_ws(spreadsheet):
    import gspread

    try:
        return spreadsheet.worksheet(TASKLOG_TAB)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=TASKLOG_TAB, rows=200, cols=N_COLS)
        ws.update(values=[HEADERS], range_name=f"A1:{LAST_COL}1")
        requests_body = [
            {
                "repeatCell": {
                    "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": N_COLS},
                    "cell": {"userEnteredFormat": {"backgroundColor": DARK, "textFormat": {"foregroundColor": WHITE, "bold": True}, "horizontalAlignment": "CENTER"}},
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": ws.id, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            {
                "addTable": {
                    "table": {
                        "name": "Tasklog",
                        "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 150, "startColumnIndex": 0, "endColumnIndex": N_COLS},
                    }
                }
            },
        ]
        spreadsheet.batch_update({"requests": requests_body})
        return ws


def sync(config: dict, spreadsheet, jql: str = None) -> str:
    """Upsert assigned issues into the Tasklog tab, keyed by issue KEY."""
    base, _ = _auth(config)
    issues = fetch_issues(config, jql)
    ws = get_tasklog_ws(spreadsheet)

    existing = ws.get_all_values()
    row_by_key = {row[0]: i for i, row in enumerate(existing, 1) if i > 1 and row and row[0].strip()}
    next_free = len(existing) + 1

    updates = []
    added = updated = 0
    for issue in issues:
        row_values = _issue_row(issue, base)
        if issue["key"] in row_by_key:
            updates.append({"range": f"A{row_by_key[issue['key']]}:{LAST_COL}{row_by_key[issue['key']]}", "values": [row_values]})
            updated += 1
        else:
            updates.append({"range": f"A{next_free}:{LAST_COL}{next_free}", "values": [row_values]})
            next_free += 1
            added += 1
    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")
    return f"Synced {len(issues)} issues into '{TASKLOG_TAB}' ({added} new, {updated} refreshed)"
