from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStatusBar, QMessageBox, QTabWidget, QLabel, QApplication,
    QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon, QCloseEvent

from ..models import BookMeta
from ..scanner import BookshelfScanner
from ..metadata_parser import MetadataParser
from ..metadata_editor import MetadataEditor
from ..network_source import NetworkSourceManager
from ..converter import FormatConverter
from ..shelf_models import ShelfTree, ShelfStorage, SHELF_ROOT_ID

from .scanner_panel import ScannerPanel
from .book_table import BookTableWidget
from .edit_panel import MetadataEditPanel
from .search_dialog import OnlineSearchDialog
from .convert_dialog import ConvertDialog
from .workers import ScanWorker, ParseWorker
from .shelf_panel import ShelfPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📚 电子书元数据管理器")
        self.setMinimumSize(1400, 800)

        self._books: list = []
        self._book_index: dict = {}
        self._scanner = BookshelfScanner()
        self._parser = MetadataParser()
        self._editor = MetadataEditor()
        self._source_manager = NetworkSourceManager()
        self._converter = FormatConverter()
        self._shelf_storage = ShelfStorage()
        self._shelf_tree = self._shelf_storage.load()

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(5000)
        self._autosave_timer.timeout.connect(self._auto_save_shelves)
        self._autosave_timer.start()

        self._init_ui()
        self._init_menu()
        self._init_statusbar()
        self._sync_books_to_shelf_tree()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        self.scanner_panel = ScannerPanel()
        self.scanner_panel.scan_requested.connect(self._on_scan_requested)
        main_layout.addWidget(self.scanner_panel)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.shelf_panel = ShelfPanel(self._shelf_tree, self)
        self.shelf_panel.shelf_selected.connect(self._on_shelf_selected)
        self.shelf_panel.books_moved_to_shelf.connect(self._on_books_dropped_from_shelf)
        self.shelf_panel.data_modified.connect(self._on_shelf_data_modified)
        self.shelf_panel.setMinimumWidth(240)
        main_splitter.addWidget(self.shelf_panel)

        right_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.book_table = BookTableWidget()
        self.book_table.set_shelf_tree(self._shelf_tree)
        self.book_table.selection_changed.connect(self._on_selection_changed)
        self.book_table.edit_requested.connect(self._on_edit_requested)
        self.book_table.convert_requested.connect(self._on_convert_requested)
        self.book_table.search_meta_requested.connect(self._on_search_meta_requested)
        self.book_table.books_dragged_to_shelf.connect(self._on_books_moved_to_shelf)
        self.book_table.move_books_to_shelf.connect(self._on_books_removed_from_shelf)
        right_splitter.addWidget(self.book_table)

        self.edit_panel = MetadataEditPanel()
        self.edit_panel.save_requested.connect(self._on_save_metadata)
        right_splitter.addWidget(self.edit_panel)

        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 1)
        right_splitter.setSizes([600, 300])
        main_splitter.addWidget(right_splitter)

        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 5)
        main_splitter.setSizes([260, 900])
        main_layout.addWidget(main_splitter, stretch=1)

        self.setStyleSheet("""
            QMainWindow { background: #f5f6fa; }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                gridline-color: #eee;
                selection-background-color: #4a9eff33;
                selection-color: #000;
            }
            QTableWidget::item:hover { background: #f0f7ff; }
            QHeaderView::section {
                background: #fafafa;
                border: none;
                border-bottom: 2px solid #ddd;
                padding: 6px;
                font-weight: bold;
            }
            QLineEdit, QTextEdit, QComboBox {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #4a9eff;
            }
            QPushButton {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 4px 12px;
                background: white;
            }
            QPushButton:hover { background: #f0f7ff; border-color: #4a9eff; }
            QSplitter::handle {
                background: #e0e0e0;
                width: 2px;
            }
            QSplitter::handle:hover {
                background: #4a9eff;
            }
        """)

    def _init_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件(&F)")
        import_action = QAction("导入文件(&I)...", self)
        import_action.triggered.connect(self._import_files)
        file_menu.addAction(import_action)

        import_dir_action = QAction("导入目录(&D)...", self)
        import_dir_action.triggered.connect(self._import_directory)
        file_menu.addAction(import_dir_action)

        file_menu.addSeparator()
        save_shelf_action = QAction("💾 保存书架数据", self)
        save_shelf_action.triggered.connect(self._save_shelves_force)
        file_menu.addAction(save_shelf_action)

        file_menu.addSeparator()
        exit_action = QAction("退出(&Q)", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu("编辑(&E)")
        batch_edit_action = QAction("批量编辑(&B)", self)
        batch_edit_action.triggered.connect(lambda: self._on_edit_requested(self.book_table.get_selected_books()))
        edit_menu.addAction(batch_edit_action)

        search_meta_action = QAction("在线搜索元数据(&S)", self)
        search_meta_action.triggered.connect(lambda: self._on_search_meta_requested(self.book_table.get_selected_books()))
        edit_menu.addAction(search_meta_action)

        shelf_menu = menubar.addMenu("书架(&K)")
        new_shelf_action = QAction("📁 新建书架", self)
        new_shelf_action.triggered.connect(lambda: self.shelf_panel._on_new_shelf())
        shelf_menu.addAction(new_shelf_action)

        expand_all_action = QAction("🔼 展开全部", self)
        expand_all_action.triggered.connect(lambda: self.shelf_panel.tree_view.expandAll())
        shelf_menu.addAction(expand_all_action)

        collapse_all_action = QAction("🔽 折叠全部", self)
        collapse_all_action.triggered.connect(lambda: self.shelf_panel.tree_view.collapseAll())
        shelf_menu.addAction(collapse_all_action)

        tool_menu = menubar.addMenu("工具(&T)")
        convert_action = QAction("格式转换(&C)...", self)
        convert_action.triggered.connect(lambda: self._on_convert_requested(self.book_table.get_selected_books()))
        tool_menu.addAction(convert_action)

        calibre_status = QAction("Calibre 状态检查", self)
        calibre_status.triggered.connect(self._check_calibre)
        tool_menu.addAction(calibre_status)

        help_menu = menubar.addMenu("帮助(&H)")
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _init_statusbar(self):
        self.statusBar().showMessage("就绪")

    def _rebuild_book_index(self):
        self._book_index.clear()
        for book in self._books:
            self._book_index[book.book_id] = book

    def _get_book_by_id(self, book_id: str) -> BookMeta:
        return self._book_index.get(book_id)

    def _sync_books_to_shelf_tree(self):
        self._rebuild_book_index()
        for sid in self._shelf_tree.get_all_shelf_ids() + [SHELF_ROOT_ID]:
            node = self._shelf_tree.get_node(sid)
            if node:
                node.book_ids = []
                node.book_count = 0
        for book in self._books:
            for sid in book.shelf_ids:
                self._shelf_tree.add_book(sid, book.book_id)
        root = self._shelf_tree.get_node(SHELF_ROOT_ID)
        if root:
            root.book_count = len(self._books)
        self._shelf_storage.mark_dirty()

    def _on_shelf_selected(self, shelf_id: str, recursive: bool):
        self.book_table.set_current_shelf(shelf_id, recursive)
        node = self._shelf_tree.get_node(shelf_id)
        if node:
            path = self._shelf_tree.get_full_path(shelf_id)
            self.statusBar().showMessage(
                f"当前: {path}  ({node.book_count} 本)"
            )

    def _on_shelf_data_modified(self):
        self._shelf_storage.mark_dirty()
        self.book_table.refresh_all()

    def _on_books_dropped_from_shelf(self, book_ids: list, target_shelf_id: str, copy: bool):
        self._handle_book_move(book_ids, target_shelf_id, copy)

    def _on_books_moved_to_shelf(self, book_ids: list, target_shelf_id: str, copy: bool):
        self._handle_book_move(book_ids, target_shelf_id, copy)

    def _on_books_removed_from_shelf(self, book_ids: list, source_shelf_id: str):
        for bid in book_ids:
            book = self._get_book_by_id(bid)
            if book:
                book.remove_from_shelf(source_shelf_id)
        self.book_table.refresh_all()
        self._shelf_storage.mark_dirty()

    def _handle_book_move(self, book_ids: list, target_shelf_id: str, copy: bool):
        real_target = target_shelf_id if target_shelf_id != "root" else None
        count = 0
        for bid in book_ids:
            book = self._get_book_by_id(bid)
            if not book:
                continue
            if real_target:
                if copy:
                    book.add_to_shelf(real_target)
                    self._shelf_tree.add_book(real_target, bid)
                else:
                    if not book.shelf_ids:
                        book.add_to_shelf(real_target)
                        self._shelf_tree.add_book(real_target, bid)
                    else:
                        old_shelves = list(book.shelf_ids)
                        for sid in old_shelves:
                            book.remove_from_shelf(sid)
                            self._shelf_tree.remove_book(sid, bid)
                        book.add_to_shelf(real_target)
                        self._shelf_tree.add_book(real_target, bid)
            else:
                if not copy:
                    for sid in list(book.shelf_ids):
                        book.remove_from_shelf(sid)
                        self._shelf_tree.remove_book(sid, bid)
            count += 1
        self.shelf_panel.refresh_current()
        self.book_table.refresh_all()
        self._shelf_storage.mark_dirty()
        if real_target:
            node = self._shelf_tree.get_node(real_target)
            name = node.name if node else real_target
            action = "复制到" if copy else "移动到"
            self.statusBar().showMessage(f"已{action}「{name}」: {count} 本")
        else:
            self.statusBar().showMessage(f"已移除书架分类: {count} 本")

    def _auto_save_shelves(self):
        if self._shelf_storage.is_dirty:
            self.shelf_panel.save_state()
            self._shelf_storage.save(self._shelf_tree)

    def _save_shelves_force(self):
        self.shelf_panel.save_state()
        self._shelf_storage.save(self._shelf_tree, force=True)
        self.statusBar().showMessage("✅ 书架数据已保存", 3000)

    def closeEvent(self, event: QCloseEvent):
        self.shelf_panel.save_state()
        self._shelf_storage.save(self._shelf_tree, force=True)
        event.accept()

    def _on_scan_requested(self, directories: list, recursive: bool):
        self.statusBar().showMessage("正在扫描目录...")
        self._scan_worker = ScanWorker(directories, recursive)
        self._scan_worker.progress.connect(self.scanner_panel.on_scan_progress)
        self._scan_worker.finished_signal.connect(self._on_scan_finished)
        self._scan_worker.start()

    def _on_scan_finished(self, files: list):
        self.scanner_panel.on_scan_complete(len(files))
        if not files:
            self.statusBar().showMessage("未找到电子书文件")
            return
        self.statusBar().showMessage(f"扫描到 {len(files)} 个文件，正在解析元数据...")
        self._parse_worker = ParseWorker(files)
        self._parse_worker.progress.connect(
            lambda c, t, p: self.statusBar().showMessage(f"解析中 {c}/{t}: {Path(p).name}")
        )
        self._parse_worker.finished_signal.connect(self._on_parse_finished)
        self._parse_worker.start()

    def _on_parse_finished(self, books: list):
        existing_ids = {b.book_id for b in self._books}
        for b in books:
            if b.book_id not in existing_ids:
                self._books.append(b)
        self._sync_books_to_shelf_tree()
        self.book_table.load_books(self._books)
        self.statusBar().showMessage(f"已加载 {len(self._books)} 本电子书")

    def _on_selection_changed(self, selected: list):
        self.edit_panel.set_books(selected)
        self.statusBar().showMessage(f"已选择 {len(selected)} 本")

    def _on_edit_requested(self, books: list):
        if books:
            self.edit_panel.set_books(books)

    def _on_save_metadata(self, books: list, changes: dict):
        self._editor.apply_batch(books, changes)
        for book in books:
            if book.file_format == "epub":
                self._editor.save_epub_metadata(book)
        self.book_table.load_books(self._books)
        self.statusBar().showMessage(f"已更新 {len(books)} 本书的元数据")

    def _on_search_meta_requested(self, books: list):
        if not books:
            QMessageBox.information(self, "提示", "请先选择书籍")
            return
        dialog = OnlineSearchDialog(books, self._source_manager, self)
        if dialog.exec() == OnlineSearchDialog.DialogCode.Accepted:
            data = dialog.get_selected_data()
            if data:
                overwrite = QMessageBox.question(
                    self,
                    "确认",
                    "是否用搜索结果覆盖已有元数据？\n选\"是\"覆盖全部，选\"否\"仅填充空字段",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                )
                if overwrite == QMessageBox.StandardButton.Cancel:
                    return
                for book in books:
                    self._editor.merge_from_source(book, data, overwrite=(overwrite == QMessageBox.StandardButton.Yes))
                    if book.file_format == "epub":
                        self._editor.save_epub_metadata(book)
                self.book_table.load_books(self._books)
                self.statusBar().showMessage(f"已从在线源填充 {len(books)} 本书的元数据")

    def _on_convert_requested(self, books: list):
        if not books:
            books = self.book_table.get_selected_books()
        if not books:
            QMessageBox.information(self, "提示", "请先选择要转换的书籍")
            return
        dialog = ConvertDialog(books, self._converter, self)
        dialog.exec()

    def _import_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择电子书文件", "",
            "电子书 (*.epub *.mobi *.pdf);;所有文件 (*)"
        )
        if files:
            self._parse_and_add(files)

    def _import_directory(self):
        d = QFileDialog.getExistingDirectory(self, "选择电子书目录")
        if d:
            files = self._scanner.scan_directory(d)
            if files:
                self._parse_and_add(files)

    def _parse_and_add(self, files: list):
        existing_paths = {b.file_path for b in self._books}
        new_files = [f for f in files if f not in existing_paths]
        if not new_files:
            self.statusBar().showMessage("文件已存在于列表中")
            return
        parser = MetadataParser()
        for f in new_files:
            try:
                book = parser.parse(f)
                self._books.append(book)
            except Exception:
                self._books.append(BookMeta(file_path=f, file_format=Path(f).suffix.lstrip("."), title=Path(f).stem))
        self._sync_books_to_shelf_tree()
        self.book_table.load_books(self._books)
        self.statusBar().showMessage(f"已导入 {len(new_files)} 本电子书")

    def _check_calibre(self):
        if self._converter.is_calibre_available:
            QMessageBox.information(self, "Calibre 状态", "✅ Calibre (ebook-convert) 已安装且可用")
        else:
            QMessageBox.warning(
                self, "Calibre 状态",
                "❌ 未检测到 Calibre\n\n格式转换功能需要 Calibre 支持。\n"
                "请从 https://calibre-ebook.com 下载安装，\n"
                "并确保 ebook-convert 在系统 PATH 中。"
            )

    def _show_about(self):
        QMessageBox.about(
            self, "关于",
            "📚 电子书元数据管理器 v2.0\n\n"
            "支持 EPUB/MOBI/PDF 元数据编辑与格式转换\n"
            "多级书架分类管理，支持拖拽批量操作\n"
            "元数据来源: 豆瓣读书、OpenLibrary\n"
            "格式转换依赖: Calibre (ebook-convert)"
        )
