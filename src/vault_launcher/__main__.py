import locale
import logging
import sys

from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from vault_launcher import APP_ID, APP_NAME, __version__, paths
from vault_launcher.settings import THEME_SYSTEM, load_settings
from vault_launcher.store import VaultStore
from vault_launcher.ui.main_window import MainWindow, obsidian_icon


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        locale.setlocale(locale.LC_COLLATE, "")
    except locale.Error:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_ID)
    app.setStyle("Fusion")
    QIcon.setThemeSearchPaths(
        QIcon.themeSearchPaths() + [str(d) for d in paths.icon_search_dirs() if d.is_dir()]
    )
    if not QIcon.themeName():
        QIcon.setThemeName("hicolor")
    QIcon.setFallbackThemeName("hicolor")

    icon = obsidian_icon()
    if icon:
        app.setWindowIcon(icon)

    font = QFont(app.font())
    font.setFamilies(["Inter", app.font().family()])
    app.setFont(font)

    settings_path = paths.settings_file()
    settings = load_settings(settings_path)
    store = VaultStore(paths.vaults_file())
    store.load()

    window = MainWindow(store, settings, settings_path, paths.obsidian_config_candidates)
    window.apply_theme()
    QGuiApplication.styleHints().colorSchemeChanged.connect(
        lambda _: settings.theme == THEME_SYSTEM and window.apply_theme()
    )
    window.show()
    window.sync_from_obsidian()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
