from typing import Optional, TYPE_CHECKING
from PyQt6.QtWidgets import QTreeView, QAbstractItemView
from PyQt6.QtCore import Qt, QMimeData, QByteArray, QModelIndex
from PyQt6.QtGui import QDrag

from ...shelf_models import SHELF_ROOT_ID, SHELF_MIME, PATH_SEPARATOR

if TYPE_CHECKING:
    from ..shelf_tree_model import ShelfTreeModel


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
                drag = QDrag(self)
                drag.setMimeData(mime_data)
                drag.exec(Qt.DropAction.MoveAction)

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

    def saveExpandedState(self, model: "ShelfTreeModel"):
        if not hasattr(model, "tree"):
            return
        tree = model.tree
        for nid in tree.get_all_shelf_ids():
            idx = model.find_index(nid)
            if idx.isValid():
                node = tree.get_node(nid)
                if node:
                    node.expanded = self.isExpanded(idx)

    def restoreExpandedState(self, model: "ShelfTreeModel"):
        if not hasattr(model, "tree"):
            return
        tree = model.tree
        for nid in tree.get_all_shelf_ids():
            node = tree.get_node(nid)
            if node and node.expanded:
                idx = model.find_index(nid)
                if idx.isValid():
                    self.expand(idx)
