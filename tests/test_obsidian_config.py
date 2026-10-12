import json
import os
import re

import pytest

from vault_launcher.jsonfile import JsonFileError
from vault_launcher.obsidian_config import (
    LOCK_NAME,
    ObsidianVault,
    obsidian_running,
    read_obsidian_vaults,
    register_vault,
    unregister_vault,
)

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


def test_register_vault_keeps_everything_else(tmp_path):
    config = tmp_path / "obsidian.json"
    config.write_text(json.dumps(CONFIG))
    config.chmod(0o644)
    vault_id = register_vault(config, "/data/vault/New One", now_ms=1234)

    assert re.fullmatch(r"[0-9a-f]{16}", vault_id)
    data = json.loads(config.read_text())
    assert data["vaults"][vault_id] == {"path": "/data/vault/New One", "ts": 1234}
    del data["vaults"][vault_id]
    assert data == CONFIG
    assert json.loads((tmp_path / "obsidian.json.bak").read_text()) == CONFIG
    assert config.stat().st_mode & 0o777 == 0o644


def test_register_vault_known_path_returns_id(tmp_path):
    config = tmp_path / "obsidian.json"
    config.write_text(json.dumps(CONFIG))
    before = config.read_text()
    assert register_vault(config, "/data/vault/PKM") == "aaaa000000000001"
    assert config.read_text() == before
    assert not (tmp_path / "obsidian.json.bak").exists()


def test_register_vault_refuses_unexpected_content(tmp_path):
    config = tmp_path / "obsidian.json"
    config.write_text('{"vaults": []}')
    with pytest.raises(JsonFileError):
        register_vault(config, "/data/vault/x")
    assert config.read_text() == '{"vaults": []}'


def test_obsidian_running(tmp_path):
    assert obsidian_running(tmp_path) is False
    os.symlink("ws-4242", tmp_path / LOCK_NAME)
    assert obsidian_running(tmp_path, lambda pid: pid == 4242, hostname="ws") is True
    assert obsidian_running(tmp_path, lambda pid: False, hostname="ws") is False
    assert obsidian_running(tmp_path, lambda pid: False, hostname="other") is True
    # flatpak: processes of the host are not visible
    assert obsidian_running(tmp_path, None) is True


def test_unregister_vault_removes_entry_and_window_state(tmp_path):
    config = tmp_path / "obsidian.json"
    config.write_text(json.dumps(CONFIG))
    (tmp_path / "aaaa000000000001.json").write_text("{}")
    (tmp_path / "aaaa000000000002.json").write_text("{}")

    assert unregister_vault(config, "aaaa000000000001") is True

    data = json.loads(config.read_text())
    assert "aaaa000000000001" not in data["vaults"]
    expected = json.loads(json.dumps(CONFIG))
    del expected["vaults"]["aaaa000000000001"]
    assert data == expected
    assert json.loads((tmp_path / "obsidian.json.bak").read_text()) == CONFIG
    assert not (tmp_path / "aaaa000000000001.json").exists()
    assert (tmp_path / "aaaa000000000002.json").exists()


def test_unregister_unknown_vault_changes_nothing(tmp_path):
    config = tmp_path / "obsidian.json"
    config.write_text(json.dumps(CONFIG))
    before = config.read_text()
    assert unregister_vault(config, "nope") is False
    assert config.read_text() == before
    assert not (tmp_path / "obsidian.json.bak").exists()


def test_unregister_odd_id_does_not_delete_other_files(tmp_path):
    sub = tmp_path / "obsidian"
    sub.mkdir()
    config = sub / "obsidian.json"
    config.write_text(json.dumps({"vaults": {"../victim": {"path": "/x"}}}))
    (tmp_path / "victim.json").write_text("keep")
    assert unregister_vault(config, "../victim") is True
    assert (tmp_path / "victim.json").read_text() == "keep"
