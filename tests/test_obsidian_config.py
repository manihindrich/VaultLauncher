import json

from vault_launcher.obsidian_config import ObsidianVault, read_obsidian_vaults

CONFIG = {
    "vaults": {
        "aaaa000000000001": {"path": "/data/vault/PKM", "ts": 200, "open": True},
        "aaaa000000000002": {"path": "/data/vault/WEB STT", "ts": 100},
        "broken": {"ts": 5},
        "alsobroken": "nope",
    },
    "frame": "native",
}


def write(path, content):
    path.write_text(content if isinstance(content, str) else json.dumps(content))
    return path


def test_reads_valid_config(tmp_path):
    vaults = read_obsidian_vaults([write(tmp_path / "obsidian.json", CONFIG)])
    assert vaults == [
        ObsidianVault("aaaa000000000001", "/data/vault/PKM", 200, True),
        ObsidianVault("aaaa000000000002", "/data/vault/WEB STT", 100, False),
    ]


def test_missing_file_returns_none(tmp_path):
    assert read_obsidian_vaults([tmp_path / "nope.json"]) is None


def test_broken_file_returns_none(tmp_path):
    assert read_obsidian_vaults([write(tmp_path / "a.json", "{not json")]) is None
    assert read_obsidian_vaults([write(tmp_path / "b.json", {"other": 1})]) is None


def test_empty_vault_list_is_not_none(tmp_path):
    assert read_obsidian_vaults([write(tmp_path / "a.json", {"vaults": {}})]) == []


def test_merges_multiple_files_first_wins(tmp_path):
    first = write(tmp_path / "a.json", {"vaults": {"x": {"path": "/a"}}})
    second = write(tmp_path / "b.json", {"vaults": {"x": {"path": "/b"}, "y": {"path": "/c"}}})
    broken = write(tmp_path / "c.json", "garbage")
    vaults = read_obsidian_vaults([tmp_path / "missing.json", first, broken, second])
    assert [(v.id, v.path) for v in vaults] == [("x", "/a"), ("y", "/c")]
