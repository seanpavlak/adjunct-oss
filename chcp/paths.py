"""Repository paths for config data and assets."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"


def courses_config_path() -> Path:
    return CONFIG_DIR / "courses.json"


def announcements_config_path() -> Path:
    return CONFIG_DIR / "announcements.json"
