"""Private machine configuration, kept outside the skill package."""

import os
from pathlib import Path


def config_dir():
    return Path(os.environ.get("JEV_CONFIG_DIR", Path.home() / ".config" / "jev-browser"))


def state_dir():
    return Path(os.environ.get("JEV_STATE_DIR", Path.home() / ".local" / "share" / "jev-browser"))


def load_environment():
    for path in (config_dir() / ".env", Path.cwd() / ".env"):
        if path.exists():
            for line in path.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
