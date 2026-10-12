import logging
import os
import secrets
import shutil
import socket
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from vault_launcher.jsonfile import JsonFileError, read_json, write_json_atomic

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ObsidianVault:
    id: str
    path: str
    ts: int = 0
    open: bool = False


def parse_obsidian_config(data: object) -> list[ObsidianVault]:
    """Extract vaults from the parsed content of obsidian.json, skipping malformed entries."""
    if not isinstance(data, dict) or not isinstance(data.get("vaults"), dict):
        raise ValueError("missing 'vaults' object")
    result = []
    for vault_id, entry in data["vaults"].items():
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            log.warning("skipping malformed vault entry %r", vault_id)
            continue
        ts = entry.get("ts")
        result.append(
            ObsidianVault(
                id=str(vault_id),
                path=entry["path"],
                ts=ts if isinstance(ts, int) else 0,
                open=entry.get("open") is True,
            )
        )
    return result


def read_obsidian_vaults(config_files: Iterable[Path]) -> list[ObsidianVault] | None:
    """Merge vaults from all readable obsidian.json files.

    Returns None when no file could be read, so the caller can skip syncing
    instead of treating every known vault as removed.
    """
    found_any = False
    vaults: dict[str, ObsidianVault] = {}
    for path in config_files:
        try:
            data = read_json(path)
            if data is None:
                continue
            parsed = parse_obsidian_config(data)
        except (JsonFileError, ValueError) as e:
            log.warning("cannot read Obsidian config %s: %s", path, e)
            continue
        found_any = True
        for vault in parsed:
            vaults.setdefault(vault.id, vault)
    return list(vaults.values()) if found_any else None


# Obsidian (Electron) holds this symlink to "<hostname>-<pid>" in its config folder while
# it runs, and removes it on a clean exit.
LOCK_NAME = "SingletonLock"


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def obsidian_running(
    config_dir: Path,
    pid_alive: Callable[[int], bool] | None = pid_alive,
    hostname: str | None = None,
) -> bool:
    """Whether an Obsidian instance uses the config in config_dir.

    pid_alive=None means processes of the host are not visible (flatpak sandbox);
    then a present lock counts as running, even if Obsidian crashed and left it behind.
    """
    try:
        target = os.readlink(config_dir / LOCK_NAME)
    except FileNotFoundError:
        return False
    except OSError:
        return (config_dir / LOCK_NAME).exists()
    host, _, pid = target.rpartition("-")
    if pid_alive is None or not pid.isdigit():
        return True
    if host != (hostname or socket.gethostname()):
        return True  # another machine sharing this home folder
    return pid_alive(int(pid))


def register_vault(config_file: Path, path: str, now_ms: int | None = None) -> str:
    """Add a folder to Obsidian's vault list the way Obsidian does, return its id.

    Obsidian reads obsidian.json only at startup and later overwrites it with its
    in-memory state, so this must only be called while Obsidian is not running.
    Everything else in the file is kept; the previous version is saved as .bak.
    """
    data = read_json(config_file)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise JsonFileError(f"{config_file}: not a JSON object")
    vaults = data.setdefault("vaults", {})
    if not isinstance(vaults, dict):
        raise JsonFileError(f"{config_file}: 'vaults' is not an object")
    path = os.path.abspath(path)
    for vault_id, entry in vaults.items():
        if isinstance(entry, dict) and entry.get("path") == path:
            return vault_id
    vault_id = secrets.token_hex(8)
    while vault_id in vaults:
        vault_id = secrets.token_hex(8)
    vaults[vault_id] = {"path": path, "ts": now_ms if now_ms is not None else int(time.time() * 1000)}
    if config_file.exists():
        shutil.copy2(config_file, config_file.with_name(config_file.name + ".bak"))
    write_json_atomic(config_file, data)
    log.info("registered %s in %s as %s", path, config_file, vault_id)
    return vault_id
