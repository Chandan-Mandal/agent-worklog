# agent-worklog

A local agent that logs your daily work into a Google Sheet tracker and helps you share standup updates (Slack/Geekbot) — designed to be driven from your terminal or from an AI CLI like Claude Code.

## Why

Every day you have to tell your team what you did yesterday and what you plan to do today. agent-worklog gives you one place to capture that:

- A professionally formatted **Daily Work Tracker** Google Sheet (created for you on setup)
- A `worklog` CLI to append entries in seconds
- (Coming soon) Standup message generation + posting to Slack/Geekbot, Jira sync

## Install

```bash
git clone <this-repo>
cd agent-worklog
pip install -e .
```

## Setup

```bash
worklog setup
```

The wizard walks you through:

1. **Google Sheets (required)** — provide a service account JSON key, create a blank sheet at [sheets.new](https://sheets.new) and share it with the service account (Google no longer lets service accounts own files). The agent then *initializes the base worklog tracker inside it*: scorecard with total hours, frozen headers, alternating row colors, Priority/Workplace dropdowns, date pickers, number formats.
2. **Slack (optional)** — webhook/channel for your standup updates.
3. **Jira (optional)** — credentials for future task sync.

Config is stored at `~/.worklog/config.json` (chmod 600). Keep your service account key outside the repo.

### Getting a Google service account key (~5 min, one time)

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project
2. Enable the **Google Sheets API** and **Google Drive API**
3. IAM & Admin → Service Accounts → Create service account
4. Keys → Add key → JSON → download the file
5. Point `worklog setup` at that file

Prefer the terminal? With [gcloud](https://cloud.google.com/sdk) installed:

```bash
gcloud projects create agent-worklog-<something-unique>
gcloud config set project agent-worklog-<something-unique>
gcloud services enable sheets.googleapis.com drive.googleapis.com
gcloud iam service-accounts create agent-worklog
gcloud iam service-accounts keys create ~/.worklog/google-sa-key.json \
    --iam-account=agent-worklog@agent-worklog-<something-unique>.iam.gserviceaccount.com
```

To use an **existing** sheet, share it with the service account's email (Editor) and paste its URL into the setup wizard — you can skip the tracker initialization to keep your current layout.

## Usage

```bash
# Log an entry — lands in the right month tab and week block automatically
worklog log --task "Reviewed schema design PR" --tag data-platform \
    --hours 1.5 --priority High --timelog "11AM - 12:30PM" \
    --assigned-by CTO --assigned-at 2026-08-05

# Create month tabs (defaults: current month through December)
worklog template --from 2026-08 --to 2026-12

# Grow the sheet over time
worklog add-next-week     # append the next week block to the latest month
worklog add-next-month    # create next month's tab, archive (hide) the previous

# Sorting (persisted as your default)
worklog sort              # ascending by date within each week block
worklog sort --desc

# Check configuration
worklog status
```

## Sheet structure

Everything lives in **one tab** (`Worklog`) — month sections stacked vertically, each made of week blocks:

```
MONTH - AUG,2026                                TOTAL HRS  <auto-sum>

WEEK 1 (1-2)
DATE | DAY | TASK_TAG | SUBTASK | PRIORITY | WORKPLACE | TIMELOG | TIMESPENT | ASSIGNED_AT | ASSIGNED_BY | NOTES
...

WEEK 2 (3-9)
...

MONTH - SEP,2026
...
```

- Weeks are Monday–Sunday, clipped to the month
- `worklog log` finds the right month section + week block by date, fills the first empty row, and keeps the block sorted
- **Priority**: High / Medium / Low; **Workplace**: Home / Office / Leave (dropdowns); each month's TOTAL HRS auto-sums that month's entries
- Logging the same task twice on one day merges TIMELOG ("1PM - 2PM, 5PM - 7PM") and adds up hours
- When a month changes, `add-next-month` moves the previous month's section to an `Archive` tab (values + formatting preserved)

## Using with Claude Code (or any AI CLI)

Clone the repo and open it in Claude Code. The codebase is small and prompt-friendly — customize it to your needs by just asking, e.g.:

- "Add a `Blocked By` column to the tracker"
- "Change the workplace options to Remote/Onsite"
- "When I say 'log my day', parse my message and call `worklog log` for each task"

## Roadmap

- [ ] `worklog standup` — generate yesterday/today standup text from the sheet
- [ ] Post standup to Slack / Geekbot automatically
- [ ] Jira: pull assigned tickets, link entries to issues
- [ ] Natural-language entry (`worklog log "built the setup wizard, 2h, high"`)

## License

MIT
