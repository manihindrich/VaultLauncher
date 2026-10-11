import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from vault_launcher.jsonfile import JsonFileError, read_json

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
