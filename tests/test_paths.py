from pathlib import Path

from vault_launcher import paths

HOME = Path("/home/user")


def test_native_defaults():
    candidates = paths.obsidian_config_candidates({}, HOME)
    assert candidates[0] == HOME / ".config/obsidian/obsidian.json"
    assert HOME / ".var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json" in candidates
    assert paths.settings_file({}, HOME) == HOME / ".config/vault-launcher/settings.json"
    assert paths.vaults_file({}, HOME) == HOME / ".local/share/vault-launcher/vaults.json"


def test_respects_xdg_vars():
    env = {"XDG_CONFIG_HOME": "/cfg", "XDG_DATA_HOME": "/data"}
    assert paths.obsidian_config_candidates(env, HOME)[0] == Path("/cfg/obsidian/obsidian.json")
    assert paths.vaults_file(env, HOME) == Path("/data/vault-launcher/vaults.json")


def test_relative_xdg_var_is_ignored():
    env = {"XDG_CONFIG_HOME": "relative"}
    assert paths.app_config_dir(env, HOME) == HOME / ".config/vault-launcher"


def test_flatpak_reads_host_config():
    env = {
        "FLATPAK_ID": "io.github.manihindrich.VaultLauncher",
        "XDG_CONFIG_HOME": "/home/user/.var/app/io.github.manihindrich.VaultLauncher/config",
    }
    assert paths.obsidian_config_candidates(env, HOME)[0] == HOME / ".config/obsidian/obsidian.json"
    env["HOST_XDG_CONFIG_HOME"] = "/host/cfg"
    assert paths.obsidian_config_candidates(env, HOME)[0] == Path("/host/cfg/obsidian/obsidian.json")
    # The app's own files stay inside the sandbox.
    assert paths.settings_file(env, HOME).is_relative_to(HOME / ".var/app")


def test_icon_search_dirs():
    env = {"XDG_DATA_DIRS": "/a/share:relative:/usr/share", "USER": "me"}
    dirs = paths.icon_search_dirs(env, HOME)
    assert dirs[:3] == [HOME / ".icons", HOME / ".local/share/icons", Path("/a/share/icons")]
    assert Path("/etc/profiles/per-user/me/share/icons") in dirs
    assert Path("/run/current-system/sw/share/icons") in dirs
    assert len(dirs) == len(set(dirs))
