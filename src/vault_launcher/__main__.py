import sys

from PySide6.QtWidgets import QApplication, QMainWindow

from vault_launcher import APP_ID, APP_NAME, __version__


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_ID)

    window = QMainWindow()
    window.setWindowTitle(APP_NAME)
    window.resize(640, 420)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
