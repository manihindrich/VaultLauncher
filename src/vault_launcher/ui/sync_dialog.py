from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from vault_launcher.store import Vault
from vault_launcher.ui.vault_list import display_path


class SyncDialog(QDialog):
    """Asks what to do with vaults that disappeared from Obsidian's vault list."""

    def __init__(self, missing: list[Vault], parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Vaults removed from Obsidian"))
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        intro = QLabel(
            self.tr("These vaults are no longer in Obsidian's vault list. Checked vaults stay "
                    "in the launcher and will be opened by their folder path; unchecked "
                    "vaults are removed from the launcher. Folders are never touched."),
            wordWrap=True,
        )
        layout.addWidget(intro)

        self.list = QListWidget(objectName="hiddenList")
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.list.setMaximumHeight(180)
        for vault in missing:
            item = QListWidgetItem(f"{vault.display_name}  —  {display_path(vault.path)}")
            item.setToolTip(vault.path)
            item.setData(Qt.ItemDataRole.UserRole, vault.key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list.addItem(item)
        layout.addWidget(self.list)

        buttons = QDialogButtonBox()
        apply = buttons.addButton(self.tr("Apply"), QDialogButtonBox.ButtonRole.AcceptRole)
        apply.setObjectName("primary")
        buttons.addButton(self.tr("Ask later"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def decision(self) -> tuple[list[str], list[str]]:
        """Return (keys to keep, keys to remove)."""
        keep, remove = [], []
        for i in range(self.list.count()):
            item = self.list.item(i)
            key = item.data(Qt.ItemDataRole.UserRole)
            (keep if item.checkState() == Qt.CheckState.Checked else remove).append(key)
        return keep, remove
