from urllib.parse import quote

from vault_launcher.store import Vault


def build_uri(vault: Vault) -> str:
    """Obsidian URI that opens the vault.

    Vaults known to Obsidian are opened by id, which stays unambiguous even when
    two vaults share a folder name. Obsidian resolves a path only to a vault it
    already knows that contains the path, so other folders have to be registered
    first (obsidian_config.register_vault).
    """
    if vault.in_obsidian and vault.obsidian_id:
        return "obsidian://open?vault=" + quote(vault.obsidian_id, safe="")
    return "obsidian://open?path=" + quote(vault.path, safe="")


def open_uri(uri: str) -> bool:
    """Hand the URI to the desktop (xdg-open, or the OpenURI portal inside flatpak)."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    return QDesktopServices.openUrl(QUrl(uri, QUrl.ParsingMode.StrictMode))
