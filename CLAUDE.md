# agent-worklog

Local agent that logs daily work to a Google Sheet and (soon) posts standups to Slack/Geekbot.

## Architecture
- `worklog/cli.py` — argparse CLI: `setup`, `log`, `template`, `add-next-week`, `add-next-month`, `sort`, `status`
- `worklog/setup_flow.py` — interactive setup wizard (Google required, Slack/Jira optional)
- `worklog/sheets.py` — gspread client helpers
- `worklog/template.py` — single-tab template engine: month sections, week blocks, insert/sort/add-next-week/month/archive
- `worklog/config.py` — config at `~/.worklog/config.json`

## Conventions
- Sheet layout: single "Worklog" tab; month sections ("MONTH - AUG,2026") stacked vertically, each with week blocks (label row, header row, data rows); archive = move section to "Archive" tab
- Columns: DATE, DAY, TASK_TAG, SUBTASK, PRIORITY, WORKPLACE, TIMELOG, TIMESPENT, ASSIGNED_AT, ASSIGNED_BY, NOTES
- Same date+subtask logged again merges: TIMELOG appended, hours summed
- Never commit credentials; `.gitignore` blocks `*.json`

## When the user asks to log work
Parse their message into one `worklog log` call per task, filling task/hours/priority/workplace/time from context. Default date is today.
