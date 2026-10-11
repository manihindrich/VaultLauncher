from vault_launcher.launcher import build_uri
from vault_launcher.store import Vault


def test_known_vault_opens_by_id():
    vault = Vault("id1", "/v/PKM", obsidian_id="372f8dd71eb890bd", in_obsidian=True)
    assert build_uri(vault) == "obsidian://open?vault=372f8dd71eb890bd"


def test_manual_vault_opens_by_encoded_path():
    vault = Vault("manual:x", "/data/vault/Můj vault & co?#1")
    assert build_uri(vault) == (
        "obsidian://open?path=%2Fdata%2Fvault%2FM%C5%AFj%20vault%20%26%20co%3F%231"
    )


def test_vault_removed_from_obsidian_opens_by_path():
    vault = Vault("id1", "/v/PKM", obsidian_id="372f8dd71eb890bd", in_obsidian=False)
    assert build_uri(vault) == "obsidian://open?path=%2Fv%2FPKM"
