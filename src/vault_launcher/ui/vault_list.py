import os
from collections.abc import Callable

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRectF, QSize, Qt
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPainterPath
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from vault_launcher.store import Vault
from vault_launcher.theme import ThemeColors, qcolor

VaultRole = Qt.ItemDataRole.UserRole + 1
FolderExistsRole = Qt.ItemDataRole.UserRole + 2

HOME = os.path.expanduser("~")


def display_path(path: str) -> str:
    if path == HOME or path.startswith(HOME + os.sep):
        return "~" + path[len(HOME):]
    return path


class VaultListModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._vaults: list[Vault] = []
        self._exists: dict[str, bool] = {}

    def set_vaults(self, vaults: list[Vault]) -> None:
        self.beginResetModel()
        self._vaults = list(vaults)
        self._exists = {v.key: os.path.isdir(v.path) for v in self._vaults}
        self.endResetModel()

    def row_of(self, key: str) -> int:
        return next((i for i, v in enumerate(self._vaults) if v.key == key), -1)

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._vaults)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        vault = self._vaults[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return vault.display_name
        if role == Qt.ItemDataRole.ToolTipRole:
            return vault.path
        if role == VaultRole:
            return vault
        if role == FolderExistsRole:
            return self._exists.get(vault.key, False)
        return None


class VaultDelegate(QStyledItemDelegate):
    PAD_X = 10
    PAD_Y = 7
    MARGIN = 4
    LINE_GAP = 2

    def __init__(self, colors: Callable[[], ThemeColors], parent=None):
        super().__init__(parent)
        self._colors = colors

    def _fonts(self, option: QStyleOptionViewItem) -> tuple[QFont, QFont, QFont]:
        title = QFont(option.font)
        title.setPixelSize(13)
        title.setWeight(QFont.Weight.DemiBold)
        sub = QFont(option.font)
        sub.setPixelSize(11)
        badge = QFont(sub)
        badge.setPixelSize(10)
        return title, sub, badge

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        title, sub, _ = self._fonts(option)
        height = (QFontMetrics(title).height() + self.LINE_GAP + QFontMetrics(sub).height()
                  + 2 * self.PAD_Y + self.MARGIN)
        return QSize(200, height)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        vault: Vault = index.data(VaultRole)
        exists: bool = index.data(FolderExistsRole)
        c = self._colors()
        title_font, sub_font, badge_font = self._fonts(option)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(option.rect).adjusted(self.MARGIN, self.MARGIN // 2,
                                            -self.MARGIN, -self.MARGIN // 2)
        background = None
        if option.state & QStyle.StateFlag.State_Selected:
            background = c.modifier_active
        elif option.state & QStyle.StateFlag.State_MouseOver:
            background = c.modifier_hover
        if background:
            path = QPainterPath()
            path.addRoundedRect(rect, 4, 4)
            painter.fillPath(path, qcolor(background))

        inner = rect.adjusted(self.PAD_X, self.PAD_Y, -self.PAD_X, -self.PAD_Y)
        title_fm = QFontMetrics(title_font)
        sub_fm = QFontMetrics(sub_font)

        badge = None
        if not exists:
            badge = (self.tr("folder missing"), c.text_error)
        elif not vault.in_obsidian:
            badge = (self.tr("not in Obsidian"), c.text_warning)

        title_width = inner.width()
        if badge:
            badge_fm = QFontMetrics(badge_font)
            badge_width = badge_fm.horizontalAdvance(badge[0])
            painter.setFont(badge_font)
            painter.setPen(qcolor(badge[1]))
            painter.drawText(
                QRectF(inner.right() - badge_width, inner.top(), badge_width, title_fm.height()),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                badge[0],
            )
            title_width -= badge_width + 8

        painter.setFont(title_font)
        painter.setPen(qcolor(c.text_normal if exists else c.text_faint))
        painter.drawText(
            QRectF(inner.left(), inner.top(), title_width, title_fm.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title_fm.elidedText(vault.display_name, Qt.TextElideMode.ElideRight, int(title_width)),
        )

        painter.setFont(sub_font)
        painter.setPen(qcolor(c.text_muted if exists else c.text_faint))
        sub_top = inner.top() + title_fm.height() + self.LINE_GAP
        painter.drawText(
            QRectF(inner.left(), sub_top, inner.width(), sub_fm.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            sub_fm.elidedText(display_path(vault.path), Qt.TextElideMode.ElideMiddle,
                              int(inner.width())),
        )
        painter.restore()
