import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from vault_launcher.jsonfile import JsonFileError, read_json, write_json_atomic
from vault_launcher.store import SORT_MODES, SORT_RECENT

log = logging.getLogger(__name__)

THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEMES = (THEME_SYSTEM, THEME_LIGHT, THEME_DARK)


@dataclass
class Settings:
    theme: str = THEME_SYSTEM
    close_after_open: bool = True
    sort_mode: str = SORT_RECENT
    window_geometry: str | None = None

    @classmethod
    def from_dict(cls, data: object) -> "Settings":
        settings = cls()
        if not isinstance(data, dict):
            return settings
        if data.get("theme") in THEMES:
            settings.theme = data["theme"]
        if isinstance(data.get("close_after_open"), bool):
            settings.close_after_open = data["close_after_open"]
        if data.get("sort_mode") in SORT_MODES:
            settings.sort_mode = data["sort_mode"]
        if isinstance(data.get("window_geometry"), str):
            settings.window_geometry = data["window_geometry"]
        return settings


def load_settings(path: Path) -> Settings:
    try:
        return Settings.from_dict(read_json(path))
    except JsonFileError as e:
        log.warning("cannot read settings, using defaults: %s", e)
        return Settings()


def save_settings(path: Path, settings: Settings) -> None:
    write_json_atomic(path, asdict(settings))
