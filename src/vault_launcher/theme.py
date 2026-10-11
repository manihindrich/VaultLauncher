from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from vault_launcher.settings import THEME_DARK, THEME_LIGHT


@dataclass(frozen=True)
class ThemeColors:
    """Subset of Obsidian's default theme variables."""

    name: str
    bg_primary: str
    bg_secondary: str
    border: str
    text_normal: str
    text_muted: str
    text_faint: str
    text_on_accent: str
    accent: str
    accent_hover: str
    interactive_normal: str
    interactive_hover: str
    modifier_hover: str
    modifier_active: str
    text_warning: str
    text_error: str


DARK = ThemeColors(
    name=THEME_DARK,
    bg_primary="#1e1e1e",
    bg_secondary="#262626",
    border="#363636",
    text_normal="#dadada",
    text_muted="#b3b3b3",
    text_faint="#666666",
    text_on_accent="#ffffff",
    accent="#8a5cf5",
    accent_hover="#a68af9",
    interactive_normal="#363636",
    interactive_hover="#3f3f3f",
    modifier_hover="rgba(255, 255, 255, 0.075)",
    modifier_active="rgba(138, 92, 245, 0.25)",
    text_warning="#e9973f",
    text_error="#fb464c",
)

LIGHT = ThemeColors(
    name=THEME_LIGHT,
    bg_primary="#ffffff",
    bg_secondary="#f6f6f6",
    border="#e0e0e0",
    text_normal="#222222",
    text_muted="#5c5c5c",
    text_faint="#ababab",
    text_on_accent="#ffffff",
    accent="#8a5cf5",
    accent_hover="#7a4ef3",
    interactive_normal="#ffffff",
    interactive_hover="#f2f3f5",
    modifier_hover="rgba(0, 0, 0, 0.075)",
    modifier_active="rgba(138, 92, 245, 0.15)",
    text_warning="#ec7500",
    text_error="#e93147",
)


def qcolor(value: str) -> QColor:
    """QColor from a hex or CSS rgba() string."""
    if value.startswith("rgba("):
        r, g, b, a = (part.strip() for part in value[5:-1].split(","))
        return QColor(int(r), int(g), int(b), round(float(a) * 255))
    return QColor(value)


def system_is_dark() -> bool:
    # Unknown scheme (no platform theme reporting it) falls back to light.
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def resolve(setting: str) -> ThemeColors:
    if setting == THEME_LIGHT:
        return LIGHT
    if setting == THEME_DARK:
        return DARK
    return DARK if system_is_dark() else LIGHT


def _qpalette(c: ThemeColors) -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, qcolor(c.bg_primary))
    p.setColor(QPalette.ColorRole.WindowText, qcolor(c.text_normal))
    p.setColor(QPalette.ColorRole.Base, qcolor(c.bg_primary))
    p.setColor(QPalette.ColorRole.AlternateBase, qcolor(c.bg_secondary))
    p.setColor(QPalette.ColorRole.Text, qcolor(c.text_normal))
    p.setColor(QPalette.ColorRole.PlaceholderText, qcolor(c.text_faint))
    p.setColor(QPalette.ColorRole.Button, qcolor(c.interactive_normal))
    p.setColor(QPalette.ColorRole.ButtonText, qcolor(c.text_normal))
    p.setColor(QPalette.ColorRole.Highlight, qcolor(c.accent))
    p.setColor(QPalette.ColorRole.HighlightedText, qcolor(c.text_on_accent))
    p.setColor(QPalette.ColorRole.ToolTipBase, qcolor(c.bg_secondary))
    p.setColor(QPalette.ColorRole.ToolTipText, qcolor(c.text_normal))
    p.setColor(QPalette.ColorRole.Link, qcolor(c.accent))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, qcolor(c.text_faint))
    return p


def stylesheet(c: ThemeColors) -> str:
    return f"""
    QWidget {{
        background: {c.bg_primary};
        color: {c.text_normal};
        font-size: 13px;
    }}
    #sidePanel {{
        background: {c.bg_secondary};
        border-right: 1px solid {c.border};
    }}
    #sidePanel QLabel, #sidePanel QListView {{
        background: transparent;
    }}
    QListView {{
        border: none;
        outline: 0;
    }}
    QLabel#appName {{
        font-size: 20px;
        font-weight: 600;
    }}
    QLabel#muted, QLabel#emptyHint, QLabel#help {{
        color: {c.text_muted};
        font-size: 12px;
    }}
    QLabel#actionTitle {{
        font-weight: 600;
    }}
    QFrame#separator {{
        background: {c.border};
        max-height: 1px;
        border: none;
    }}
    QPushButton {{
        background: {c.interactive_normal};
        color: {c.text_normal};
        border: 1px solid {c.border};
        border-radius: 6px;
        padding: 6px 14px;
    }}
    QPushButton:hover {{
        background: {c.interactive_hover};
    }}
    QPushButton:disabled {{
        color: {c.text_faint};
    }}
    QPushButton#primary {{
        background: {c.accent};
        color: {c.text_on_accent};
        border: none;
    }}
    QPushButton#primary:hover {{
        background: {c.accent_hover};
    }}
    QPushButton#primary:disabled {{
        background: {c.interactive_normal};
        color: {c.text_faint};
    }}
    QToolButton#iconButton {{
        background: transparent;
        color: {c.text_muted};
        border: none;
        border-radius: 6px;
        padding: 4px 6px;
        font-size: 16px;
    }}
    QToolButton#iconButton:hover {{
        background: {c.modifier_hover};
        color: {c.text_normal};
    }}
    QComboBox, QLineEdit {{
        background: {c.interactive_normal};
        color: {c.text_normal};
        border: 1px solid {c.border};
        border-radius: 6px;
        padding: 5px 8px;
        selection-background-color: {c.accent};
        selection-color: {c.text_on_accent};
    }}
    QComboBox:hover, QLineEdit:hover {{
        background: {c.interactive_hover};
    }}
    QLineEdit:focus {{
        border: 1px solid {c.accent};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background: {c.bg_secondary};
        border: 1px solid {c.border};
        selection-background-color: {c.modifier_active};
        selection-color: {c.text_normal};
        outline: 0;
    }}
    QCheckBox {{
        spacing: 8px;
        background: transparent;
    }}
    QCheckBox::indicator, QListWidget::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {c.text_faint};
        border-radius: 4px;
        background: {c.interactive_normal};
    }}
    QCheckBox::indicator:checked, QListWidget::indicator:checked {{
        border: 1px solid {c.accent};
        background: {c.accent};
    }}
    QListWidget#hiddenList {{
        background: {c.bg_secondary};
        border: 1px solid {c.border};
        border-radius: 6px;
        padding: 2px;
    }}
    QListWidget#hiddenList::item {{
        padding: 4px 6px;
        border-radius: 4px;
    }}
    QListWidget#hiddenList::item:selected {{
        background: {c.modifier_active};
        color: {c.text_normal};
    }}
    QMenu {{
        background: {c.bg_secondary};
        border: 1px solid {c.border};
        border-radius: 6px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 5px 20px 5px 10px;
        border-radius: 4px;
        background: transparent;
    }}
    QMenu::item:selected {{
        background: {c.modifier_hover};
    }}
    QMenu::item:disabled {{
        color: {c.text_faint};
    }}
    QMenu::separator {{
        height: 1px;
        background: {c.border};
        margin: 4px 6px;
    }}
    QToolTip {{
        background: {c.bg_secondary};
        color: {c.text_normal};
        border: 1px solid {c.border};
        padding: 4px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {c.modifier_hover};
        border-radius: 3px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c.text_faint};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        height: 0;
        background: transparent;
    }}
    """


def apply(app: QApplication, setting: str) -> ThemeColors:
    colors = resolve(setting)
    app.setPalette(_qpalette(colors))
    app.setStyleSheet(stylesheet(colors))
    return colors
