import logging
import os
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QByteArray, QItemSelectionModel, QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListView,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from vault_launcher import APP_NAME, __version__, theme
from vault_launcher.launcher import build_uri, open_uri
from vault_launcher.obsidian_config import read_obsidian_vaults
from vault_launcher.settings import Settings, save_settings
from vault_launcher.store import Vault, VaultStore, sort_vaults
from vault_launcher.ui.settings_dialog import SettingsDialog
from vault_launcher.ui.vault_list import VaultDelegate, VaultListModel, VaultRole

log = logging.getLogger(__name__)

# Icon names under which Obsidian installs its icon (native packages, flatpak).
OBSIDIAN_ICON_NAMES = ("obsidian", "md.obsidian.Obsidian")
LOGO_SIZE = 72

# Give the desktop a moment to receive the URI (D-Bus / portal) before quitting.
QUIT_DELAY_MS = 300


class MainWindow(QWidget):
    def __init__(
        self,
        store: VaultStore,
        settings: Settings,
        settings_path: Path,
        obsidian_config_files: Callable[[], list[Path]],
    ):
        super().__init__()
        self.store = store
        self.settings = settings
        self.settings_path = settings_path
        self.obsidian_config_files = obsidian_config_files
        self.colors = theme.resolve(settings.theme)

        self.setWindowTitle(APP_NAME)
        self.resize(640, 420)
        self.setMinimumSize(520, 320)
        self._build_ui()
        self._restore_geometry()

        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.close)
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            QShortcut(QKeySequence(key), self, self.open_selected)
        QShortcut(QKeySequence(Qt.Key.Key_F2), self, self.edit_label_selected)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self.remove_selected)
        QShortcut(QKeySequence.StandardKey.Open, self, self.add_folder)
        QShortcut(QKeySequence("Ctrl+,"), self, self.show_settings)

    # UI construction

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = QFrame(objectName="sidePanel")
        side.setFixedWidth(280)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(6, 8, 6, 8)

        self.model = VaultListModel(self)
        self.list = QListView()
        self.list.setModel(self.model)
        self.list.setItemDelegate(VaultDelegate(lambda: self.colors, self.list))
        self.list.setMouseTracking(True)
        self.list.setUniformItemSizes(True)
        self.list.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.list.doubleClicked.connect(lambda index: self.open_vault(index.data(VaultRole)))
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._show_context_menu)
        side_layout.addWidget(self.list)

        self.empty_hint = QLabel(
            self.tr("No vaults yet.\nOpen a vault in Obsidian\nor add a folder."),
            objectName="emptyHint",
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        side_layout.addWidget(self.empty_hint)
        root.addWidget(side)

        main = QWidget(objectName="mainPanel")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(28, 24, 28, 12)
        main_layout.addStretch(2)

        logo = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        icon = obsidian_icon()
        if icon:
            logo.setPixmap(icon.pixmap(LOGO_SIZE, LOGO_SIZE))
            main_layout.addWidget(logo)
            main_layout.addSpacing(8)

        name = QLabel(APP_NAME, objectName="appName", alignment=Qt.AlignmentFlag.AlignCenter)
        version = QLabel(
            self.tr("Version {}").format(__version__),
            objectName="muted",
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        main_layout.addWidget(name)
        main_layout.addWidget(version)
        main_layout.addStretch(1)

        self.open_button = QPushButton(self.tr("Open"), objectName="primary")
        self.open_button.clicked.connect(self.open_selected)
        main_layout.addLayout(
            self._action_row(
                self.tr("Open vault"),
                self.tr("Open the selected vault in Obsidian."),
                self.open_button,
            )
        )
        main_layout.addSpacing(14)
        separator = QFrame(objectName="separator")
        separator.setFixedHeight(1)
        main_layout.addWidget(separator)
        main_layout.addSpacing(14)
        add_button = QPushButton(self.tr("Add"))
        add_button.clicked.connect(self.add_folder)
        main_layout.addLayout(
            self._action_row(
                self.tr("Add folder as vault"),
                self.tr("Add a vault that Obsidian does not know about yet."),
                add_button,
            )
        )
        main_layout.addStretch(3)

        bottom = QHBoxLayout()
        bottom.addStretch()
        settings_button = QToolButton(objectName="iconButton", text="⚙")
        settings_button.setToolTip(self.tr("Settings and help (Ctrl+,)"))
        settings_button.clicked.connect(self.show_settings)
        bottom.addWidget(settings_button)
        main_layout.addLayout(bottom)
        root.addWidget(main, 1)

    def _action_row(self, title: str, description: str, button: QPushButton) -> QHBoxLayout:
        row = QHBoxLayout()
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(QLabel(title, objectName="actionTitle"))
        desc = QLabel(description, objectName="muted", wordWrap=True)
        text.addWidget(desc)
        row.addLayout(text, 1)
        row.addSpacing(12)
        row.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    def _restore_geometry(self) -> None:
        if self.settings.window_geometry:
            self.restoreGeometry(QByteArray.fromBase64(self.settings.window_geometry.encode()))

    # Data

    def selected_vault(self) -> Vault | None:
        index = self.list.currentIndex()
        return index.data(VaultRole) if index.isValid() else None

    def refresh(self) -> None:
        current = self.selected_vault()
        self.model.set_vaults(sort_vaults(self.store.visible_vaults, self.settings.sort_mode))
        row = self.model.row_of(current.key) if current else -1
        if row < 0 and self.model.rowCount() > 0:
            row = 0
        if row >= 0:
            self.list.selectionModel().setCurrentIndex(
                self.model.index(row), QItemSelectionModel.SelectionFlag.ClearAndSelect
            )
        has_vaults = self.model.rowCount() > 0
        self.list.setVisible(has_vaults)
        self.empty_hint.setVisible(not has_vaults)
        self.open_button.setEnabled(has_vaults)
        self.list.setFocus()

    def sync_from_obsidian(self) -> None:
        vaults = read_obsidian_vaults(self.obsidian_config_files())
        if vaults is None:
            log.info("no readable obsidian.json found, skipping sync")
        else:
            result = self.store.sync(vaults)
            if result.changed:
                self._save_store()
        self.refresh()

    # Actions

    def open_selected(self) -> None:
        vault = self.selected_vault()
        if vault:
            self.open_vault(vault)

    def open_vault(self, vault: Vault) -> None:
        uri = build_uri(vault)
        log.info("opening %s", uri)
        if not open_uri(uri):
            QMessageBox.warning(
                self,
                APP_NAME,
                self.tr("Could not open the vault. Is Obsidian installed and registered "
                        "as the handler for obsidian:// links?"),
            )
            return
        self.store.mark_opened(vault.key)
        self._save_store()
        if self.settings.close_after_open:
            self._remember_geometry()
            self.hide()
            QTimer.singleShot(QUIT_DELAY_MS, self.close)
        else:
            self.refresh()

    def add_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self.tr("Add folder as vault"),
                                                os.path.expanduser("~"))
        if not path:
            return
        if not os.path.isdir(os.path.join(path, ".obsidian")):
            answer = QMessageBox.question(
                self,
                self.tr("Add folder as vault"),
                self.tr("“{}” does not look like an Obsidian vault (it has no .obsidian "
                        "folder). Obsidian will turn it into a new vault when you open it.\n\n"
                        "Add it anyway?").format(os.path.basename(path)),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        vault = self.store.add_manual(path)
        self._save_store()
        self.refresh()
        self._select(vault.key)

    def edit_label_selected(self) -> None:
        vault = self.selected_vault()
        if not vault:
            return
        label, ok = QInputDialog.getText(
            self,
            self.tr("Edit label"),
            self.tr("Label shown instead of the folder name “{}”:").format(vault.name),
            text=vault.label or "",
        )
        if ok:
            self.store.set_label(vault.key, label)
            self._save_store()
            self.refresh()

    def clear_label(self, vault: Vault) -> None:
        self.store.set_label(vault.key, None)
        self._save_store()
        self.refresh()

    def show_in_file_manager(self, vault: Vault) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(vault.path))

    def remove_selected(self) -> None:
        vault = self.selected_vault()
        if not vault:
            return
        if vault.in_obsidian:
            detail = self.tr("Obsidian still knows this vault, so it will only be hidden. "
                             "You can restore it in Settings.")
        else:
            detail = self.tr("The folder itself is not touched.")
        answer = QMessageBox.question(
            self,
            self.tr("Remove vault"),
            self.tr("Remove “{}” from the launcher?").format(vault.display_name) + "\n\n" + detail,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.store.remove(vault.key)
            self._save_store()
            self.refresh()

    def _show_context_menu(self, pos: QPoint) -> None:
        index = self.list.indexAt(pos)
        if not index.isValid():
            return
        self.list.setCurrentIndex(index)
        vault: Vault = index.data(VaultRole)
        menu = QMenu(self)
        menu.addAction(self.tr("Open"), lambda: self.open_vault(vault))
        menu.addSeparator()
        menu.addAction(self.tr("Edit label…"), self.edit_label_selected)
        if vault.label:
            menu.addAction(self.tr("Clear label"), lambda: self.clear_label(vault))
        show = menu.addAction(self.tr("Show in file manager"),
                              lambda: self.show_in_file_manager(vault))
        show.setEnabled(os.path.isdir(vault.path))
        menu.addSeparator()
        menu.addAction(self.tr("Remove from launcher…"), self.remove_selected)
        menu.exec(self.list.viewport().mapToGlobal(pos))

    def show_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.store, self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.vaults_changed.connect(lambda: (self._save_store(), self.refresh()))
        dialog.exec()

    def _on_settings_changed(self) -> None:
        self.apply_theme()
        self.refresh()
        self._save_settings()

    def _select(self, key: str) -> None:
        row = self.model.row_of(key)
        if row >= 0:
            self.list.setCurrentIndex(self.model.index(row))

    def _save_store(self) -> None:
        try:
            self.store.save()
        except OSError as e:
            log.exception("cannot save vaults")
            QMessageBox.critical(self, APP_NAME, self.tr("Cannot save vaults: {}").format(e))

    def _save_settings(self) -> None:
        try:
            save_settings(self.settings_path, self.settings)
        except OSError:
            log.exception("cannot save settings")

    def apply_theme(self) -> None:
        self.colors = theme.apply(QApplication.instance(), self.settings.theme)
        self.list.viewport().update()

    def _remember_geometry(self) -> None:
        self.settings.window_geometry = bytes(self.saveGeometry().toBase64()).decode()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.isVisible():
            self._remember_geometry()
        self._save_settings()
        super().closeEvent(event)


def obsidian_icon() -> QIcon | None:
    for name in OBSIDIAN_ICON_NAMES:
        icon = QIcon.fromTheme(name)
        if not icon.isNull():
            return icon
    return None
