# Vault Launcher

Small launcher window for [Obsidian](https://obsidian.md) vaults: pick a vault, it opens in
Obsidian, the launcher closes (or stays, if you prefer). Not affiliated with Obsidian.

![Vault Launcher main window](data/screenshots/main.png)

- Reads the vault list from Obsidian's `obsidian.json` (native, flatpak and snap installs) and
  keeps it in sync while the window is open. Vaults removed from Obsidian are not dropped
  silently, you decide whether to keep them.
- Add folders by hand, give vaults your own labels, hide vaults you do not need.
- Sort by last use, folder name or label.
- Light / dark / system theme modelled on Obsidian's default theme.
- Vaults are opened through `obsidian://open?vault=<id>`. Obsidian cannot open a folder it
  does not know through a link, so a folder added by hand is added to Obsidian's
  `obsidian.json` the first time you open it, the same way Obsidian's "Open folder as vault"
  does. Obsidian reads that file only at startup, so the launcher asks you to close Obsidian
  first and keeps the previous version as `obsidian.json.bak`. Nothing else in Obsidian's
  files or in your vaults is changed.

## Usage

| Action | |
|---|---|
| Double-click, Enter | open the vault |
| Right-click | menu: open, edit label, show folder, hide |
| ↑ / ↓, typing letters | select a vault |
| F2 | edit label |
| Delete | hide the vault (restore it in settings) |
| Ctrl+O | add folder as vault |
| Ctrl+, | settings and help |
| Esc | close |

![Settings with help](data/screenshots/settings.png)

Data is stored in `~/.local/share/vault-launcher/vaults.json`, settings in
`~/.config/vault-launcher/settings.json` (inside `~/.var/app/io.github.manihindrich.VaultLauncher/`
when running as a flatpak).

## Install

### Nix / NixOS

```sh
nix run github:manihindrich/VaultLauncher
```

In a NixOS or home-manager configuration, add the flake as an input and use
`inputs.vault-launcher.packages.${pkgs.system}.default` (or the `overlays.default` overlay,
which provides `pkgs.vault-launcher`). The package is defined in `nix/package.nix`.

### Flatpak

The manifest is in `flatpak/`. It needs `flatpak` and `flatpak-builder` with the Flathub
remote (on NixOS: `services.flatpak.enable = true;`). `flatpak-builder` also calls
`appstreamcli` on the host; on NixOS run the commands below inside
`nix shell nixpkgs#appstream` if it is not installed.

```sh
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak-builder --user --install --install-deps-from=flathub --force-clean \
    build-dir flatpak/io.github.manihindrich.VaultLauncher.yml
flatpak run io.github.manihindrich.VaultLauncher
```

To produce a single-file bundle for distribution:

```sh
flatpak-builder --repo=repo --force-clean build-dir flatpak/io.github.manihindrich.VaultLauncher.yml
flatpak build-bundle repo vault-launcher.flatpak io.github.manihindrich.VaultLauncher \
    --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo
```

The flatpak has read-only access to the whole file system (`--filesystem=host:ro`) so that
vaults outside your home folder work too, and write access only to Obsidian's configuration
folder.

## Development

```sh
nix develop
python -m vault_launcher
pytest
ruff check .
desktop-file-validate data/*.desktop
appstreamcli validate --no-net data/*.metainfo.xml
```

## License

MIT, see [LICENSE](LICENSE). Author: Mani Hindrich, <mani@hindrich.cz>,
[github.com/manihindrich](https://github.com/manihindrich).
