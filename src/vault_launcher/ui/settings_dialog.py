from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from vault_launcher import APP_NAME, AUTHOR, AUTHOR_EMAIL, AUTHOR_URL, __version__
from vault_launcher.settings import THEME_DARK, THEME_LIGHT, THEME_SYSTEM, Settings
from vault_launcher.store import SORT_LABEL, SORT_NAME, SORT_RECENT, VaultStore
from vault_launcher.ui.vault_list import display_path


class SettingsDialog(QDialog):
    """Changes apply immediately, like Obsidian's own settings."""

    settings_changed = Signal()
    vaults_changed = Signal()

    def __init__(self, settings: Settings, store: VaultStore, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.store = store
        self.setWindowTitle(self.tr("Settings"))
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.theme = QComboBox()
        for value, label in (
            (THEME_SYSTEM, self.tr("Follow system")),
            (THEME_LIGHT, self.tr("Light")),
            (THEME_DARK, self.tr("Dark")),
        ):
            self.theme.addItem(label, value)
        self.theme.setCurrentIndex(self.theme.findData(settings.theme))
        self.theme.currentIndexChanged.connect(self._on_change)
        form.addRow(self.tr("Theme"), self.theme)

        self.sort = QComboBox()
        for value, label in (
            (SORT_RECENT, self.tr("Recently opened")),
            (SORT_NAME, self.tr("Folder name")),
            (SORT_LABEL, self.tr("Label")),
        ):
            self.sort.addItem(label, value)
        self.sort.setCurrentIndex(self.sort.findData(settings.sort_mode))
        self.sort.currentIndexChanged.connect(self._on_change)
        form.addRow(self.tr("Sort vaults by"), self.sort)

        self.close_after_open = QCheckBox(self.tr("Close the launcher after opening a vault"))
        self.close_after_open.setChecked(settings.close_after_open)
        self.close_after_open.toggled.connect(self._on_change)
        form.addRow(self.close_after_open)
        layout.addLayout(form)

        layout.addSpacing(8)
        layout.addWidget(QLabel(self.tr("Hidden vaults"), objectName="actionTitle"))
        self.hidden_list = QListWidget(objectName="hiddenList")
        self.hidden_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.hidden_list.setMaximumHeight(120)
        self.hidden_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.hidden_list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        layout.addWidget(self.hidden_list)
        self.hidden_empty = QLabel(self.tr("No hidden vaults."), objectName="muted")
        layout.addWidget(self.hidden_empty)

        restore_row = QHBoxLayout()
        restore_row.addStretch()
        self.restore_button = QPushButton(self.tr("Restore"))
        self.restore_button.clicked.connect(self._restore_selected)
        restore_row.addWidget(self.restore_button)
        layout.addLayout(restore_row)

        layout.addSpacing(8)
        layout.addWidget(QLabel(self.tr("Help"), objectName="actionTitle"))
        shortcuts = QGridLayout()
        shortcuts.setHorizontalSpacing(14)
        shortcuts.setVerticalSpacing(2)
        shortcuts.setColumnStretch(1, 1)
        for row, (key, action) in enumerate(self._shortcuts()):
            shortcuts.addWidget(QLabel(f"<b>{key}</b>", objectName="help"), row, 0,
                                Qt.AlignmentFlag.AlignTop)
            shortcuts.addWidget(QLabel(action, objectName="help", wordWrap=True), row, 1)
        layout.addLayout(shortcuts)
        layout.addSpacing(4)
        badges = QLabel(
            self.tr("<b>not in Obsidian</b> – opening it adds the folder to Obsidian's vault "
                    "list; Obsidian has to be closed for that.<br><b>folder missing</b> – the "
                    "folder does not exist; the vault disappears once Obsidian no longer "
                    "lists it either."),
            objectName="help",
            wordWrap=True,
        )
        badges.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(badges)

        layout.addSpacing(8)
        layout.addWidget(QLabel(self.tr("About"), objectName="actionTitle"))
        github = AUTHOR_URL.removeprefix("https://")
        about = QLabel(
            f"{APP_NAME} {__version__} · "
            + self.tr("made by {}").format(AUTHOR)
            + f"<br><a href='mailto:{AUTHOR_EMAIL}'>{AUTHOR_EMAIL}</a>"
            + f" · <a href='{AUTHOR_URL}'>{github}</a>",
            objectName="help",
            wordWrap=True,
        )
        about.setTextFormat(Qt.TextFormat.RichText)
        about.setOpenExternalLinks(True)
        layout.addWidget(about)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.hidden_list.itemSelectionChanged.connect(self._update_restore_button)
        self._fill_hidden()

    def _shortcuts(self) -> list[tuple[str, str]]:
        return [
            (self.tr("Double-click"), self.tr("Open the vault")),
            (self.tr("Right-click"), self.tr("Menu: label, show folder, hide, remove")),
            ("↑ / ↓", self.tr("Select a vault")),
            (self.tr("Type letters"), self.tr("Jump to a vault by its name or label")),
            ("Enter", self.tr("Open the selected vault")),
            ("F2", self.tr("Edit label")),
            ("Delete", self.tr("Hide vault (restore it here)")),
            ("Ctrl+O", self.tr("Add folder as vault")),
            ("Ctrl+,", self.tr("Settings and help")),
            ("Esc", self.tr("Close the window")),
        ]

    def _fill_hidden(self) -> None:
        self.hidden_list.clear()
        for vault in sorted(self.store.hidden_vaults, key=lambda v: v.display_name.casefold()):
            item = QListWidgetItem(f"{vault.display_name}  —  {display_path(vault.path)}")
            item.setToolTip(vault.path)
            item.setData(Qt.ItemDataRole.UserRole, vault.key)
            self.hidden_list.addItem(item)
        has_hidden = self.hidden_list.count() > 0
        self.hidden_list.setVisible(has_hidden)
        self.hidden_empty.setVisible(not has_hidden)
        self.restore_button.setVisible(has_hidden)
        self._update_restore_button()

    def _update_restore_button(self) -> None:
        self.restore_button.setEnabled(bool(self.hidden_list.selectedItems()))

    def _restore_selected(self) -> None:
        for item in self.hidden_list.selectedItems():
            self.store.unhide(item.data(Qt.ItemDataRole.UserRole))
        self._fill_hidden()
        self.vaults_changed.emit()

    def _on_change(self) -> None:
        self.settings.theme = self.theme.currentData()
        self.settings.sort_mode = self.sort.currentData()
        self.settings.close_after_open = self.close_after_open.isChecked()
        self.settings_changed.emit()
