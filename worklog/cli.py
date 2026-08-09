"""worklog CLI entry point."""

import argparse
from datetime import date

from . import config as config_store


def _parse_year_month(value: str) -> tuple:
    year, month = value.split("-")
    return int(year), int(month)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="worklog",
        description="agent-worklog: log daily work to Google Sheets and share standup updates.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup", help="Interactive setup: Google Sheets, Slack, Jira")

    log_p = sub.add_parser("log", help="Log a work entry into the right month/week block")
    log_p.add_argument("--task", required=True, help="What you worked on (SUBTASK)")
    log_p.add_argument("--tag", default="", help="TASK_TAG, e.g. project or epic name")
    log_p.add_argument("--type", dest="work_type", choices=["DEV", "DELIVERY", "OPS", "AD-HOC", "MEETING", "LEARNING"], default="", help="Kind of work")
    log_p.add_argument("--priority", choices=["High", "Medium", "Low"], default="")
    log_p.add_argument("--workplace", choices=["Home", "Office", "Leave"], default="")
    log_p.add_argument("--timelog", default="", help='Time range, e.g. "1PM - 2PM". Logging the same task+date again appends to it')
    log_p.add_argument("--hours", type=float, help="TIMESPENT in hours, e.g. 1.5 (adds up when merging)")
    log_p.add_argument("--date", default=None, help="Entry date YYYY-MM-DD (default: today)")
    log_p.add_argument("--assigned-at", default="", help="Date the task was assigned, YYYY-MM-DD")
    log_p.add_argument("--assigned-by", default="", help="Who assigned it")
    log_p.add_argument("--notes", default="")
    log_p.add_argument("--jira", default="", help="Jira issue key or link, e.g. BDP-141")

    adhoc_p = sub.add_parser("adhoc", help="Log a small ad-hoc item into the day's single Ad-hoc roll-up row")
    adhoc_p.add_argument("text", help='What you did, e.g. "sent mail to xyz"')
    adhoc_p.add_argument("--mins", type=int, default=15, help="Rough minutes spent (default: 15)")
    adhoc_p.add_argument("--workplace", choices=["Home", "Office", "Leave"], default="")
    adhoc_p.add_argument("--date", default=None, help="Entry date YYYY-MM-DD (default: today)")

    template_p = sub.add_parser("template", help="Create month tabs with week blocks")
    template_p.add_argument("--from", dest="start", default=None, help="Start month YYYY-MM (default: current month)")
    template_p.add_argument("--to", dest="end", default=None, help="End month YYYY-MM (default: December of start year)")

    sub.add_parser("add-next-week", help="Append the next week block to the latest month tab")

    next_month_p = sub.add_parser("add-next-month", help="Create the next month tab and archive the previous one")
    next_month_p.add_argument("--no-archive", action="store_true", help="Keep the previous month tab visible")

    sort_p = sub.add_parser("sort", help="Sort week blocks by date")
    sort_p.add_argument("--desc", action="store_true", help="Sort descending (default: ascending)")
    sort_p.add_argument("--month", default=None, help="Limit to one month section, e.g. 'AUG 2026' (default: all)")

    jira_p = sub.add_parser("jira", help="Jira integration")
    jira_sub = jira_p.add_subparsers(dest="jira_command")
    sync_p = jira_sub.add_parser("sync", help="Sync your assigned issues into the Tasklog tab")
    sync_p.add_argument("--jql", default=None, help="Custom JQL (default: open issues assigned to you)")

    sub.add_parser("status", help="Show current configuration")

    args = parser.parse_args()

    if args.command == "setup":
        from . import setup_flow

        setup_flow.run()
        return
    if args.command == "status":
        _status()
        return
    if args.command is None:
        parser.print_help()
        return

    from . import sheets, template

    config = config_store.require()
    spreadsheet = sheets.open_configured(config)
    ascending = config.get("sort_order", "asc") == "asc"

    if args.command == "log":
        entry_date = template.parse_date(args.date)
        tab = template.insert_entry(
            spreadsheet,
            entry_date,
            task_tag=args.tag,
            subtask=args.task,
            work_type=args.work_type,
            priority=args.priority,
            workplace=args.workplace,
            timelog=args.timelog,
            timespent=args.hours,
            assigned_at=args.assigned_at,
            assigned_by=args.assigned_by,
            notes=args.notes,
            jira=args.jira,
            ascending=ascending,
        )
        print(f"Logged into '{tab}': {args.task}")
        print(f"Sheet: {config['google'].get('sheet_url', '')}")
    elif args.command == "adhoc":
        entry_date = template.parse_date(args.date)
        hours = round(args.mins / 60, 2)
        tab = template.insert_entry(
            spreadsheet,
            entry_date,
            task_tag="adhoc",
            subtask="Ad-hoc",
            work_type="AD-HOC",
            priority="Low",
            workplace=args.workplace,
            timespent=hours,
            notes=f"{args.text} ({args.mins}m)",
            ascending=ascending,
        )
        print(f"Ad-hoc logged into '{tab}': {args.text} ({args.mins}m)")
    elif args.command == "template":
        today = date.today()
        start = _parse_year_month(args.start) if args.start else (today.year, today.month)
        end = _parse_year_month(args.end) if args.end else (start[0], 12)
        created = template.build_range(spreadsheet, start, end)
        print(f"Created tabs: {', '.join(created) if created else '(all already exist)'}")
    elif args.command == "add-next-week":
        print(template.add_next_week(spreadsheet))
    elif args.command == "add-next-month":
        print(template.add_next_month(spreadsheet, archive_previous=not args.no_archive))
    elif args.command == "jira":
        from . import jira

        if args.jira_command == "sync":
            print(jira.sync(config, spreadsheet, jql=args.jql))
        else:
            print("Usage: worklog jira sync [--jql ...]")
    elif args.command == "sort":
        ascending = not args.desc
        config["sort_order"] = "asc" if ascending else "desc"
        config_store.save(config)
        n = template.sort_blocks(spreadsheet, args.month, ascending)
        order = "ascending" if ascending else "descending"
        scope = f"in '{args.month}'" if args.month else "across all months"
        print(f"Sorted {n} week blocks {scope} ({order}). Default order saved: {order}.")


def _status() -> None:
    config = config_store.load()
    if not config:
        print("Not configured. Run: worklog setup")
        return
    google = config.get("google", {})
    print(f"Config: {config_store.CONFIG_PATH}")
    print(f"Sheet:  {google.get('sheet_url', '(not set)')}")
    print(f"Sort:   {config.get('sort_order', 'asc')}")
    print(f"Slack:  {'configured' if config.get('slack', {}).get('webhook_url') else 'not configured'}")
    print(f"Jira:   {'configured' if config.get('jira', {}).get('base_url') else 'not configured'}")


if __name__ == "__main__":
    main()
