"""
书架系统拖拽刷新功能测试

测试内容：
1. 书籍添加 - 书架计数是否正确更新
2. 书籍移动 - 源/目标书架计数是否正确
3. 书籍复制 - 源不变、目标增加
4. 递归计数 - 父书架是否包含子书架书籍
5. 模型刷新 - notify_books_changed 是否触发正确节点刷新
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ebook_manager.shelf_models import (
    ShelfTree, ShelfNode, ShelfStorage, SHELF_ROOT_ID
)
from ebook_manager.models import BookMeta


class TestBookCountFreshness(unittest.TestCase):
    """测试书架书籍计数的即时性"""

    def setUp(self):
        self.tree = ShelfTree()
        self.lit = self.tree.create_shelf("文学", icon="📖")
        self.chinese = self.tree.create_shelf("中国当代", parent_id=self.lit.id, icon="📚")
        self.mo_yan = self.tree.create_shelf("莫言作品", parent_id=self.chinese.id, icon="📕")
        self.foreign = self.tree.create_shelf("外国文学", parent_id=self.lit.id, icon="📗")
        self.books = []
        for i in range(10):
            b = BookMeta(
                title=f"书籍{i+1}",
                author=f"作者{i+1}",
                file_path=f"/path/book{i+1}.epub",
                file_format="epub",
                file_size=1024 * 100 * (i + 1)
            )
            self.books.append(b)

    def test_add_book_instant_count(self):
        """添加书籍后，书架计数立即反映"""
        self.assertEqual(self.tree.get_node(self.lit.id).book_count, 0)
        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 0)

        self.tree.add_book(self.lit.id, self.books[0].book_id)
        self.assertEqual(self.tree.get_node(self.lit.id).book_count, 1,
                         "直接添加后，直接计数应为1")
        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 1,
                         "直接添加后，递归计数应为1")

        self.tree.add_book(self.chinese.id, self.books[1].book_id)
        self.assertEqual(self.tree.get_node(self.chinese.id).book_count, 1,
                         "子书架直接计数应为1")
        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 2,
                         "父书架递归计数应包含子书架")

        self.tree.add_book(self.mo_yan.id, self.books[2].book_id)
        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 3,
                         "孙辈添加后，祖父递归计数应增加")
        self.assertEqual(self.tree.get_recursive_book_count(self.chinese.id), 2,
                         "子书架递归计数应包含孙辈")

    def test_remove_book_instant_count(self):
        """移除书籍后，书架计数立即反映"""
        self.tree.add_book(self.lit.id, self.books[0].book_id)
        self.tree.add_book(self.lit.id, self.books[1].book_id)
        self.tree.add_book(self.chinese.id, self.books[2].book_id)

        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 3)

        self.tree.remove_book(self.lit.id, self.books[0].book_id)
        self.assertEqual(self.tree.get_node(self.lit.id).book_count, 1,
                         "直接移除后，直接计数应减1")
        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 2,
                         "直接移除后，递归计数应减1")

        self.tree.remove_book(self.chinese.id, self.books[2].book_id)
        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 1,
                         "子书架移除后，父递归计数应减1")

    def test_move_book_instant_count(self):
        """移动书籍后，源和目标计数都正确更新"""
        self.tree.add_book(self.lit.id, self.books[0].book_id)
        self.tree.add_book(self.lit.id, self.books[1].book_id)

        self.tree.move_book(self.books[0].book_id, self.lit.id, self.chinese.id, copy=False)

        self.assertEqual(self.tree.get_node(self.lit.id).book_count, 1,
                         "源书架直接计数应减1")
        self.assertEqual(self.tree.get_node(self.chinese.id).book_count, 1,
                         "目标书架直接计数应加1")
        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 2,
                         "父书架递归计数不变（书还在子树中）")
        self.assertEqual(self.tree.get_total_books(), 2,
                         "总书数不变")

    def test_copy_book_instant_count(self):
        """复制书籍后，源不变、目标增加、总数增加"""
        self.tree.add_book(self.lit.id, self.books[0].book_id)

        self.tree.move_book(self.books[0].book_id, self.lit.id, self.chinese.id, copy=True)

        self.assertEqual(self.tree.get_node(self.lit.id).book_count, 1,
                         "复制时源书架计数不变")
        self.assertEqual(self.tree.get_node(self.chinese.id).book_count, 1,
                         "复制时目标书架计数加1")
        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 1,
                         "父书架递归计数（去重）不变")
        self.assertEqual(self.tree.get_total_books(), 1,
                         "唯一书籍总数不变（同一本书）")

    def test_batch_move_books(self):
        """批量移动书籍计数正确"""
        for i in range(5):
            self.tree.add_book(self.lit.id, self.books[i].book_id)

        book_ids = [b.book_id for b in self.books[:3]]
        moved = self.tree.batch_move_books(book_ids, self.lit.id, self.chinese.id, copy=False)
        self.assertEqual(moved, 3)

        self.assertEqual(self.tree.get_node(self.lit.id).book_count, 2)
        self.assertEqual(self.tree.get_node(self.chinese.id).book_count, 3)
        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 5)
        self.assertEqual(self.tree.get_total_books(), 5)

    def test_batch_copy_books(self):
        """批量复制书籍计数正确"""
        for i in range(3):
            self.tree.add_book(self.lit.id, self.books[i].book_id)

        book_ids = [b.book_id for b in self.books[:3]]
        copied = self.tree.batch_move_books(book_ids, self.lit.id, self.foreign.id, copy=True)
        self.assertEqual(copied, 3)

        self.assertEqual(self.tree.get_node(self.lit.id).book_count, 3)
        self.assertEqual(self.tree.get_node(self.foreign.id).book_count, 3)
        self.assertEqual(self.tree.get_total_books(), 3,
                         "复制不会增加唯一书籍总数")
        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 3)

    def test_deep_nesting_recursive_count(self):
        """深层嵌套书架的递归计数正确"""
        current_parent = self.lit.id
        for i in range(5):
            node = self.tree.create_shelf(f"层{i}", parent_id=current_parent)
            current_parent = node.id

        self.tree.add_book(current_parent, self.books[0].book_id)

        self.assertEqual(self.tree.get_node(current_parent).book_count, 1)
        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 1,
                         "顶层递归计数应包含最底层的书")
        self.assertEqual(self.tree.get_recursive_book_count(self.chinese.id), 0)

    def test_rename_does_not_affect_count(self):
        """重命名不影响书籍计数，且子节点显示路径级联更新"""
        self.tree.add_book(self.chinese.id, self.books[0].book_id)
        before_count = self.tree.get_recursive_book_count(self.lit.id)
        before_total = self.tree.get_total_books()

        old_path = self.tree.get_full_path(self.mo_yan.id)
        self.assertIn("中国当代", old_path)

        self.tree.rename_shelf(self.chinese.id, "现当代文学")

        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), before_count)
        self.assertEqual(self.tree.get_total_books(), before_total)

        new_path = self.tree.get_full_path(self.mo_yan.id)
        self.assertIn("现当代文学", new_path,
                      "重命名后，子节点的完整显示路径应级联更新")
        self.assertNotIn("中国当代", new_path,
                         "重命名后，旧名称不应再出现在路径中")
        self.assertTrue(self.tree.validate_structure())

    def test_move_shelf_books_count(self):
        """移动书架时，所有书籍的递归计数随之变化"""
        self.tree.add_book(self.chinese.id, self.books[0].book_id)
        self.tree.add_book(self.mo_yan.id, self.books[1].book_id)
        sci = self.tree.create_shelf("科技")

        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 2)
        self.assertEqual(self.tree.get_recursive_book_count(sci.id), 0)

        self.tree.move_shelf(self.chinese.id, sci.id)

        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 0,
                         "移走子书架后，父递归计数减为0")
        self.assertEqual(self.tree.get_recursive_book_count(sci.id), 2,
                         "新父递归计数增加")
        self.assertEqual(self.tree.get_node(self.chinese.id).book_count, 1)
        self.assertEqual(self.tree.get_total_books(), 2)

    def test_delete_shelf_books_count(self):
        """删除书架后，书籍从计数中移除"""
        self.tree.add_book(self.chinese.id, self.books[0].book_id)
        self.tree.add_book(self.mo_yan.id, self.books[1].book_id)
        self.assertEqual(self.tree.get_total_books(), 2)
        self.assertEqual(self.tree.get_recursive_book_count(self.lit.id), 2)

        removed = self.tree.delete_shelf(self.chinese.id)
        total_removed = sum(len(v) for v in removed.values())

        self.assertEqual(total_removed, 2, "返回所有被删除书架的书籍")
        self.assertEqual(self.tree.get_total_books(), 0,
                         "删除后，总书籍数归零")

    def test_book_shelf_association(self):
        """书籍所在书架查询正确"""
        self.tree.add_book(self.lit.id, self.books[0].book_id)
        self.tree.add_book(self.chinese.id, self.books[0].book_id)

        shelves = self.tree.find_book_shelves(self.books[0].book_id)
        self.assertEqual(len(shelves), 2)
        self.assertIn(self.lit.id, shelves)
        self.assertIn(self.chinese.id, shelves)

    def test_get_books_in_shelf_recursive(self):
        """递归获取书架中的所有书籍"""
        self.tree.add_book(self.lit.id, self.books[0].book_id)
        self.tree.add_book(self.chinese.id, self.books[1].book_id)
        self.tree.add_book(self.mo_yan.id, self.books[2].book_id)
        self.tree.add_book(self.foreign.id, self.books[3].book_id)

        direct = self.tree.get_books_in_shelf(self.lit.id, recursive=False)
        self.assertEqual(len(direct), 1)

        recursive = self.tree.get_books_in_shelf(self.lit.id, recursive=True)
        self.assertEqual(len(recursive), 4)

        chinese_recursive = self.tree.get_books_in_shelf(self.chinese.id, recursive=True)
        self.assertEqual(len(chinese_recursive), 2)


class TestShelfTreeModelRefresh(unittest.TestCase):
    """测试模型刷新机制（需要Qt环境，跳过核心逻辑测试）"""

    def setUp(self):
        try:
            from PyQt6.QtWidgets import QApplication
            from ebook_manager.ui.shelf_tree_model import ShelfTreeModel
            self.QtAvailable = True
            self.app = QApplication.instance() or QApplication(sys.argv)
        except ImportError:
            self.QtAvailable = False
            return

        self.tree = ShelfTree()
        self.lit = self.tree.create_shelf("文学")
        self.chinese = self.tree.create_shelf("中国当代", parent_id=self.lit.id)
        self.model = ShelfTreeModel(self.tree)

    @unittest.skipIf(not hasattr(__import__('builtins'), '_qt_available'), "Qt not available")
    def test_notify_books_changed_data(self):
        """notify_books_changed 触发 dataChanged 信号"""
        if not self.QtAvailable:
            self.skipTest("Qt not available")

        changed = []
        def on_data_changed(top_left, bottom_right, roles):
            changed.append((top_left.row(), bottom_right.row(), roles))

        self.model.dataChanged.connect(on_data_changed)

        self.tree.add_book(self.chinese.id, "book_123")
        self.model.notify_books_changed(source_id=None, target_id=self.chinese.id)

        self.assertGreater(len(changed), 0,
                         "notify_books_changed 应触发 dataChanged 信号")


class TestShelfDragEdgeCases(unittest.TestCase):
    """拖拽边界情况测试"""

    def setUp(self):
        self.tree = ShelfTree()
        self.lit = self.tree.create_shelf("文学")
        self.chinese = self.tree.create_shelf("中国当代", parent_id=self.lit.id)
        self.book = BookMeta(title="测试书", file_path="/test.epub")

    def test_add_same_book_twice(self):
        """同一本书不能重复添加到同一书架"""
        r1 = self.tree.add_book(self.lit.id, self.book.book_id)
        self.assertTrue(r1)
        r2 = self.tree.add_book(self.lit.id, self.book.book_id)
        self.assertFalse(r2)
        self.assertEqual(self.tree.get_node(self.lit.id).book_count, 1)

    def test_move_book_not_in_source(self):
        """源书架没有的书不能移动"""
        r = self.tree.move_book(self.book.book_id, self.lit.id, self.chinese.id)
        self.assertFalse(r)

    def test_move_to_same_shelf(self):
        """移动到同一书架应失败（重复）"""
        self.tree.add_book(self.lit.id, self.book.book_id)
        r = self.tree.move_book(self.book.book_id, self.lit.id, self.lit.id, copy=False)
        self.assertFalse(r)
        self.assertEqual(self.tree.get_node(self.lit.id).book_count, 1)

    def test_copy_to_same_shelf(self):
        """复制到同一书架应失败"""
        self.tree.add_book(self.lit.id, self.book.book_id)
        r = self.tree.move_book(self.book.book_id, self.lit.id, self.lit.id, copy=True)
        self.assertFalse(r)

    def test_remove_nonexistent_book(self):
        """移除不存在的书返回False"""
        r = self.tree.remove_book(self.lit.id, "nonexistent")
        self.assertFalse(r)

    def test_add_to_nonexistent_shelf(self):
        """添加到不存在的书架返回False"""
        r = self.tree.add_book("nonexistent", self.book.book_id)
        self.assertFalse(r)

    def test_root_book_operations(self):
        """根节点上的书籍操作"""
        self.tree.add_book(SHELF_ROOT_ID, self.book.book_id)
        self.assertEqual(self.tree.get_node(SHELF_ROOT_ID).book_count, 1)
        self.assertEqual(self.tree.get_total_books(), 1)

        self.tree.remove_book(SHELF_ROOT_ID, self.book.book_id)
        self.assertEqual(self.tree.get_node(SHELF_ROOT_ID).book_count, 0)
        self.assertEqual(self.tree.get_total_books(), 0)


class TestShelfPersistenceBookCounts(unittest.TestCase):
    """持久化后的书籍计数正确性"""

    def test_save_load_book_counts(self):
        """保存后再加载，书籍计数一致"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ShelfStorage(tmpdir)
            tree = ShelfTree()

            lit = tree.create_shelf("测试文学")
            chinese = tree.create_shelf("测试中国当代", parent_id=lit.id)
            book1 = BookMeta(title="书1", file_path="/a.epub")
            book2 = BookMeta(title="书2", file_path="/b.epub")
            tree.add_book(lit.id, book1.book_id)
            tree.add_book(chinese.id, book2.book_id)

            storage.mark_dirty()
            storage.save(tree, force=True)

            storage2 = ShelfStorage(tmpdir)
            loaded = storage2.load()

            lit_loaded = loaded.find_by_path("全部书架 / 测试文学")
            self.assertIsNotNone(lit_loaded)
            self.assertEqual(lit_loaded.book_count, 1,
                             "直接书籍数加载正确")
            self.assertEqual(loaded.get_recursive_book_count(lit_loaded.id), 2,
                             "递归书籍数加载正确")
            self.assertEqual(loaded.get_total_books(), 2,
                             "总书籍数加载正确")
            self.assertTrue(loaded.validate_structure(),
                            "加载后结构验证通过")

    def test_save_load_expanded_state(self):
        """保存后再加载，展开状态一致"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ShelfStorage(tmpdir)
            tree = storage.load()

            lit = tree.create_shelf("文学")
            chinese = tree.create_shelf("中国当代", parent_id=lit.id)
            tree.set_expanded(lit.id, True)
            tree.set_expanded(chinese.id, True)
            tree.set_expanded(SHELF_ROOT_ID, True)

            storage.mark_dirty()
            storage.save(tree, force=True)

            storage2 = ShelfStorage(tmpdir)
            loaded = storage2.load()

            expanded = loaded.get_expanded_ids()
            self.assertIn(lit.id, expanded, "文学书架应保持展开状态")
            self.assertIn(chinese.id, expanded, "中国当代书架应保持展开状态")


def run_tests():
    print("=" * 60)
    print("书架拖拽刷新功能测试")
    print("=" * 60)
    unittest.main(verbosity=2, exit=False)
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
