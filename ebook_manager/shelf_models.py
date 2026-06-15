import json
import os
import uuid
import copy
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set
from pathlib import Path


SHELF_ROOT_ID = "root"
PATH_SEPARATOR = "/"
BOOK_MIME = "application/x-ebook-book"
SHELF_MIME = "application/x-ebook-shelf"
MOVE_ACTION = "application/x-ebook-action-move"
COPY_ACTION = "application/x-ebook-action-copy"


@dataclass
class ShelfNode:
    id: str
    name: str
    parent_id: Optional[str] = None
    path: str = ""
    sort_order: int = 0
    icon: str = "📁"
    color: str = ""
    expanded: bool = False
    book_count: int = 0
    book_ids: List[str] = field(default_factory=list)
    children_ids: List[str] = field(default_factory=list)
    is_virtual: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "path": self.path,
            "sort_order": self.sort_order,
            "icon": self.icon,
            "color": self.color,
            "expanded": self.expanded,
            "book_count": self.book_count,
            "book_ids": self.book_ids,
            "children_ids": self.children_ids,
            "is_virtual": self.is_virtual,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ShelfNode":
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            parent_id=d.get("parent_id"),
            path=d.get("path", ""),
            sort_order=d.get("sort_order", 0),
            icon=d.get("icon", "📁"),
            color=d.get("color", ""),
            expanded=d.get("expanded", False),
            book_count=d.get("book_count", 0),
            book_ids=d.get("book_ids", []),
            children_ids=d.get("children_ids", []),
            is_virtual=d.get("is_virtual", False),
        )


class ShelfTree:
    def __init__(self):
        self._nodes: Dict[str, ShelfNode] = {}
        self._children_index: Dict[str, List[str]] = {}
        self._path_index: Dict[str, str] = {}
        self._init_root()

    def _init_root(self):
        root = ShelfNode(
            id=SHELF_ROOT_ID,
            name="全部书架",
            parent_id=None,
            path=SHELF_ROOT_ID,
            sort_order=0,
            icon="🏠",
            expanded=True,
            is_virtual=True,
        )
        self._nodes[SHELF_ROOT_ID] = root
        self._children_index[SHELF_ROOT_ID] = []
        self._path_index[SHELF_ROOT_ID] = SHELF_ROOT_ID

    def _generate_id(self) -> str:
        return f"shelf_{uuid.uuid4().hex[:12]}"

    def _build_path(self, node_id: str, parent_id: Optional[str]) -> str:
        if parent_id is None:
            return node_id
        parent_path = self._nodes[parent_id].path
        return f"{parent_path}{PATH_SEPARATOR}{node_id}"

    def _rebuild_subtree_paths(self, node_id: str, new_parent_path: str):
        node = self._nodes[node_id]
        old_path = node.path
        new_path = f"{new_parent_path}{PATH_SEPARATOR}{node_id}"
        node.path = new_path
        self._path_index[node_id] = new_path
        for child_id in node.children_ids:
            self._rebuild_subtree_paths(child_id, new_path)
        return old_path

    def _update_descendant_total_count(self, shelf_id: str, delta: int):
        pass

    def _get_leaf_ids(self, node_id: str) -> List[str]:
        result = []
        stack = [node_id]
        while stack:
            nid = stack.pop()
            node = self._nodes[nid]
            if not node.children_ids:
                result.append(nid)
            else:
                stack.extend(reversed(node.children_ids))
        return result

    def get_node(self, node_id: str) -> Optional[ShelfNode]:
        return self._nodes.get(node_id)

    def get_children(self, parent_id: Optional[str]) -> List[ShelfNode]:
        pid = parent_id if parent_id is not None else SHELF_ROOT_ID
        child_ids = self._children_index.get(pid, [])
        return [self._nodes[cid] for cid in sorted(
            child_ids, key=lambda x: (self._nodes[x].sort_order, self._nodes[x].name)
        )]

    def get_parent(self, node_id: str) -> Optional[ShelfNode]:
        node = self._nodes.get(node_id)
        if not node or node.parent_id is None:
            return None
        return self._nodes.get(node.parent_id)

    def get_ancestors(self, node_id: str) -> List[ShelfNode]:
        result = []
        current_id = self._nodes[node_id].parent_id
        while current_id is not None:
            result.append(self._nodes[current_id])
            current_id = self._nodes[current_id].parent_id
        return list(reversed(result))

    def get_descendant_ids(self, node_id: str) -> Set[str]:
        result: Set[str] = set()
        stack = list(self._nodes[node_id].children_ids)
        while stack:
            nid = stack.pop()
            result.add(nid)
            stack.extend(self._nodes[nid].children_ids)
        return result

    def is_descendant(self, ancestor_id: str, descendant_id: str) -> bool:
        if ancestor_id == descendant_id:
            return True
        desc_path = self._nodes[descendant_id].path
        anc_path = self._nodes[ancestor_id].path
        return desc_path.startswith(f"{anc_path}{PATH_SEPARATOR}")

    def get_path_parts(self, node_id: str) -> List[str]:
        parts = self._nodes[node_id].path.split(PATH_SEPARATOR)
        return [self._nodes[p].name for p in parts]

    def get_full_path(self, node_id: str) -> str:
        return " / ".join(self.get_path_parts(node_id))

    def find_by_path(self, path_str: str) -> Optional[ShelfNode]:
        parts = path_str.split(" / ")
        current_id = SHELF_ROOT_ID
        for part in parts[1:]:
            found = None
            for cid in self._children_index.get(current_id, []):
                if self._nodes[cid].name == part:
                    found = cid
                    break
            if found is None:
                return None
            current_id = found
        return self._nodes.get(current_id)

    def _sync_children_ids(self, parent_id: str):
        if parent_id in self._nodes and parent_id in self._children_index:
            self._nodes[parent_id].children_ids = list(self._children_index[parent_id])

    def create_shelf(self, name: str, parent_id: Optional[str] = None,
                     icon: str = "📁", color: str = "") -> ShelfNode:
        pid = parent_id if parent_id is not None else SHELF_ROOT_ID
        if pid not in self._nodes:
            raise ValueError(f"Parent shelf not found: {pid}")
        new_id = self._generate_id()
        path = self._build_path(new_id, pid)
        siblings = self._children_index.get(pid, [])
        sort_order = max(
            [self._nodes[s].sort_order for s in siblings], default=-1
        ) + 1
        node = ShelfNode(
            id=new_id,
            name=name,
            parent_id=pid,
            path=path,
            sort_order=sort_order,
            icon=icon,
            color=color,
        )
        self._nodes[new_id] = node
        self._children_index[new_id] = []
        self._path_index[new_id] = path
        if pid not in self._children_index:
            self._children_index[pid] = []
        self._children_index[pid].append(new_id)
        self._sync_children_ids(pid)
        self._sync_children_ids(new_id)
        return node

    def rename_shelf(self, shelf_id: str, new_name: str) -> bool:
        if shelf_id not in self._nodes:
            return False
        if shelf_id == SHELF_ROOT_ID:
            return False
        self._nodes[shelf_id].name = new_name
        return True

    def move_shelf(self, shelf_id: str, new_parent_id: str,
                   insert_index: int = -1) -> bool:
        if shelf_id == SHELF_ROOT_ID:
            return False
        if shelf_id not in self._nodes:
            return False
        if new_parent_id not in self._nodes:
            return False
        if self.is_descendant(shelf_id, new_parent_id):
            return False
        node = self._nodes[shelf_id]
        old_parent_id = node.parent_id
        if old_parent_id == new_parent_id and insert_index == -1:
            return True
        if old_parent_id is not None:
            self._children_index[old_parent_id].remove(shelf_id)
            self._sync_children_ids(old_parent_id)
        node.parent_id = new_parent_id
        old_path = node.path
        new_parent_path = self._nodes[new_parent_id].path
        self._rebuild_subtree_paths(shelf_id, new_parent_path)
        siblings = self._children_index.setdefault(new_parent_id, [])
        if 0 <= insert_index < len(siblings):
            siblings.insert(insert_index, shelf_id)
        else:
            siblings.append(shelf_id)
        for i, cid in enumerate(siblings):
            self._nodes[cid].sort_order = i
        self._sync_children_ids(new_parent_id)
        return True

    def reorder_siblings(self, parent_id: str, ordered_ids: List[str]):
        pid = parent_id if parent_id is not None else SHELF_ROOT_ID
        if pid not in self._children_index:
            return
        self._children_index[pid] = list(ordered_ids)
        for i, cid in enumerate(ordered_ids):
            if cid in self._nodes:
                self._nodes[cid].sort_order = i
        self._sync_children_ids(pid)

    def delete_shelf(self, shelf_id: str) -> Dict[str, List[str]]:
        if shelf_id == SHELF_ROOT_ID:
            return {}
        if shelf_id not in self._nodes:
            return {}
        all_book_ids: Dict[str, List[str]] = {}
        to_delete: List[str] = [shelf_id]
        stack = list(self._children_index.get(shelf_id, []))
        while stack:
            nid = stack.pop()
            to_delete.append(nid)
            stack.extend(self._children_index.get(nid, []))
        for nid in to_delete:
            node = self._nodes[nid]
            all_book_ids[nid] = list(node.book_ids)
        parent_id = None
        if shelf_id in self._nodes and self._nodes[shelf_id].parent_id:
            parent_id = self._nodes[shelf_id].parent_id
            if parent_id in self._children_index:
                self._children_index[parent_id].remove(shelf_id)
                self._sync_children_ids(parent_id)
        for nid in to_delete:
            del self._nodes[nid]
            if nid in self._children_index:
                del self._children_index[nid]
            if nid in self._path_index:
                del self._path_index[nid]
        return all_book_ids

    def set_shelf_icon(self, shelf_id: str, icon: str) -> bool:
        if shelf_id in self._nodes:
            self._nodes[shelf_id].icon = icon
            return True
        return False

    def set_shelf_color(self, shelf_id: str, color: str) -> bool:
        if shelf_id in self._nodes:
            self._nodes[shelf_id].color = color
            return True
        return False

    def set_expanded(self, shelf_id: str, expanded: bool):
        if shelf_id in self._nodes:
            self._nodes[shelf_id].expanded = expanded

    def get_expanded_ids(self) -> Set[str]:
        return {nid for nid, n in self._nodes.items() if n.expanded}

    def add_book(self, shelf_id: str, book_id: str) -> bool:
        if shelf_id not in self._nodes:
            return False
        if book_id in self._nodes[shelf_id].book_ids:
            return False
        self._nodes[shelf_id].book_ids.append(book_id)
        self._nodes[shelf_id].book_count = len(self._nodes[shelf_id].book_ids)
        return True

    def remove_book(self, shelf_id: str, book_id: str) -> bool:
        if shelf_id not in self._nodes:
            return False
        if book_id not in self._nodes[shelf_id].book_ids:
            return False
        self._nodes[shelf_id].book_ids.remove(book_id)
        self._nodes[shelf_id].book_count = len(self._nodes[shelf_id].book_ids)
        return True

    def move_book(self, book_id: str, from_shelf_id: str,
                  to_shelf_id: str, copy: bool = False) -> bool:
        if to_shelf_id not in self._nodes:
            return False
        if from_shelf_id != SHELF_ROOT_ID and from_shelf_id in self._nodes:
            if book_id not in self._nodes[from_shelf_id].book_ids:
                return False
        if book_id in self._nodes[to_shelf_id].book_ids:
            return False
        self._nodes[to_shelf_id].book_ids.append(book_id)
        self._nodes[to_shelf_id].book_count = len(self._nodes[to_shelf_id].book_ids)
        if not copy and from_shelf_id != SHELF_ROOT_ID and from_shelf_id in self._nodes:
            self._nodes[from_shelf_id].book_ids.remove(book_id)
            self._nodes[from_shelf_id].book_count = len(self._nodes[from_shelf_id].book_ids)
        return True

    def batch_move_books(self, book_ids: List[str], from_shelf_id: str,
                         to_shelf_id: str, copy: bool = False) -> int:
        count = 0
        for bid in book_ids:
            if self.move_book(bid, from_shelf_id, to_shelf_id, copy):
                count += 1
        return count

    def get_books_in_shelf(self, shelf_id: str, recursive: bool = False) -> List[str]:
        if shelf_id not in self._nodes:
            return []
        result = list(self._nodes[shelf_id].book_ids)
        if recursive:
            stack = list(self._children_index.get(shelf_id, []))
            while stack:
                nid = stack.pop()
                result.extend(self._nodes[nid].book_ids)
                stack.extend(self._children_index.get(nid, []))
        return result

    def find_book_shelves(self, book_id: str) -> List[str]:
        return [nid for nid, n in self._nodes.items() if book_id in n.book_ids]

    def get_all_shelf_ids(self) -> List[str]:
        return [nid for nid in self._nodes.keys() if nid != SHELF_ROOT_ID]

    def get_shelf_count(self) -> int:
        return len(self._nodes) - 1

    def get_total_books(self) -> int:
        unique_books: Set[str] = set()
        for nid in list(self._nodes.keys()):
            unique_books.update(self._nodes[nid].book_ids)
        return len(unique_books)

    def get_recursive_book_count(self, shelf_id: str) -> int:
        if shelf_id not in self._nodes:
            return 0
        unique: Set[str] = set()
        unique.update(self._nodes[shelf_id].book_ids)
        stack = list(self._children_index.get(shelf_id, []))
        while stack:
            nid = stack.pop()
            unique.update(self._nodes[nid].book_ids)
            stack.extend(self._children_index.get(nid, []))
        return len(unique)

    def validate_structure(self) -> bool:
        for nid, node in self._nodes.items():
            if nid != SHELF_ROOT_ID:
                if node.parent_id is None:
                    return False
                if node.parent_id not in self._nodes:
                    return False
                if nid not in self._children_index.get(node.parent_id, []):
                    return False
            expected_path = self._build_path(nid, node.parent_id)
            if expected_path != node.path:
                return False
        return True

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "nodes": {nid: n.to_dict() for nid, n in self._nodes.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ShelfTree":
        tree = cls()
        tree._nodes.clear()
        tree._children_index.clear()
        tree._path_index.clear()
        nodes_data = d.get("nodes", {})
        for nid, nd in nodes_data.items():
            node = ShelfNode.from_dict(nd)
            tree._nodes[nid] = node
            tree._children_index[nid] = list(node.children_ids)
            tree._path_index[nid] = node.path
        return tree


class ShelfStorage:
    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir is None:
            home = Path.home()
            storage_dir = str(home / ".ebook_manager")
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._shelves_file = self._storage_dir / "shelves.json"
        self._dirty = False

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self):
        self._dirty = True

    def load(self) -> ShelfTree:
        if not self._shelves_file.exists():
            tree = ShelfTree()
            self._create_default_shelves(tree)
            return tree
        try:
            with open(self._shelves_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            tree = ShelfTree.from_dict(data)
            if not tree.validate_structure():
                tree = ShelfTree()
                self._create_default_shelves(tree)
            return tree
        except (json.JSONDecodeError, KeyError, Exception):
            tree = ShelfTree()
            self._create_default_shelves(tree)
            return tree

    def save(self, tree: ShelfTree, force: bool = False):
        if not self._dirty and not force:
            return
        data = tree.to_dict()
        tmp_file = self._shelves_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_file.replace(self._shelves_file)
        self._dirty = False

    def save_incremental(self, tree: ShelfTree, changed_ids: Optional[Set[str]] = None):
        self.save(tree, force=True)

    def _create_default_shelves(self, tree: ShelfTree):
        lit = tree.create_shelf("文学", icon="📖")
        tree.create_shelf("中国当代", parent_id=lit.id, icon="📚")
        tree.create_shelf("外国文学", parent_id=lit.id, icon="📕")
        sci = tree.create_shelf("科技", icon="🔬")
        tree.create_shelf("计算机", parent_id=sci.id, icon="💻")
        tree.create_shelf("数学", parent_id=sci.id, icon="📐")
        tree.create_shelf("历史", icon="🏛️")
        tree.create_shelf("哲学", icon="🧠")
        tree.create_shelf("艺术", icon="🎨")
        tree.set_expanded(SHELF_ROOT_ID, True)
