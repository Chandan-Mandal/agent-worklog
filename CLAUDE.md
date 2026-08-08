# worklog-agent

Local agent that logs daily work to a Google Sheet and (soon) posts standups to Slack/Geekbot.

## Architecture
- `worklog/cli.py` — argparse CLI: `setup`, `log`, `status`
- `worklog/setup_flow.py` — interactive setup wizard (Google required, Slack/Jira optional)
- `worklog/sheets.py` — gspread integration; creates the formatted base tracker, appends entries
- `worklog/config.py` — config at `~/.worklog/config.json`

## Conventions
- Sheet layout: scorecard in row 1, headers in row 3 (`HEADER_ROW`), data from row 4
- Columns: Date, Task, Priority, Workplace, Time Range, Total Hours, Assigned On, Notes
- Never commit credentials; `.gitignore` blocks `*.json`

## When the user asks to log work
Parse their message into one `worklog log` call per task, filling task/hours/priority/workplace/time from context. Default date is today.
