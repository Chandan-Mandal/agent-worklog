"""Config storage for worklog-agent. Lives at ~/.worklog/config.json."""

import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("WORKLOG_HOME", Path.home() / ".worklog"))
CONFIG_PATH = CONFIG_DIR / "config.json"


def load() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(CONFIG_PATH, 0o600)


def require() -> dict:
    config = load()
    if not config.get("google", {}).get("sheet_id"):
        raise SystemExit("worklog is not configured yet. Run: worklog setup")
    return config
