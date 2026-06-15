from typing import Optional, List, Dict, Any
from PyQt6.QtCore import (
    QAbstractItemModel, QModelIndex, Qt, QMimeData, QByteArray,
    pyqtSignal, QVariant
)
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter, QFont, QBrush
from PyQt6.QtWidgets import QStyle, QApplication

from ..shelf_models import (
    ShelfTree, ShelfNode, SHELF_ROOT_ID,
    BOOK_MIME, SHELF_MIME, MOVE_ACTION, COPY_ACTION, PATH_SEPARATOR
)


class ShelfTreeModel(QAbstractItemModel):
    shelves_changed = pyqtSignal()
    shelf_created = pyqtSignal(str)
    shelf_deleted = pyqtSignal(str, dict)
    shelf_moved = pyqtSignal(str, str)
    shelf_renamed = pyqtSignal(str, str)
    books_dropped = pyqtSignal(list, str, bool)
    data_modified = pyqtSignal()

    COLUMN_NAME = 0
    COLUMN_COUNT = 1

    ROLE_SHELF_ID = Qt.ItemDataRole.UserRole + 1
    ROLE_SHELF_PATH = Qt.ItemDataRole.UserRole + 2
    ROLE_SHELF_ICON = Qt.ItemDataRole.UserRole + 3
    ROLE_SHELF_COLOR = Qt.ItemDataRole.UserRole + 4
    ROLE_BOOK_COUNT = Qt.ItemDataRole.UserRole + 5
    ROLE_IS_VIRTUAL = Qt.ItemDataRole.UserRole + 6

    def __init__(self, shelf_tree: ShelfTree, parent=None):
        super().__init__(parent)
        self._tree = shelf_tree
        self._row_cache: Dict[str, int] = {}
        self._rebuild_row_cache()

    @property
    def tree(self) -> ShelfTree:
        return self._tree

    def set_tree(self, tree: ShelfTree):
        self.beginResetModel()
        self._tree = tree
        self._rebuild_row_cache()
        self.endResetModel()

    def _rebuild_row_cache(self):
        self._row_cache.clear()
        self._build_row_cache_recursive(SHELF_ROOT_ID)

    def _build_row_cache_recursive(self, node_id: str):
        children = self._tree.get_children(node_id)
        for row, node in enumerate(children):
            self._row_cache[node.id] = row
            self._build_row_cache_recursive(node.id)

    def _get_shelf_id(self, index: QModelIndex) -> Optional[str]:
        if not index.isValid():
            return SHELF_ROOT_ID
        node = index.internalPointer()
        return node.id if isinstance(node, ShelfNode) else None

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if column < 0 or column >= self.COLUMN_COUNT:
            return QModelIndex()
        parent_id = self._get_shelf_id(parent)
        children = self._tree.get_children(parent_id)
        if 0 <= row < len(children):
            return self.createIndex(row, column, children[row])
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        node = index.internalPointer()
        if not isinstance(node, ShelfNode):
            return QModelIndex()
        parent = self._tree.get_parent(node.id)
        if parent is None or parent.id == SHELF_ROOT_ID:
            return QModelIndex()
        grandparent = self._tree.get_parent(parent.id)
        grandparent_id = grandparent.id if grandparent else SHELF_ROOT_ID
        siblings = self._tree.get_children(grandparent_id)
        for row, sib in enumerate(siblings):
            if sib.id == parent.id:
                return self.createIndex(row, 0, parent)
        return QModelIndex()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        parent_id = self._get_shelf_id(parent)
        if parent_id is None:
            return 0
        return len(self._tree.get_children(parent_id))

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self.COLUMN_COUNT

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return QVariant()
        node = index.internalPointer()
        if not isinstance(node, ShelfNode):
            return QVariant()
        col = index.column()
        if col == self.COLUMN_NAME:
            if role == Qt.ItemDataRole.DisplayRole:
                total = self._tree.get_recursive_book_count(node.id)
                direct = node.book_count
                if node.is_virtual:
                    return f"{node.name}  ({total})"
                if total > direct:
                    return f"{node.name}  ({direct}/{total})"
                return f"{node.name}  ({direct})"
            elif role == Qt.ItemDataRole.DecorationRole:
                return self._create_icon(node)
            elif role == Qt.ItemDataRole.EditRole:
                return node.name
            elif role == Qt.ItemDataRole.ToolTipRole:
                return self._tree.get_full_path(node.id)
            elif role == Qt.ItemDataRole.ForegroundRole:
                if node.color:
                    return QBrush(QColor(node.color))
            elif role == Qt.ItemDataRole.BackgroundRole:
                if node.color:
                    return QBrush(QColor(node.color).lighter(195))
            elif role == Qt.ItemDataRole.FontRole:
                if node.is_virtual:
                    f = QFont()
                    f.setBold(True)
                    return f
            elif role == self.ROLE_SHELF_ID:
                return node.id
            elif role == self.ROLE_SHELF_PATH:
                return node.path
            elif role == self.ROLE_SHELF_ICON:
                return node.icon
            elif role == self.ROLE_SHELF_COLOR:
                return node.color
            elif role == self.ROLE_BOOK_COUNT:
                return node.book_count
            elif role == self.ROLE_IS_VIRTUAL:
                return node.is_virtual
        return QVariant()

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False
        node = index.internalPointer()
        if not isinstance(node, ShelfNode):
            return False
        if role == Qt.ItemDataRole.EditRole:
            new_name = str(value).strip()
            if not new_name:
                return False
            if self._tree.rename_shelf(node.id, new_name):
                self.data_modified.emit()
                self.shelf_renamed.emit(node.id, new_name)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                return True
        elif role == self.ROLE_SHELF_ICON:
            if self._tree.set_shelf_icon(node.id, str(value)):
                self.data_modified.emit()
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])
                return True
        elif role == self.ROLE_SHELF_COLOR:
            if self._tree.set_shelf_color(node.id, str(value)):
                self.data_modified.emit()
                self.dataChanged.emit(index, index, [
                    Qt.ItemDataRole.ForegroundRole, Qt.ItemDataRole.BackgroundRole
                ])
                return True
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        default_flags = (
            Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsDragEnabled
            | Qt.ItemFlag.ItemIsDropEnabled
        )
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled
        node = index.internalPointer()
        if isinstance(node, ShelfNode) and node.is_virtual:
            return default_flags
        return default_flags | Qt.ItemFlag.ItemIsEditable

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and section == self.COLUMN_NAME:
            if role == Qt.ItemDataRole.DisplayRole:
                return "📚 书架"
        return QVariant()

    def supportedDropActions(self) -> Qt.DropAction:
        return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction

    def supportedDragActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def mimeTypes(self) -> List[str]:
        return [SHELF_MIME, BOOK_MIME]

    def mimeData(self, indexes: List[QModelIndex]) -> QMimeData:
        mime_data = QMimeData()
        shelf_ids = []
        for idx in indexes:
            if idx.isValid() and idx.column() == self.COLUMN_NAME:
                node = idx.internalPointer()
                if isinstance(node, ShelfNode) and not node.is_virtual:
                    shelf_ids.append(node.id)
        if shelf_ids:
            data = QByteArray(PATH_SEPARATOR.join(shelf_ids).encode("utf-8"))
            mime_data.setData(SHELF_MIME, data)
        return mime_data

    def canDropMimeData(self, data: QMimeData, action: Qt.DropAction,
                        row: int, column: int, parent: QModelIndex) -> bool:
        if column > 0:
            return False
        target_id = self._get_shelf_id(parent)
        if target_id is None:
            return False
        if data.hasFormat(SHELF_MIME):
            raw = bytes(data.data(SHELF_MIME)).decode("utf-8")
            shelf_ids = [s for s in raw.split(PATH_SEPARATOR) if s]
            if not shelf_ids:
                return False
            for sid in shelf_ids:
                if sid == target_id:
                    return False
                if self._tree.is_descendant(sid, target_id):
                    return False
            return True
        if data.hasFormat(BOOK_MIME):
            if self._tree.get_node(target_id) is None:
                return False
            return True
        return False

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction,
                     row: int, column: int, parent: QModelIndex) -> bool:
        if not self.canDropMimeData(data, action, row, column, parent):
            return False
        target_id = self._get_shelf_id(parent)
        if target_id is None:
            return False
        if data.hasFormat(SHELF_MIME):
            raw = bytes(data.data(SHELF_MIME)).decode("utf-8")
            shelf_ids = [s for s in raw.split(PATH_SEPARATOR) if s]
            return self._handle_shelf_drop(shelf_ids, target_id, row, action)
        if data.hasFormat(BOOK_MIME):
            raw = bytes(data.data(BOOK_MIME)).decode("utf-8")
            book_ids = [s for s in raw.split(PATH_SEPARATOR) if s]
            copy = (action == Qt.DropAction.CopyAction)
            source_id = None
            if data.hasFormat("application/x-ebook-source-shelf"):
                source_id = bytes(data.data("application/x-ebook-source-shelf")).decode("utf-8")
            self.books_dropped.emit(book_ids, target_id, copy)
            self._notify_books_changed(source_id, target_id)
            return True
        return False

    def _handle_shelf_drop(self, shelf_ids: List[str], target_id: str,
                           row: int, action: Qt.DropAction) -> bool:
        if not shelf_ids:
            return False
        for sid in shelf_ids:
            insert_idx = row if row >= 0 else -1
            old_parent = self._tree.get_parent(sid)
            old_parent_id = old_parent.id if old_parent else SHELF_ROOT_ID
            self._begin_move_shelf(sid, old_parent_id, target_id, insert_idx)
            result = self._tree.move_shelf(sid, target_id, insert_idx)
            if result:
                self._end_move_shelf(sid, old_parent_id, target_id)
                self.data_modified.emit()
                self.shelf_moved.emit(sid, target_id)
        return True

    def _begin_move_shelf(self, shelf_id: str, old_parent_id: str,
                          new_parent_id: str, insert_index: int):
        old_siblings = self._tree.get_children(old_parent_id)
        old_row = -1
        for i, s in enumerate(old_siblings):
            if s.id == shelf_id:
                old_row = i
                break
        if old_row < 0:
            return
        new_siblings = self._tree.get_children(new_parent_id)
        if new_parent_id == old_parent_id:
            target_row = insert_index if insert_index >= 0 else len(new_siblings) - 1
            if insert_index > old_row:
                target_row -= 1
            old_parent_idx = self._index_for_id(old_parent_id)
            self.beginMoveRows(old_parent_idx, old_row, old_row, old_parent_idx, target_row)
        else:
            old_parent_idx = self._index_for_id(old_parent_id)
            new_parent_idx = self._index_for_id(new_parent_id)
            target_row = insert_index if insert_index >= 0 else len(new_siblings)
            self.beginMoveRows(old_parent_idx, old_row, old_row, new_parent_idx, target_row)

    def _end_move_shelf(self, shelf_id: str, old_parent_id: str, new_parent_id: str):
        self.endMoveRows()
        self._rebuild_row_cache()
        old_parent_idx = self._index_for_id(old_parent_id)
        if old_parent_idx.isValid():
            self.dataChanged.emit(old_parent_idx, old_parent_idx, [Qt.ItemDataRole.DisplayRole])
        new_parent_idx = self._index_for_id(new_parent_id)
        if new_parent_idx.isValid():
            self.dataChanged.emit(new_parent_idx, new_parent_idx, [Qt.ItemDataRole.DisplayRole])

    def _index_for_id(self, shelf_id: str) -> QModelIndex:
        if shelf_id == SHELF_ROOT_ID:
            return QModelIndex()
        node = self._tree.get_node(shelf_id)
        if node is None or node.parent_id is None:
            return QModelIndex()
        siblings = self._tree.get_children(node.parent_id)
        for row, sib in enumerate(siblings):
            if sib.id == shelf_id:
                return self.createIndex(row, 0, node)
        return QModelIndex()

    def _notify_books_changed(self, source_id: Optional[str], target_id: str):
        if source_id:
            src_idx = self._index_for_id(source_id)
            if src_idx.isValid():
                self.dataChanged.emit(src_idx, src_idx, [Qt.ItemDataRole.DisplayRole])
        tgt_idx = self._index_for_id(target_id)
        if tgt_idx.isValid():
            self.dataChanged.emit(tgt_idx, tgt_idx, [Qt.ItemDataRole.DisplayRole])

    def create_shelf(self, name: str, parent_id: Optional[str] = None,
                     icon: str = "📁", color: str = "") -> Optional[str]:
        pid = parent_id if parent_id is not None else SHELF_ROOT_ID
        parent_idx = self._index_for_id(pid)
        children = self._tree.get_children(pid)
        row = len(children)
        self.beginInsertRows(parent_idx, row, row)
        node = self._tree.create_shelf(name, pid, icon, color)
        self._rebuild_row_cache()
        self.endInsertRows()
        self.data_modified.emit()
        self.shelf_created.emit(node.id)
        if parent_idx.isValid():
            self.dataChanged.emit(parent_idx, parent_idx, [Qt.ItemDataRole.DisplayRole])
        return node.id

    def delete_shelf(self, shelf_id: str) -> Dict[str, List[str]]:
        if shelf_id == SHELF_ROOT_ID:
            return {}
        node = self._tree.get_node(shelf_id)
        if node is None or node.parent_id is None:
            return {}
        parent_idx = self._index_for_id(node.parent_id)
        siblings = self._tree.get_children(node.parent_id)
        row = -1
        for i, s in enumerate(siblings):
            if s.id == shelf_id:
                row = i
                break
        if row < 0:
            return {}
        self.beginRemoveRows(parent_idx, row, row)
        removed_books = self._tree.delete_shelf(shelf_id)
        self._rebuild_row_cache()
        self.endRemoveRows()
        self.data_modified.emit()
        self.shelf_deleted.emit(shelf_id, removed_books)
        if parent_idx.isValid():
            self.dataChanged.emit(parent_idx, parent_idx, [Qt.ItemDataRole.DisplayRole])
        return removed_books

    def get_shelf_id(self, index: QModelIndex) -> Optional[str]:
        return self._get_shelf_id(index)

    def get_shelf_node(self, index: QModelIndex) -> Optional[ShelfNode]:
        if not index.isValid():
            return None
        node = index.internalPointer()
        return node if isinstance(node, ShelfNode) else None

    def find_index(self, shelf_id: str) -> QModelIndex:
        return self._index_for_id(shelf_id)

    def refresh_node(self, shelf_id: str):
        idx = self._index_for_id(shelf_id)
        if idx.isValid():
            self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])

    def refresh_all(self):
        self.dataChanged.emit(
            self.index(0, 0),
            self.index(self.rowCount() - 1, 0),
            [Qt.ItemDataRole.DisplayRole]
        )

    def _create_icon(self, node: ShelfNode) -> QIcon:
        size = 24
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if node.color:
            color = QColor(node.color)
            painter.setBrush(color.lighter(180))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(1, 1, size - 2, size - 2, 4, 4)
        font = QFont()
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, node.icon or "📁")
        painter.end()
        return QIcon(pixmap)
