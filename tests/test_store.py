import json

from vault_launcher.obsidian_config import ObsidianVault
from vault_launcher.store import (
    SORT_LABEL,
    SORT_NAME,
    SORT_RECENT,
    SOURCE_OBSIDIAN,
    Vault,
    VaultStore,
    sort_vaults,
)


def make_store(tmp_path):
    store = VaultStore(tmp_path / "vaults.json")
    store.load()
    return store


def test_sync_adds_new_vaults(tmp_path):
    store = make_store(tmp_path)
    result = store.sync([ObsidianVault("id1", "/v/PKM", 10), ObsidianVault("id2", "/v/LIB/", 20)])
    assert [v.key for v in result.added] == ["id1", "id2"]
    assert result.changed and not result.missing
    lib = store.get("id2")
    assert lib.path == "/v/LIB"
    assert lib.source == SOURCE_OBSIDIAN and lib.in_obsidian and lib.obsidian_ts == 20


def test_sync_updates_existing(tmp_path):
    store = make_store(tmp_path)
    store.sync([ObsidianVault("id1", "/v/PKM", 10)])
    store.set_label("id1", "Moje PKM")

    result = store.sync([ObsidianVault("id1", "/v/PKM-moved", 30)])
    assert result.updated and not result.added
    vault = store.get("id1")
    assert vault.path == "/v/PKM-moved" and vault.obsidian_ts == 30
    assert vault.label == "Moje PKM"

    assert not store.sync([ObsidianVault("id1", "/v/PKM-moved", 30)]).changed


def test_sync_reports_missing_without_removing(tmp_path):
    store = make_store(tmp_path)
    store.sync([ObsidianVault("id1", "/v/a"), ObsidianVault("id2", "/v/b")])
    manual = store.add_manual("/v/manual")

    result = store.sync([ObsidianVault("id1", "/v/a")])
    assert [v.key for v in result.missing] == ["id2"]
    assert store.get("id2") is not None
    assert manual not in result.missing


def test_resolve_missing(tmp_path):
    store = make_store(tmp_path)
    store.sync([ObsidianVault("id1", "/v/a"), ObsidianVault("id2", "/v/b")])
    store.resolve_missing(keep=["id1"], remove=["id2"])
    assert store.get("id2") is None
    assert store.get("id1").in_obsidian is False
    # Kept vault is no longer reported as missing.
    assert store.sync([]).missing == []


def test_manual_vault_merges_when_obsidian_registers_it(tmp_path):
    store = make_store(tmp_path)
    manual = store.add_manual("/v/new/")
    store.set_label(manual.key, "Nový")
    store.mark_opened(manual.key, 500)

    result = store.sync([ObsidianVault("id9", "/v/new", 400)])
    assert not result.added and result.updated == [manual]
    assert len(store.vaults) == 1
    assert manual.obsidian_id == "id9" and manual.in_obsidian
    assert manual.label == "Nový" and manual.last_used == 500


def test_duplicate_entries_are_merged(tmp_path):
    store = make_store(tmp_path)
    store.sync([ObsidianVault("id1", "/v/a")])
    manual = store.add_manual("/v/b")
    store.set_label(manual.key, "B")

    store.sync([ObsidianVault("id1", "/v/b")])
    assert [v.key for v in store.vaults] == ["id1"]
    assert store.get("id1").label == "B"


def test_add_manual_is_idempotent(tmp_path):
    store = make_store(tmp_path)
    first = store.add_manual("/v/x")
    assert store.add_manual("/v/x/") is first
    assert first.key.startswith("manual:") and not first.in_obsidian


def test_set_label_blank_clears(tmp_path):
    store = make_store(tmp_path)
    vault = store.add_manual("/v/x")
    store.set_label(vault.key, "  ")
    assert vault.label is None and vault.display_name == "x"


def test_persistence_roundtrip(tmp_path):
    store = make_store(tmp_path)
    store.sync([ObsidianVault("id1", "/v/a", 5)])
    store.add_manual("/v/ž vault")
    store.set_label("id1", "Á")
    store.save()

    again = make_store(tmp_path)
    assert [v.__dict__ for v in again.vaults] == [v.__dict__ for v in store.vaults]
    data = json.loads((tmp_path / "vaults.json").read_text())
    assert data["version"] == 1


def test_broken_store_is_moved_aside(tmp_path):
    (tmp_path / "vaults.json").write_text("{broken")
    store = make_store(tmp_path)
    assert store.vaults == []
    assert (tmp_path / "vaults.json.broken").read_text() == "{broken"


def test_unknown_fields_are_ignored(tmp_path):
    (tmp_path / "vaults.json").write_text(
        json.dumps({"version": 1, "vaults": [{"key": "k", "path": "/p", "future": 1}, {"x": 1}]})
    )
    store = make_store(tmp_path)
    assert [v.key for v in store.vaults] == ["k"]


def test_sorting():
    a = Vault("a", "/v/beta", label="Zeta", obsidian_ts=100)
    b = Vault("b", "/v/Alpha", last_opened=300)
    c = Vault("c", "/v/gamma", label="aardvark", obsidian_ts=200)
    assert [v.key for v in sort_vaults([a, b, c], SORT_RECENT)] == ["b", "c", "a"]
    assert [v.key for v in sort_vaults([a, b, c], SORT_NAME)] == ["b", "a", "c"]
    assert [v.key for v in sort_vaults([a, b, c], SORT_LABEL)] == ["c", "b", "a"]
