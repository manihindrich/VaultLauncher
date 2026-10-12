import hashlib
import locale
import logging
import os
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from vault_launcher.jsonfile import JsonFileError, read_json, write_json_atomic
from vault_launcher.obsidian_config import ObsidianVault

log = logging.getLogger(__name__)

STORE_VERSION = 1

SOURCE_OBSIDIAN = "obsidian"
SOURCE_MANUAL = "manual"

SORT_RECENT = "recent"
SORT_NAME = "name"
SORT_LABEL = "label"
SORT_MODES = (SORT_RECENT, SORT_NAME, SORT_LABEL)


def normalize_path(path: str) -> str:
    return os.path.normpath(os.path.expanduser(path))


def manual_key(path: str) -> str:
    digest = hashlib.sha1(normalize_path(path).encode("utf-8")).hexdigest()
    return f"manual:{digest[:16]}"


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class Vault:
    key: str
    path: str
    obsidian_id: str | None = None
    label: str | None = None
    source: str = SOURCE_MANUAL
    in_obsidian: bool = False
    obsidian_ts: int = 0
    last_opened: int = 0
    hidden: bool = False

    @property
    def name(self) -> str:
        return os.path.basename(self.path.rstrip(os.sep)) or self.path

    @property
    def display_name(self) -> str:
        return self.label or self.name

    @property
    def last_used(self) -> int:
        return max(self.obsidian_ts, self.last_opened)

    @classmethod
    def from_dict(cls, data: dict) -> "Vault":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class SyncResult:
    added: list[Vault] = field(default_factory=list)
    updated: list[Vault] = field(default_factory=list)
    missing: list[Vault] = field(default_factory=list)
    removed: list[Vault] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.added or self.updated or self.removed)


def _collate(text: str) -> str:
    try:
        return locale.strxfrm(text.casefold())
    except (OSError, ValueError):
        return text.casefold()


def sort_vaults(vaults: Iterable[Vault], mode: str) -> list[Vault]:
    if mode == SORT_RECENT:
        return sorted(vaults, key=lambda v: (-v.last_used, _collate(v.display_name)))
    if mode == SORT_LABEL:
        return sorted(vaults, key=lambda v: (_collate(v.display_name), v.path))
    return sorted(vaults, key=lambda v: (_collate(v.name), v.path))


class VaultStore:
    def __init__(self, path: Path, folder_exists: Callable[[str], bool] = os.path.isdir):
        self.path = path
        self._folder_exists = folder_exists
        self._vaults: dict[str, Vault] = {}

    @property
    def vaults(self) -> list[Vault]:
        return list(self._vaults.values())

    @property
    def visible_vaults(self) -> list[Vault]:
        return [v for v in self._vaults.values() if not v.hidden]

    @property
    def hidden_vaults(self) -> list[Vault]:
        return [v for v in self._vaults.values() if v.hidden]

    def get(self, key: str) -> Vault | None:
        return self._vaults.get(key)

    def load(self) -> None:
        try:
            data = read_json(self.path)
        except JsonFileError as e:
            backup = self.path.with_name(self.path.name + ".broken")
            log.error("cannot read %s (%s), moving it to %s", self.path, e, backup)
            os.replace(self.path, backup)
            data = None
        self._vaults = {}
        if not isinstance(data, dict):
            return
        for entry in data.get("vaults", []):
            try:
                vault = Vault.from_dict(entry)
            except TypeError:
                log.warning("skipping malformed vault entry %r", entry)
                continue
            self._vaults[vault.key] = vault

    def save(self) -> None:
        write_json_atomic(
            self.path,
            {"version": STORE_VERSION, "vaults": [asdict(v) for v in self._vaults.values()]},
        )

    def find_by_path(self, path: str) -> Vault | None:
        norm = normalize_path(path)
        for vault in self._vaults.values():
            if normalize_path(vault.path) == norm:
                return vault
        return None

    def add_manual(self, path: str) -> Vault:
        """Add a folder by hand; returns the existing entry if the path is already known."""
        existing = self.find_by_path(path)
        if existing:
            existing.hidden = False
            return existing
        norm = normalize_path(path)
        vault = Vault(key=manual_key(norm), path=norm, source=SOURCE_MANUAL)
        self._vaults[vault.key] = vault
        return vault

    def hide(self, key: str) -> None:
        """Hide a vault in the launcher; it can be restored in Settings.

        Hiding instead of deleting also keeps a sync from bringing the vault back.
        """
        vault = self._vaults.get(key)
        if vault is not None:
            vault.hidden = True

    def forget(self, key: str) -> None:
        """Delete a vault from the launcher for good."""
        self._vaults.pop(key, None)

    def unhide(self, key: str) -> None:
        self._vaults[key].hidden = False

    def set_label(self, key: str, label: str | None) -> None:
        vault = self._vaults[key]
        vault.label = (label or "").strip() or None

    def mark_opened(self, key: str, timestamp: int | None = None) -> None:
        self._vaults[key].last_opened = timestamp if timestamp is not None else now_ms()

    def sync(self, obsidian_vaults: list[ObsidianVault]) -> SyncResult:
        """Merge vaults from obsidian.json into the store.

        Vaults that disappeared from Obsidian are only reported in `missing`;
        the caller decides via resolve_missing() whether to keep or drop them.
        Vaults that Obsidian does not list and whose folder is gone are dropped
        right away and reported in `removed`.
        """
        result = SyncResult()
        seen_keys: set[str] = set()

        for ov in obsidian_vaults:
            norm = normalize_path(ov.path)
            by_id = next((v for v in self._vaults.values() if v.obsidian_id == ov.id), None)
            by_path = self.find_by_path(norm)

            if by_id and by_path and by_id is not by_path:
                # A manually added vault got registered in Obsidian under an id we already track.
                by_id.label = by_id.label or by_path.label
                by_id.last_opened = max(by_id.last_opened, by_path.last_opened)
                del self._vaults[by_path.key]
            vault = by_id or by_path

            if vault is None:
                vault = Vault(
                    key=ov.id,
                    path=norm,
                    obsidian_id=ov.id,
                    source=SOURCE_OBSIDIAN,
                    in_obsidian=True,
                    obsidian_ts=ov.ts,
                )
                self._vaults[vault.key] = vault
                result.added.append(vault)
            else:
                before = asdict(vault)
                vault.obsidian_id = ov.id
                vault.path = norm
                vault.in_obsidian = True
                vault.obsidian_ts = ov.ts
                if asdict(vault) != before:
                    result.updated.append(vault)
            seen_keys.add(vault.key)

        for vault in self._vaults.values():
            if vault.key in seen_keys:
                continue
            if not self._folder_exists(vault.path):
                # Gone from Obsidian and from disk: nothing left to open or to ask about.
                result.removed.append(vault)
                continue
            if not vault.in_obsidian:
                continue
            if vault.hidden:
                # Nothing to ask about: the user already hid it in the launcher.
                vault.in_obsidian = False
                result.updated.append(vault)
            else:
                result.missing.append(vault)
        for vault in result.removed:
            del self._vaults[vault.key]
        return result

    def resolve_missing(self, keep: Iterable[str], remove: Iterable[str]) -> None:
        for key in keep:
            if key in self._vaults:
                self._vaults[key].in_obsidian = False
        for key in remove:
            self._vaults.pop(key, None)
