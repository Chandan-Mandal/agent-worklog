# worklog-agent

A local agent that logs your daily work into a Google Sheet tracker and helps you share standup updates (Slack/Geekbot) — designed to be driven from your terminal or from an AI CLI like Claude Code.

## Why

Every day you have to tell your team what you did yesterday and what you plan to do today. worklog-agent gives you one place to capture that:

- A professionally formatted **Daily Work Tracker** Google Sheet (created for you on setup)
- A `worklog` CLI to append entries in seconds
- (Coming soon) Standup message generation + posting to Slack/Geekbot, Jira sync

## Install

```bash
git clone <this-repo>
cd worklog-agent
pip install -e .
```

## Setup

```bash
worklog setup
```

The wizard walks you through:

1. **Google Sheets (required)** — provide a service account JSON key. The agent then *creates the base worklog sheet for you*: scorecard with total hours, frozen headers, alternating row colors, Priority/Workplace dropdowns, date pickers, number formats — and shares it with your Google account.
2. **Slack (optional)** — webhook/channel for your standup updates.
3. **Jira (optional)** — credentials for future task sync.

Config is stored at `~/.worklog/config.json` (chmod 600). Keep your service account key outside the repo.

### Getting a Google service account key (~5 min, one time)

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project
2. Enable the **Google Sheets API** and **Google Drive API**
3. IAM & Admin → Service Accounts → Create service account
4. Keys → Add key → JSON → download the file
5. Point `worklog setup` at that file

If you want to use an **existing** sheet instead of a generated one, share it with the service account's email (Editor) and give the setup wizard its spreadsheet ID.

## Usage

```bash
# Log an entry
worklog log --task "Reviewed schema design PR" --hours 1.5 \
    --priority High --workplace Office --time "11AM - 12:30PM"

# Check configuration
worklog status
```

## Sheet structure

| Date | Task | Priority | Workplace | Time Range | Total Hours | Assigned On | Notes |
|------|------|----------|-----------|------------|-------------|-------------|-------|

- **Total Hours Logged** scorecard at the top auto-sums the Total Hours column
- **Priority**: High / Medium / Low (dropdown)
- **Workplace**: Home / Office / Sick / Casual (dropdown)

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
