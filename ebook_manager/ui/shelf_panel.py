from typing import Optional, List, Dict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QPushButton, QLabel,
    QMenu, QInputDialog, QMessageBox, QColorDialog, QDialog,
    QDialogButtonBox, QComboBox, QLineEdit, QFormLayout, QToolBar,
    QSizePolicy, QAbstractItemView
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QMimeData, QByteArray, QModelIndex, QSize, QPoint
)
from PyQt6.QtGui import QAction, QIcon, QColor, QPainter, QBrush, QPen
from PyQt6.QtCore import QEvent

from ..shelf_models import (
    ShelfTree, SHELF_ROOT_ID, BOOK_MIME, SHELF_MIME, PATH_SEPARATOR
)
from .shelf_tree_model import ShelfTreeModel


SHELF_ICONS = [
    "📁", "📂", "📚", "📖", "📕", "📗", "📘", "📙",
    "🏠", "🏛️", "🔬", "💻", "📐", "🧠", "🎨", "🎵",
    "⭐", "❤️", "🔥", "🌿", "🎯", "🎭", "📝", "🗂️",
    "📰", "📜", "📓", "📔", "📒", "📃", "📄", "📰",
]

PRESET_COLORS = [
    "", "#e74c3c", "#e67e22", "#f1c40f", "#2ecc71",
    "#1abc9c", "#3498db", "#9b59b6", "#34495e", "#95a5a6"
]


class ShelfTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.DoubleClicked
        )
        self.setUniformRowHeights(True)
        self.setIndentation(20)
        self.setAnimated(True)
        self.setHeaderHidden(False)
        self.setExpandsOnDoubleClick(True)
        self.setAlternatingRowColors(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setStyleSheet("""
            QTreeView {
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
                outline: none;
            }
            QTreeView::item {
                padding: 4px 6px;
                border-radius: 3px;
            }
            QTreeView::item:hover {
                background: #f0f7ff;
            }
            QTreeView::item:selected {
                background: #4a9eff;
                color: white;
            }
            QTreeView::item:selected:!active {
                background: #4a9effcc;
                color: white;
            }
            QTreeView::branch {
                background: transparent;
            }
            QTreeView::branch:has-siblings:!adjoins-item {
                border-image: none;
            }
        """)

    def startDrag(self, supportedActions):
        indexes = self.selectedIndexes()
        valid_indexes = [idx for idx in indexes if idx.column() == 0]
        if not valid_indexes:
            return
        model = self.model()
        if hasattr(model, "mimeData"):
            mime_data = model.mimeData(valid_indexes)
            if mime_data:
                drag = self._create_drag_object()
                drag.setMimeData(mime_data)
                drag.exec(Qt.DropAction.MoveAction)

    def _create_drag_object(self):
        from PyQt6.QtGui import QDrag
        return QDrag(self)

    def expandTo(self, shelf_id: str):
        model = self.model()
        if not hasattr(model, "tree"):
            return
        tree = model.tree
        ancestors = tree.get_ancestors(shelf_id)
        for anc in ancestors:
            if anc.id != SHELF_ROOT_ID:
                idx = model.find_index(anc.id)
                if idx.isValid():
                    self.expand(idx)

    def saveExpandedState(self, model: ShelfTreeModel):
        if not hasattr(model, "tree"):
            return
        tree = model.tree
        for nid in tree.get_all_shelf_ids():
            idx = model.find_index(nid)
            if idx.isValid():
                tree.set_expanded(nid, self.isExpanded(idx))

    def restoreExpandedState(self, model: ShelfTreeModel):
        if not hasattr(model, "tree"):
            return
        tree = model.tree
        root = tree.get_node(SHELF_ROOT_ID)
        if root and root.expanded:
            self.expand(model.find_index(SHELF_ROOT_ID))
        for nid in tree.get_all_shelf_ids():
            node = tree.get_node(nid)
            if node and node.expanded:
                idx = model.find_index(nid)
                if idx.isValid():
                    self.expand(idx)


class ShelfIconPickerDialog(QDialog):
    def __init__(self, current_icon: str = "📁", parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择图标")
        self.setMinimumSize(360, 320)
        self._selected_icon = current_icon
        layout = QVBoxLayout(self)
        from PyQt6.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.setSpacing(4)
        self._buttons = []
        cols = 8
        for i, icon in enumerate(SHELF_ICONS):
            btn = QPushButton(icon)
            btn.setCheckable(True)
            btn.setFixedSize(40, 40)
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 20px;
                    border: 2px solid transparent;
                    border-radius: 6px;
                    background: #fafafa;
                }
                QPushButton:hover {
                    background: #e8f0fe;
                }
                QPushButton:checked {
                    border-color: #4a9eff;
                    background: #e8f0fe;
                }
            """)
            if icon == current_icon:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, ic=icon: self._on_icon_selected(ic))
            grid.addWidget(btn, i // cols, i % cols)
            self._buttons.append((btn, icon))
        layout.addLayout(grid)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_icon_selected(self, icon: str):
        self._selected_icon = icon
        for btn, ic in self._buttons:
            btn.setChecked(ic == icon)

    def get_selected_icon(self) -> str:
        return self._selected_icon


class ShelfColorPickerDialog(QDialog):
    def __init__(self, current_color: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择颜色")
        self.setMinimumSize(320, 180)
        self._selected_color = current_color
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("预设颜色:"))
        from PyQt6.QtWidgets import QGridLayout, QPushButton
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, color in enumerate(PRESET_COLORS):
            btn = QPushButton()
            btn.setFixedSize(40, 40)
            btn.setCheckable(True)
            if color:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {color};
                        border: 2px solid transparent;
                        border-radius: 6px;
                    }}
                    QPushButton:hover {{
                        border-color: #999;
                    }}
                    QPushButton:checked {{
                        border-color: #4a9eff;
                    }}
                """)
            else:
                btn.setText("无")
                btn.setStyleSheet("""
                    QPushButton {
                        background: #fafafa;
                        border: 2px solid transparent;
                        border-radius: 6px;
                        color: #666;
                    }
                    QPushButton:hover {
                        border-color: #999;
                    }
                    QPushButton:checked {
                        border-color: #4a9eff;
                    }
                """)
            if color == current_color:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, c=color: self._on_color_selected(c))
            grid.addWidget(btn, i // 5, i % 5)
        layout.addLayout(grid)
        custom_row = QHBoxLayout()
        custom_btn = QPushButton("自定义颜色...")
        custom_btn.clicked.connect(self._pick_custom_color)
        custom_row.addWidget(custom_btn)
        custom_row.addStretch()
        layout.addLayout(custom_row)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_color_selected(self, color: str):
        self._selected_color = color

    def _pick_custom_color(self):
        initial = QColor(self._selected_color) if self._selected_color else QColor()
        color = QColorDialog.getColor(initial, self, "自定义颜色")
        if color.isValid():
            self._selected_color = color.name()

    def get_selected_color(self) -> str:
        return self._selected_color


class ShelfPanel(QWidget):
    shelf_selected = pyqtSignal(str, bool)
    create_shelf_requested = pyqtSignal(str)
    rename_shelf_requested = pyqtSignal(str)
    delete_shelf_requested = pyqtSignal(str)
    books_moved_to_shelf = pyqtSignal(list, str, bool)
    data_modified = pyqtSignal()

    def __init__(self, shelf_tree: ShelfTree, parent=None):
        super().__init__(parent)
        self._tree = shelf_tree
        self._current_shelf_id: Optional[str] = SHELF_ROOT_ID
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        header = QHBoxLayout()
        title = QLabel("📚 书架")
        title.setStyleSheet("font-weight: bold; font-size: 13px; padding: 4px;")
        header.addWidget(title)
        header.addStretch()
        self.btn_new = QPushButton("➕")
        self.btn_new.setToolTip("新建书架")
        self.btn_new.setFixedSize(28, 28)
        self.btn_rename = QPushButton("✏️")
        self.btn_rename.setToolTip("重命名")
        self.btn_rename.setFixedSize(28, 28)
        self.btn_delete = QPushButton("🗑️")
        self.btn_delete.setToolTip("删除书架")
        self.btn_delete.setFixedSize(28, 28)
        for btn in [self.btn_new, self.btn_rename, self.btn_delete]:
            btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background: white;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: #f0f7ff;
                    border-color: #4a9eff;
                }
            """)
            header.addWidget(btn)
        layout.addLayout(header)
        self.tree_view = ShelfTreeView()
        self.model = ShelfTreeModel(self._tree, self)
        self.tree_view.setModel(self.model)
        layout.addWidget(self.tree_view, stretch=1)
        self.lbl_info = QLabel()
        self.lbl_info.setStyleSheet("color: #666; padding: 4px; font-size: 11px;")
        self.lbl_info.setWordWrap(True)
        layout.addWidget(self.lbl_info)
        self._update_info_label()
        self.tree_view.restoreExpandedState(self.model)
        root_idx = self.model.find_index(SHELF_ROOT_ID)
        if root_idx.isValid():
            self.tree_view.setCurrentIndex(root_idx)

    def _connect_signals(self):
        self.btn_new.clicked.connect(self._on_new_shelf)
        self.btn_rename.clicked.connect(self._on_rename_shelf)
        self.btn_delete.clicked.connect(self._on_delete_shelf)
        self.tree_view.customContextMenuRequested.connect(self._on_context_menu)
        self.tree_view.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        self.tree_view.expanded.connect(self._on_expanded)
        self.tree_view.collapsed.connect(self._on_collapsed)
        self.model.books_dropped.connect(self._on_books_dropped)
        self.model.data_modified.connect(self._on_data_modified)
        self.model.shelf_created.connect(self._on_shelf_created)
        self.model.shelf_deleted.connect(self._on_shelf_deleted)
        self.model.shelf_moved.connect(lambda *_: self._update_info_label())

    def _update_info_label(self):
        total_shelves = self._tree.get_shelf_count()
        total_books = self._tree.get_total_books()
        self.lbl_info.setText(f"书架: {total_shelves} 个  |  藏书: {total_books} 本")

    def _on_data_modified(self):
        self.data_modified.emit()

    def _on_books_dropped(self, book_ids: list, target_shelf_id: str, copy: bool):
        self.books_moved_to_shelf.emit(book_ids, target_shelf_id, copy)
        self._update_info_label()

    def _on_shelf_created(self, shelf_id: str):
        idx = self.model.find_index(shelf_id)
        if idx.isValid():
            self.tree_view.scrollTo(idx)
            self.tree_view.setCurrentIndex(idx)
        self._update_info_label()

    def _on_shelf_deleted(self, shelf_id: str, removed_books: dict):
        if self._current_shelf_id == shelf_id:
            self._current_shelf_id = SHELF_ROOT_ID
            self.shelf_selected.emit(SHELF_ROOT_ID, True)
        self._update_info_label()

    def _on_expanded(self, index: QModelIndex):
        shelf_id = self.model.get_shelf_id(index)
        if shelf_id:
            self._tree.set_expanded(shelf_id, True)
            self.data_modified.emit()

    def _on_collapsed(self, index: QModelIndex):
        shelf_id = self.model.get_shelf_id(index)
        if shelf_id:
            self._tree.set_expanded(shelf_id, False)
            self.data_modified.emit()

    def _on_selection_changed(self, selected, deselected):
        indexes = self.tree_view.selectedIndexes()
        if not indexes:
            return
        first_idx = indexes[0]
        shelf_id = self.model.get_shelf_id(first_idx)
        if shelf_id and shelf_id != self._current_shelf_id:
            self._current_shelf_id = shelf_id
            node = self._tree.get_node(shelf_id)
            recursive = node.is_virtual if node else False
            self.shelf_selected.emit(shelf_id, recursive)

    def _get_selected_shelf_id(self) -> Optional[str]:
        idx = self.tree_view.currentIndex()
        if idx.isValid():
            return self.model.get_shelf_id(idx)
        return None

    def _on_new_shelf(self):
        parent_id = self._get_selected_shelf_id() or SHELF_ROOT_ID
        name, ok = QInputDialog.getText(self, "新建书架", "书架名称:")
        if ok and name.strip():
            new_id = self.model.create_shelf(name.strip(), parent_id)
            if new_id:
                self.create_shelf_requested.emit(new_id)

    def _on_rename_shelf(self):
        shelf_id = self._get_selected_shelf_id()
        if not shelf_id or shelf_id == SHELF_ROOT_ID:
            return
        idx = self.model.find_index(shelf_id)
        if idx.isValid():
            self.tree_view.edit(idx)
            self.rename_shelf_requested.emit(shelf_id)

    def _on_delete_shelf(self):
        shelf_id = self._get_selected_shelf_id()
        if not shelf_id or shelf_id == SHELF_ROOT_ID:
            return
        node = self._tree.get_node(shelf_id)
        if not node:
            return
        desc_count = len(self._tree.get_descendant_ids(shelf_id))
        total_books = node.book_count
        if desc_count > 0:
            for did in self._tree.get_descendant_ids(shelf_id):
                dn = self._tree.get_node(did)
                if dn:
                    total_books += dn.book_count
        msg = f"确定删除书架「{node.name}」？"
        if desc_count > 0:
            msg += f"\n包含 {desc_count} 个子书架"
        if total_books > 0:
            msg += f"，{total_books} 本书籍将移至未分类"
        msg += "\n\n此操作不可撤销"
        reply = QMessageBox.question(
            self, "确认删除", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.model.delete_shelf(shelf_id)
            self.delete_shelf_requested.emit(shelf_id)

    def _on_context_menu(self, pos: QPoint):
        idx = self.tree_view.indexAt(pos)
        shelf_id = self.model.get_shelf_id(idx) if idx.isValid() else SHELF_ROOT_ID
        menu = QMenu(self)
        act_new = QAction("📁 新建子书架", self)
        act_new.triggered.connect(lambda: self._context_new(shelf_id))
        menu.addAction(act_new)
        if shelf_id != SHELF_ROOT_ID:
            menu.addSeparator()
            act_rename = QAction("✏️ 重命名", self)
            act_rename.triggered.connect(lambda: self._context_rename(shelf_id))
            menu.addAction(act_rename)
            act_icon = QAction("🎨 设置图标", self)
            act_icon.triggered.connect(lambda: self._context_set_icon(shelf_id))
            menu.addAction(act_icon)
            act_color = QAction("🌈 设置颜色", self)
            act_color.triggered.connect(lambda: self._context_set_color(shelf_id))
            menu.addAction(act_color)
            menu.addSeparator()
            act_del = QAction("🗑️ 删除书架", self)
            act_del.triggered.connect(lambda: self._context_delete(shelf_id))
            menu.addAction(act_del)
        menu.addSeparator()
        act_expand_all = QAction("🔼 展开全部", self)
        act_expand_all.triggered.connect(self.tree_view.expandAll)
        menu.addAction(act_expand_all)
        act_collapse_all = QAction("🔽 折叠全部", self)
        act_collapse_all.triggered.connect(self.tree_view.collapseAll)
        menu.addAction(act_collapse_all)
        menu.exec(self.tree_view.viewport().mapToGlobal(pos))

    def _context_new(self, parent_id: str):
        name, ok = QInputDialog.getText(self, "新建书架", "书架名称:")
        if ok and name.strip():
            self.model.create_shelf(name.strip(), parent_id)

    def _context_rename(self, shelf_id: str):
        idx = self.model.find_index(shelf_id)
        if idx.isValid():
            self.tree_view.edit(idx)

    def _context_set_icon(self, shelf_id: str):
        node = self._tree.get_node(shelf_id)
        if not node:
            return
        dlg = ShelfIconPickerDialog(node.icon, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            icon = dlg.get_selected_icon()
            idx = self.model.find_index(shelf_id)
            if idx.isValid():
                self.model.setData(idx, icon, ShelfTreeModel.ROLE_SHELF_ICON)

    def _context_set_color(self, shelf_id: str):
        node = self._tree.get_node(shelf_id)
        if not node:
            return
        dlg = ShelfColorPickerDialog(node.color, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            color = dlg.get_selected_color()
            idx = self.model.find_index(shelf_id)
            if idx.isValid():
                self.model.setData(idx, color, ShelfTreeModel.ROLE_SHELF_COLOR)

    def _context_delete(self, shelf_id: str):
        self.tree_view.setCurrentIndex(self.model.find_index(shelf_id))
        self._on_delete_shelf()

    @property
    def tree_model(self) -> ShelfTreeModel:
        return self.model

    def get_current_shelf_id(self) -> Optional[str]:
        return self._current_shelf_id

    def get_selected_books(self, recursive: bool = False) -> List[str]:
        if not self._current_shelf_id:
            return []
        return self._tree.get_books_in_shelf(self._current_shelf_id, recursive)

    def add_books_to_shelf(self, shelf_id: str, book_ids: List[str]):
        for bid in book_ids:
            self._tree.add_book(shelf_id, bid)
        self.model.refresh_node(shelf_id)
        ancestors = self._tree.get_ancestors(shelf_id)
        for anc in ancestors:
            self.model.refresh_node(anc.id)
        self._update_info_label()

    def remove_books_from_shelf(self, shelf_id: str, book_ids: List[str]):
        for bid in book_ids:
            self._tree.remove_book(shelf_id, bid)
        self.model.refresh_node(shelf_id)
        ancestors = self._tree.get_ancestors(shelf_id)
        for anc in ancestors:
            self.model.refresh_node(anc.id)
        self._update_info_label()

    def refresh_current(self):
        if self._current_shelf_id:
            self.model.refresh_node(self._current_shelf_id)

    def save_state(self):
        self.tree_view.saveExpandedState(self.model)

    def reload_tree(self, tree: ShelfTree):
        self._tree = tree
        self.model.set_tree(tree)
        self.tree_view.restoreExpandedState(self.model)
        self._update_info_label()

    def create_drag_mime_data_for_books(self, book_ids: List[str],
                                        source_shelf_id: Optional[str] = None) -> QMimeData:
        mime = QMimeData()
        data = QByteArray(PATH_SEPARATOR.join(book_ids).encode("utf-8"))
        mime.setData(BOOK_MIME, data)
        if source_shelf_id:
            src_data = QByteArray(source_shelf_id.encode("utf-8"))
            mime.setData("application/x-ebook-source-shelf", src_data)
        return mime
