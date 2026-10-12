import logging
import os
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    QByteArray,
    QFileSystemWatcher,
    QItemSelectionModel,
    QPoint,
    Qt,
    QTimer,
    QUrl,
)
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

from vault_launcher import APP_ID, APP_NAME, __version__, paths, theme
from vault_launcher.launcher import build_uri, open_uri
from vault_launcher.jsonfile import JsonFileError, read_json
from vault_launcher.obsidian_config import (
    obsidian_running,
    parse_obsidian_config,
    pid_alive,
    read_obsidian_vaults,
    register_vault,
    unregister_vault,
)
from vault_launcher.settings import Settings, save_settings
from vault_launcher.store import Vault, VaultStore, sort_vaults
from vault_launcher.ui.settings_dialog import SettingsDialog
from vault_launcher.ui.sync_dialog import SyncDialog
from vault_launcher.ui.vault_list import VaultDelegate, VaultListModel, VaultRole

log = logging.getLogger(__name__)

# Icon names under which Obsidian installs its icon (native packages, flatpak).
OBSIDIAN_ICON_NAMES = ("obsidian", "md.obsidian.Obsidian")
LOGO_SIZE = 72
BUNDLED_ICON = Path(__file__).resolve().parent.parent / "resources" / "app-icon.svg"

# Obsidian rewrites obsidian.json in several steps; wait for it to settle.
SYNC_DEBOUNCE_MS = 500

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
        # Missing vaults the user postponed with "Ask later" in this session.
        self._postponed_missing: set[str] = set()
        self._sync_dialog_open = False

        self._watcher = QFileSystemWatcher(self)
        self._sync_timer = QTimer(self, singleShot=True, interval=SYNC_DEBOUNCE_MS)
        self._sync_timer.timeout.connect(self.sync_from_obsidian)
        self._watcher.fileChanged.connect(lambda _: self._sync_timer.start())
        self._watcher.directoryChanged.connect(lambda _: self._sync_timer.start())

        self.setWindowTitle(APP_NAME)
        self.resize(640, 420)
        self.setMinimumSize(520, 320)
        self._build_ui()
        self._restore_geometry()

        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.close)
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            QShortcut(QKeySequence(key), self, self.open_selected)
        QShortcut(QKeySequence(Qt.Key.Key_F2), self, self.edit_label_selected)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self.hide_selected)
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
        logo.setPixmap(app_logo().pixmap(LOGO_SIZE, LOGO_SIZE))
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
        self._update_watcher()
        vaults = read_obsidian_vaults(self.obsidian_config_files())
        if vaults is None:
            log.info("no readable obsidian.json found, skipping sync")
            self.refresh()
            return
        result = self.store.sync(vaults)
        if result.changed:
            log.info("synced: %d added, %d updated, %d removed",
                     len(result.added), len(result.updated), len(result.removed))
            self._save_store()
        self.refresh()
        self._ask_about_missing([v for v in result.missing
                                 if v.key not in self._postponed_missing])

    def _update_watcher(self) -> None:
        """Watch the config files and their folders.

        Obsidian replaces obsidian.json on save, which drops a file watch, and the
        file may not exist yet; the folder watch covers both cases.
        """
        wanted = set()
        for path in self.obsidian_config_files():
            if path.is_file():
                wanted.add(str(path))
            if path.parent.is_dir():
                wanted.add(str(path.parent))
        current = set(self._watcher.files() + self._watcher.directories())
        if current - wanted:
            self._watcher.removePaths(list(current - wanted))
        if wanted - current:
            self._watcher.addPaths(list(wanted - current))

    def _ask_about_missing(self, missing: list[Vault]) -> None:
        if not missing or self._sync_dialog_open or not self.isVisible():
            return
        self._sync_dialog_open = True
        try:
            dialog = SyncDialog(missing, self)
            if dialog.exec() == SyncDialog.DialogCode.Accepted:
                keep, remove = dialog.decision()
                self.store.resolve_missing(keep, remove)
                self._save_store()
                self.refresh()
            else:
                self._postponed_missing.update(v.key for v in missing)
        finally:
            self._sync_dialog_open = False

    # Actions

    def open_selected(self) -> None:
        vault = self.selected_vault()
        if vault:
            self.open_vault(vault)

    def open_vault(self, vault: Vault) -> None:
        if not (vault.in_obsidian and vault.obsidian_id) and not self._register_in_obsidian(vault):
            return
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

    def _register_in_obsidian(self, vault: Vault) -> bool:
        """Add a folder Obsidian does not know yet to its vault list.

        Obsidian cannot open such a folder through a link, and it reads obsidian.json
        only at startup, so this waits until Obsidian is closed.
        """
        config = next((p for p in self.obsidian_config_files() if p.is_file()), None)
        if config is None:
            QMessageBox.warning(
                self, APP_NAME,
                self.tr("Obsidian's list of vaults (obsidian.json) was not found. "
                        "Start Obsidian once, then try again."),
            )
            return False
        text = self.tr(
            "Obsidian does not know “{}” yet. It reads its list of vaults only when it "
            "starts, so the folder can be added to the list only while Obsidian is "
            "closed."
        ).format(vault.display_name)
        if not self._wait_for_obsidian_closed(config, text):
            return False
        try:
            register_vault(config, vault.path)
        except (OSError, JsonFileError) as e:
            log.error("cannot register %s: %s", vault.path, e)
            QMessageBox.warning(
                self, APP_NAME,
                self.tr("Could not add the folder to Obsidian's list of vaults:\n{}").format(e),
            )
            return False
        # Merges the folder with the new Obsidian entry, which gives it an Obsidian id.
        self.sync_from_obsidian()
        return vault.in_obsidian and vault.obsidian_id is not None

    def _wait_for_obsidian_closed(self, config: Path, text: str) -> bool:
        """Ask the user to close Obsidian until it is closed; False if they cancel.

        Obsidian keeps obsidian.json in memory and overwrites it, so it may only be
        edited while Obsidian is not running.
        """
        # Inside the flatpak the host's processes are not visible, only Obsidian's lock.
        alive = None if paths.is_flatpak() else pid_alive
        while obsidian_running(config.parent, alive):
            message = text + "\n\n" + self.tr("Close all Obsidian windows and click Retry.")
            if alive is None:
                message += "\n\n" + self.tr(
                    "If Obsidian is not running, it did not quit properly last time. "
                    "Start it and quit it once.")
            box = QMessageBox(QMessageBox.Icon.Information, APP_NAME, message, parent=self)
            retry = box.addButton(self.tr("Retry"), QMessageBox.ButtonRole.AcceptRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(retry)
            box.exec()
            if box.clickedButton() is not retry:
                return False
        return True

    def _config_with_vault(self, vault_id: str) -> Path | None:
        """The obsidian.json that lists the vault."""
        for path in self.obsidian_config_files():
            try:
                if any(v.id == vault_id for v in parse_obsidian_config(read_json(path))):
                    return path
            except (JsonFileError, ValueError):
                continue
        return None

    def remove_from_obsidian(self, vault: Vault) -> None:
        box = QMessageBox(
            QMessageBox.Icon.Question,
            self.tr("Remove from Obsidian"),
            self.tr("Remove “{}” from Obsidian?\n\nObsidian will no longer list this vault "
                    "and it disappears from the launcher too. The folder and your notes are "
                    "not touched.").format(vault.display_name),
            parent=self,
        )
        remove = box.addButton(self.tr("Remove"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() is not remove:
            return
        config = self._config_with_vault(vault.obsidian_id) if vault.obsidian_id else None
        if config is not None:
            text = self.tr(
                "Obsidian keeps its list of vaults in memory and would undo the change, so "
                "“{}” can be removed from it only while Obsidian is closed."
            ).format(vault.display_name)
            if not self._wait_for_obsidian_closed(config, text):
                return
            try:
                unregister_vault(config, vault.obsidian_id)
            except (OSError, JsonFileError) as e:
                log.error("cannot remove %s from Obsidian: %s", vault.obsidian_id, e)
                QMessageBox.warning(
                    self, APP_NAME,
                    self.tr("Could not remove the vault from Obsidian's list of vaults:\n{}")
                    .format(e),
                )
                return
        self.store.forget(vault.key)
        self._save_store()
        self.sync_from_obsidian()

    def add_folder(self) -> None:
        title = self.tr("Add folder as vault")
        path = QFileDialog.getExistingDirectory(self, title, os.path.expanduser("~"))
        if not path:
            return
        real_path = paths.host_path(path)
        if real_path is None:
            # The portal gave a sandbox-only path and did not say where the folder really
            # is. Qt's own dialog browses the (read-only) host file system directly.
            log.info("cannot resolve %s, asking again without the portal", path)
            path = QFileDialog.getExistingDirectory(
                self, title, os.path.expanduser("~"),
                QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog,
            )
            if not path:
                return
            real_path = path
        path = real_path
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

    def hide_selected(self) -> None:
        # No confirmation: hidden vaults can be restored in Settings.
        vault = self.selected_vault()
        if not vault:
            return
        self.store.hide(vault.key)
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
        menu.addAction(self.tr("Hide vault"), self.hide_selected)
        if vault.in_obsidian and vault.obsidian_id:
            menu.addAction(self.tr("Remove from Obsidian…"),
                           lambda: self.remove_from_obsidian(vault))
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


def app_logo() -> QIcon:
    """Obsidian's icon from the system icon theme, or the launcher's own icon."""
    for name in OBSIDIAN_ICON_NAMES:
        icon = QIcon.fromTheme(name)
        if not icon.isNull():
            return icon
    return QIcon.fromTheme(APP_ID, QIcon(str(BUNDLED_ICON)))
