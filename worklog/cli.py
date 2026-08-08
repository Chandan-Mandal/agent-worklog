"""worklog CLI entry point."""

import argparse

from . import config as config_store


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="worklog",
        description="worklog-agent: log daily work to Google Sheets and share standup updates.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup", help="Interactive setup: Google Sheets, Slack, Jira")

    log_p = sub.add_parser("log", help="Append a work entry to your tracker sheet")
    log_p.add_argument("--task", required=True, help="What you worked on")
    log_p.add_argument("--hours", type=float, help="Total hours, e.g. 1.5")
    log_p.add_argument("--priority", choices=["High", "Medium", "Low"], default="")
    log_p.add_argument("--workplace", choices=["Home", "Office", "Sick", "Casual"], default="")
    log_p.add_argument("--time", default="", help='Time range, e.g. "11AM - 12PM"')
    log_p.add_argument("--date", default=None, help="Entry date YYYY-MM-DD (default: today)")
    log_p.add_argument("--assigned-on", default="", help="Date the task was assigned, YYYY-MM-DD")
    log_p.add_argument("--notes", default="")

    sub.add_parser("status", help="Show current configuration")

    args = parser.parse_args()

    if args.command == "setup":
        from . import setup_flow

        setup_flow.run()
    elif args.command == "log":
        from . import sheets

        config = config_store.require()
        sheets.append_entry(
            config,
            task=args.task,
            hours=args.hours,
            priority=args.priority,
            workplace=args.workplace,
            time_range=args.time,
            entry_date=args.date,
            assigned_on=args.assigned_on,
            notes=args.notes,
        )
        print(f"Logged: {args.task}")
        print(f"Sheet: {config['google'].get('sheet_url', '')}")
    elif args.command == "status":
        config = config_store.load()
        if not config:
            print("Not configured. Run: worklog setup")
            return
        google = config.get("google", {})
        print(f"Config: {config_store.CONFIG_PATH}")
        print(f"Sheet:  {google.get('sheet_url', '(not set)')}")
        print(f"Slack:  {'configured' if config.get('slack', {}).get('webhook_url') else 'not configured'}")
        print(f"Jira:   {'configured' if config.get('jira', {}).get('base_url') else 'not configured'}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
