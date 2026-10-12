import os
from collections.abc import Callable, Mapping
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


def icon_search_dirs(env: Mapping[str, str] = os.environ, home: Path | None = None) -> list[Path]:
    """Icon theme directories per XDG, plus NixOS profiles and flatpak exports.

    Qt only searches these itself when a desktop platform theme plugin is loaded.
    """
    home = home or Path.home()
    data_dirs = [_xdg_dir(env, "XDG_DATA_HOME", home, ".local/share")]
    data_dirs += [Path(d) for d in env.get("XDG_DATA_DIRS", "").split(":") if os.path.isabs(d)]
    user = env.get("USER", "")
    data_dirs += [
        Path("/usr/local/share"),
        Path("/usr/share"),
        home / ".nix-profile/share",
        Path(f"/etc/profiles/per-user/{user}/share") if user else None,
        Path("/run/current-system/sw/share"),
        home / ".local/share/flatpak/exports/share",
        Path("/var/lib/flatpak/exports/share"),
        Path("/run/host/usr/share"),  # host /usr inside a flatpak sandbox
    ]
    result: list[Path] = [home / ".icons"]
    for d in data_dirs:
        if d is not None and (d / "icons") not in result:
            result.append(d / "icons")
    return result


HOST_PATH_XATTR = "user.document-portal.host-path"


def _document_portal_roots(env: Mapping[str, str]) -> list[str]:
    roots = ["/run/flatpak/doc"]
    runtime_dir = env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    roots.append(os.path.join(runtime_dir, "doc"))
    return roots


def is_document_portal_path(path: str, env: Mapping[str, str] = os.environ) -> bool:
    return any(path == r or path.startswith(r + "/") for r in _document_portal_roots(env))


def host_path(
    path: str,
    env: Mapping[str, str] = os.environ,
    getxattr: Callable[[str, str], bytes] = os.getxattr,
) -> str | None:
    """The real path of a folder returned by a file chooser.

    Inside a flatpak the file chooser portal can hand out a document portal path
    (/run/user/<uid>/doc/<id>/<name>) that only this sandbox understands. The
    document portal exposes the original location as an extended attribute.
    Returns None if the real path cannot be determined.
    """
    if not is_document_portal_path(path, env):
        return path
    try:
        value = getxattr(path, HOST_PATH_XATTR).rstrip(b"\0").decode()
    except (OSError, UnicodeDecodeError):
        return None
    if os.path.isabs(value) and not is_document_portal_path(value, env):
        return value
    return None


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
