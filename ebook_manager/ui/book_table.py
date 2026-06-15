from typing import Optional, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QMenu, QAbstractItemView, QPushButton, QLineEdit,
    QComboBox, QLabel, QDrag
)
from PyQt6.QtCore import pyqtSignal, Qt, QMimeData, QByteArray, QPoint
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from ..models import BookMeta
from ..shelf_models import BOOK_MIME, SHELF_MIME, PATH_SEPARATOR


class DraggableBookTable(QTableWidget):
    books_dragged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._source_shelf_id: Optional[str] = None
        self._book_id_to_row: dict = {}

    def set_source_shelf(self, shelf_id: Optional[str]):
        self._source_shelf_id = shelf_id

    def startDrag(self, supportedActions):
        rows = set()
        for idx in self.selectedIndexes():
            rows.add(idx.row())
        if not rows:
            return
        book_ids = []
        for row in sorted(rows):
            item = self.item(row, 1)
            if item:
                bid = item.data(Qt.ItemDataRole.UserRole + 1)
                if bid:
                    book_ids.append(bid)
        if not book_ids:
            return
        mime = QMimeData()
        data = QByteArray(PATH_SEPARATOR.join(book_ids).encode("utf-8"))
        mime.setData(BOOK_MIME, data)
        if self._source_shelf_id:
            src_data = QByteArray(self._source_shelf_id.encode("utf-8"))
            mime.setData("application/x-ebook-source-shelf", src_data)
        drag = QDrag(self)
        drag.setMimeData(mime)
        action = drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)
        self.books_dragged.emit(book_ids)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasFormat(BOOK_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(BOOK_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        event.ignore()

    def update_book_index(self, book_id_to_row: dict):
        self._book_id_to_row = book_id_to_row


class BookTableWidget(QWidget):
    selection_changed = pyqtSignal(list)
    edit_requested = pyqtSignal(list)
    convert_requested = pyqtSignal(list)
    search_meta_requested = pyqtSignal(list)
    books_dragged_to_shelf = pyqtSignal(list, str, bool)
    move_books_to_shelf = pyqtSignal(list, str)

    COLUMNS = [
        ("选择", 40),
        ("书架", 80),
        ("书名", 200),
        ("作者", 150),
        ("出版社", 150),
        ("出版日期", 100),
        ("ISBN", 130),
        ("语言", 60),
        ("格式", 60),
        ("大小", 80),
        ("路径", 250),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._books: list = []
        self._filtered_books: list = []
        self._current_shelf_id: Optional[str] = None
        self._shelf_tree = None
        self._shelf_names: dict = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self._select_all)
        toolbar.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("取消全选")
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        toolbar.addWidget(self.deselect_all_btn)

        toolbar.addStretch()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索书名/作者...")
        self.search_edit.setFixedWidth(250)
        self.search_edit.textChanged.connect(self._filter_table)
        toolbar.addWidget(self.search_edit)

        self.format_filter = QComboBox()
        self.format_filter.addItem("全部格式")
        self.format_filter.addItem("EPUB")
        self.format_filter.addItem("MOBI")
        self.format_filter.addItem("PDF")
        self.format_filter.currentTextChanged.connect(self._filter_table)
        toolbar.addWidget(self.format_filter)

        self.count_label = QLabel("")
        toolbar.addWidget(self.count_label)
        layout.addLayout(toolbar)

        self.table = DraggableBookTable()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in self.COLUMNS])
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.books_dragged.connect(self._on_books_dragged)

        header = self.table.horizontalHeader()
        for i, (_, width) in enumerate(self.COLUMNS):
            header.setMinimumSectionSize(30)
            if i == 0:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(i, width)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                self.table.setColumnWidth(i, width)

        header.setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

    def set_shelf_tree(self, shelf_tree):
        self._shelf_tree = shelf_tree
        self._rebuild_shelf_names()

    def _rebuild_shelf_names(self):
        self._shelf_names.clear()
        if not self._shelf_tree:
            return
        for sid in self._shelf_tree.get_all_shelf_ids():
            node = self._shelf_tree.get_node(sid)
            if node:
                self._shelf_names[sid] = node.name

    def set_current_shelf(self, shelf_id: Optional[str], recursive: bool = False):
        self._current_shelf_id = shelf_id
        self.table.set_source_shelf(shelf_id if shelf_id != "root" else None)
        self._filter_table()

    def load_books(self, books: list):
        self._books = books
        self._filter_table()

    def _filter_table(self):
        keyword = self.search_edit.text().lower()
        fmt = self.format_filter.currentText()
        filtered = []
        for book in self._books:
            if self._current_shelf_id and self._current_shelf_id != "root":
                if not self._match_shelf_filter(book):
                    continue
            if fmt != "全部格式" and book.file_format.upper() != fmt:
                continue
            if keyword:
                searchable = f"{book.title} {book.author} {book.isbn} {book.publisher}".lower()
                if keyword not in searchable:
                    continue
            filtered.append(book)
        self._filtered_books = filtered
        self._populate_table(filtered)

    def _match_shelf_filter(self, book: BookMeta) -> bool:
        if not self._current_shelf_id or self._current_shelf_id == "root":
            return True
        if not self._shelf_tree:
            return self._current_shelf_id in book.shelf_ids
        node = self._shelf_tree.get_node(self._current_shelf_id)
        if not node:
            return False
        if node.is_virtual:
            return True
        if self._current_shelf_id in book.shelf_ids:
            return True
        descendant_ids = self._shelf_tree.get_descendant_ids(self._current_shelf_id)
        for sid in book.shelf_ids:
            if sid in descendant_ids:
                return True
        return False

    def _populate_table(self, books: list):
        self.table.blockSignals(True)
        self.table.setRowCount(len(books))
        book_id_to_row = {}
        for row, book in enumerate(books):
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check_item.setCheckState(Qt.CheckState.Unchecked)
            check_item.setData(Qt.ItemDataRole.UserRole, row)
            self.table.setItem(row, 0, check_item)

            shelf_text = self._get_shelf_text(book)
            shelf_item = QTableWidgetItem(shelf_text)
            shelf_item.setToolTip("\n".join([
                self._shelf_names.get(sid, sid) for sid in book.shelf_ids
            ]))
            self.table.setItem(row, 1, shelf_item)

            title_item = QTableWidgetItem(book.title)
            title_item.setData(Qt.ItemDataRole.UserRole + 1, book.book_id)
            title_item.setData(Qt.ItemDataRole.ToolTipRole, book.title)
            self.table.setItem(row, 2, title_item)

            self.table.setItem(row, 3, QTableWidgetItem(book.author))
            self.table.setItem(row, 4, QTableWidgetItem(book.publisher))
            self.table.setItem(row, 5, QTableWidgetItem(book.publish_date))
            self.table.setItem(row, 6, QTableWidgetItem(book.isbn))
            self.table.setItem(row, 7, QTableWidgetItem(book.language))
            self.table.setItem(row, 8, QTableWidgetItem(book.file_format.upper()))

            size_item = QTableWidgetItem(BookMeta.format_size(book.file_size))
            size_item.setData(Qt.ItemDataRole.UserRole, book.file_size)
            self.table.setItem(row, 9, size_item)

            self.table.setItem(row, 10, QTableWidgetItem(book.file_path))
            book_id_to_row[book.book_id] = row
        self.table.update_book_index(book_id_to_row)
        self.table.blockSignals(False)
        self.count_label.setText(f"共 {len(books)} 本")

    def _get_shelf_text(self, book: BookMeta) -> str:
        if not book.shelf_ids:
            return "未分类"
        if len(book.shelf_ids) == 1:
            return self._shelf_names.get(book.shelf_ids[0], "📁")
        return f"📁×{len(book.shelf_ids)}"

    def get_selected_books(self) -> list:
        selected = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                idx = item.data(Qt.ItemDataRole.UserRole)
                if 0 <= idx < len(self._filtered_books):
                    selected.append(self._filtered_books[idx])
        return selected

    def get_visible_books(self) -> list:
        return list(self._filtered_books)

    def refresh_all(self):
        if self._shelf_tree:
            self._rebuild_shelf_names()
        self._filter_table()

    def refresh_row(self, row_idx: int, book: BookMeta):
        if 0 <= row_idx < len(self._filtered_books):
            self._filtered_books[row_idx] = book
            self.table.blockSignals(True)
            self.table.item(row_idx, 1).setText(self._get_shelf_text(book))
            self.table.item(row_idx, 2).setText(book.title)
            self.table.item(row_idx, 3).setText(book.author)
            self.table.item(row_idx, 4).setText(book.publisher)
            self.table.item(row_idx, 5).setText(book.publish_date)
            self.table.item(row_idx, 6).setText(book.isbn)
            self.table.item(row_idx, 7).setText(book.language)
            self.table.blockSignals(False)

    def _select_all(self):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.CheckState.Checked)
        self.table.blockSignals(False)
        self._notify_selection()

    def _deselect_all(self):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.CheckState.Unchecked)
        self.table.blockSignals(False)
        self._notify_selection()

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() == 0:
            self._notify_selection()

    def _notify_selection(self):
        self.selection_changed.emit(self.get_selected_books())

    def _on_books_dragged(self, book_ids: list):
        pass

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        edit_action = menu.addAction("✏️ 编辑元数据")
        search_action = menu.addAction("🔍 在线搜索元数据")
        convert_action = menu.addAction("🔄 转换格式")
        menu.addSeparator()
        move_menu = menu.addMenu("📁 移动到书架")
        self._populate_shelf_menu(move_menu, is_copy=False)
        copy_menu = menu.addMenu("📋 复制到书架")
        self._populate_shelf_menu(copy_menu, is_copy=True)
        if self._current_shelf_id and self._current_shelf_id != "root":
            menu.addSeparator()
            remove_action = menu.addAction("↩️ 从当前书架移除")
        menu.addSeparator()
        open_action = menu.addAction("📂 打开文件位置")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        selected = self.get_selected_books()
        if not selected:
            return
        if action == edit_action:
            self.edit_requested.emit(selected)
        elif action == search_action:
            self.search_meta_requested.emit(selected)
        elif action == convert_action:
            self.convert_requested.emit(selected)
        elif action == open_action:
            import os
            import subprocess
            path = selected[0].file_path
            if os.path.exists(path):
                subprocess.Popen(f'explorer /select,"{path}"')
        elif 'remove_action' in locals() and action == remove_action:
            self._remove_from_current_shelf(selected)

    def _populate_shelf_menu(self, menu: QMenu, is_copy: bool):
        if not self._shelf_tree:
            return
        for sid in [None] + self._shelf_tree.get_all_shelf_ids():
            if sid is None:
                name = "🏠 全部书架 (根)"
                shelf_id_real = "root"
            else:
                node = self._shelf_tree.get_node(sid)
                if not node:
                    continue
                depth = len(self._shelf_tree.get_ancestors(sid))
                prefix = "  " * depth + ("└ " if depth > 0 else "")
                name = f"{prefix}{node.icon} {node.name}"
                shelf_id_real = sid
            act = QAction(name, menu)
            act.triggered.connect(
                lambda checked, s=shelf_id_real, c=is_copy:
                self._handle_shelf_menu_action(s, c)
            )
            menu.addAction(act)

    def _handle_shelf_menu_action(self, shelf_id: str, is_copy: bool):
        selected = self.get_selected_books()
        if not selected:
            return
        book_ids = [b.book_id for b in selected]
        source_shelf = self._current_shelf_id if not is_copy else None
        self.books_dragged_to_shelf.emit(book_ids, shelf_id, is_copy)
        if not is_copy and source_shelf and source_shelf != "root":
            self.move_books_to_shelf.emit(book_ids, source_shelf)

    def _remove_from_current_shelf(self, books: list):
        if not self._current_shelf_id or self._current_shelf_id == "root":
            return
        for book in books:
            book.remove_from_shelf(self._current_shelf_id)
            if self._shelf_tree:
                self._shelf_tree.remove_book(self._current_shelf_id, book.book_id)
        self.refresh_all()
