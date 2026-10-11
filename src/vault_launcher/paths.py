import os
from collections.abc import Mapping
from pathlib import Path

APP_DIR_NAME = "vault-launcher"
OBSIDIAN_FLATPAK_ID = "md.obsidian.Obsidian"


def is_flatpak() -> bool:
    return Path("/.flatpak-info").exists()


def _xdg_dir(env: Mapping[str, str], var: str, home: Path, default: str) -> Path:
    value = env.get(var)
    if value and os.path.isabs(value):
        return Path(value)
    return home / default


def host_config_home(env: Mapping[str, str] = os.environ, home: Path | None = None) -> Path:
    """The host's XDG config dir, also from inside a flatpak sandbox.

    Inside a flatpak XDG_CONFIG_HOME points to ~/.var/app/<id>/config, while
    flatpak exposes the host value as HOST_XDG_CONFIG_HOME.
    """
    home = home or Path.home()
    if "FLATPAK_ID" in env or "HOST_XDG_CONFIG_HOME" in env:
        return _xdg_dir(env, "HOST_XDG_CONFIG_HOME", home, ".config")
    return _xdg_dir(env, "XDG_CONFIG_HOME", home, ".config")


def obsidian_config_candidates(
    env: Mapping[str, str] = os.environ, home: Path | None = None
) -> list[Path]:
    """Possible locations of obsidian.json: native, flatpak and snap installs."""
    home = home or Path.home()
    return [
        host_config_home(env, home) / "obsidian" / "obsidian.json",
        home / ".var" / "app" / OBSIDIAN_FLATPAK_ID / "config" / "obsidian" / "obsidian.json",
        home / "snap" / "obsidian" / "current" / ".config" / "obsidian" / "obsidian.json",
    ]


def app_config_dir(env: Mapping[str, str] = os.environ, home: Path | None = None) -> Path:
    home = home or Path.home()
    return _xdg_dir(env, "XDG_CONFIG_HOME", home, ".config") / APP_DIR_NAME


def app_data_dir(env: Mapping[str, str] = os.environ, home: Path | None = None) -> Path:
    home = home or Path.home()
    return _xdg_dir(env, "XDG_DATA_HOME", home, ".local/share") / APP_DIR_NAME


def settings_file(env: Mapping[str, str] = os.environ, home: Path | None = None) -> Path:
    return app_config_dir(env, home) / "settings.json"


def vaults_file(env: Mapping[str, str] = os.environ, home: Path | None = None) -> Path:
    return app_data_dir(env, home) / "vaults.json"
