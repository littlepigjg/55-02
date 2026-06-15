import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ebook_manager.shelf_models import (
    ShelfTree, ShelfNode, ShelfStorage, SHELF_ROOT_ID
)
from ebook_manager.models import BookMeta


def test_shelf_tree_basic():
    print("=== 测试1: 基础书架创建和查询 ===")
    tree = ShelfTree()
    assert tree.get_node(SHELF_ROOT_ID) is not None, "根节点必须存在"
    print("✓ 根节点创建成功")

    lit = tree.create_shelf("文学", icon="📖")
    assert lit.id is not None, "书架ID不能为空"
    assert lit.parent_id == SHELF_ROOT_ID, "父节点应为根节点"
    print(f"✓ 创建书架「文学」 ID: {lit.id}")

    chinese = tree.create_shelf("中国当代", parent_id=lit.id, icon="📚")
    mo_yan = tree.create_shelf("莫言作品", parent_id=chinese.id, icon="📕")
    print(f"✓ 创建层级: 文学 / 中国当代 / 莫言作品")

    path = tree.get_full_path(mo_yan.id)
    assert path == "全部书架 / 文学 / 中国当代 / 莫言作品", f"路径错误: {path}"
    print(f"✓ 完整路径: {path}")

    ancestors = tree.get_ancestors(mo_yan.id)
    assert len(ancestors) == 3, f"祖先数量应为3: {len(ancestors)}"
    print(f"✓ 祖先数量: {len(ancestors)}")

    children = tree.get_children(lit.id)
    assert len(children) == 1, f"子节点数量应为1: {len(children)}"
    assert children[0].name == "中国当代"
    print("✓ 子节点查询正确")

    descendants = tree.get_descendant_ids(lit.id)
    assert chinese.id in descendants, "中国当代应是文学的后代"
    assert mo_yan.id in descendants, "莫言作品应是文学的后代"
    assert len(descendants) == 2
    print(f"✓ 后代查询正确: {len(descendants)} 个后代")

    assert tree.is_descendant(lit.id, mo_yan.id) == True
    assert tree.is_descendant(mo_yan.id, lit.id) == False
    assert tree.is_descendant(lit.id, lit.id) == True
    print("✓ 后代关系判断正确")

    return tree, lit, chinese, mo_yan


def test_book_operations():
    print("\n=== 测试2: 书籍添加和移动 ===")
    tree = ShelfTree()
    lit = tree.create_shelf("文学")
    chinese = tree.create_shelf("中国当代", parent_id=lit.id)

    books = []
    for i in range(5):
        book = BookMeta(
            title=f"书籍{i+1}",
            author=f"作者{i+1}",
            file_path=f"/path/book{i+1}.epub",
            file_format="epub",
            file_size=1024 * 100 * (i + 1)
        )
        books.append(book)

    for b in books[:3]:
        tree.add_book(lit.id, b.book_id)

    lit_node = tree.get_node(lit.id)
    assert lit_node.book_count == 3, f"书籍数量应为3: {lit_node.book_count}"
    assert tree.get_total_books() == 3, f"总书数应为3: {tree.get_total_books()}"
    print(f"✓ 文学书架添加3本: book_count={lit_node.book_count}, 总计={tree.get_total_books()}")

    for b in books[3:]:
        tree.add_book(chinese.id, b.book_id)

    chinese_node = tree.get_node(chinese.id)
    assert chinese_node.book_count == 2
    assert tree.get_total_books() == 5, f"总书数应为5: {tree.get_total_books()}"
    print(f"✓ 中国当代添加2本: book_count={chinese_node.book_count}, 总计={tree.get_total_books()}")

    direct = tree.get_books_in_shelf(lit.id, recursive=False)
    all_books = tree.get_books_in_shelf(lit.id, recursive=True)
    assert len(direct) == 3, f"直接书籍应为3: {len(direct)}"
    assert len(all_books) == 5, f"递归书籍应为5: {len(all_books)}"
    print(f"✓ 非递归查询: {len(direct)}本, 递归查询: {len(all_books)}本")

    moved = tree.batch_move_books([books[0].book_id, books[1].book_id], lit.id, chinese.id, copy=False)
    assert moved == 2
    print(f"✓ 批量移动2本: 文学 → 中国当代")

    lit_node = tree.get_node(lit.id)
    chinese_node = tree.get_node(chinese.id)
    assert lit_node.book_count == 1, f"文学剩余1本: {lit_node.book_count}"
    assert chinese_node.book_count == 4, f"中国当代应有4本: {chinese_node.book_count}"
    assert tree.get_total_books() == 5, f"总数仍应5: {tree.get_total_books()}"
    print(f"✓ 移动后: 文学={lit_node.book_count}, 中国当代={chinese_node.book_count}, 总={tree.get_total_books()}")

    copied = tree.move_book(books[4].book_id, chinese.id, lit.id, copy=True)
    assert copied == True
    lit_node = tree.get_node(lit.id)
    chinese_node = tree.get_node(chinese.id)
    assert lit_node.book_count == 2, f"文学应2本: {lit_node.book_count}"
    assert chinese_node.book_count == 4, f"中国当代应4本: {chinese_node.book_count}"
    assert tree.get_total_books() == 5, f"复制后唯一书籍总数仍5: {tree.get_total_books()}"
    print(f"✓ 复制1本后: 文学={lit_node.book_count}, 中国当代={chinese_node.book_count}, 唯一书={tree.get_total_books()}")

    shelves = tree.find_book_shelves(books[4].book_id)
    assert len(shelves) == 2, f"书籍5应在2个书架中: {len(shelves)}"
    print(f"✓ 书籍5所在书架数: {len(shelves)}")

    lit_recursive = tree.get_recursive_book_count(lit.id)
    assert lit_recursive == 5, f"文学(含子书架)唯一书数应5: {lit_recursive}"
    total_refs = lit_node.book_count + chinese_node.book_count
    assert total_refs == 6, f"总关联引用数应6: {total_refs}"
    print(f"✓ 文学(含后代)唯一书籍: {lit_recursive}, 总关联引用: {total_refs}")

    return tree


def test_shelf_move_delete():
    print("\n=== 测试3: 书架移动和删除 ===")
    tree = ShelfTree()
    lit = tree.create_shelf("文学")
    sci = tree.create_shelf("科技")
    chinese = tree.create_shelf("中国当代", parent_id=lit.id)
    mo_yan = tree.create_shelf("莫言作品", parent_id=chinese.id)

    book1 = BookMeta(title="红高粱", author="莫言", file_path="/path/hgl.epub")
    book2 = BookMeta(title="蛙", author="莫言", file_path="/path/wa.epub")
    tree.add_book(mo_yan.id, book1.book_id)
    tree.add_book(mo_yan.id, book2.book_id)

    before = tree.get_full_path(mo_yan.id)
    ok = tree.move_shelf(chinese.id, sci.id)
    assert ok == True, "移动书架失败"
    after = tree.get_full_path(mo_yan.id)
    print(f"✓ 移动前: {before}")
    print(f"✓ 移动后: {after}")
    assert "科技" in after, "路径应包含科技"

    ok = tree.move_shelf(sci.id, mo_yan.id)
    assert ok == False, "不能移入自己的后代"
    print("✓ 正确拒绝移入后代")

    mo_node = tree.get_node(mo_yan.id)
    assert mo_node.book_count == 2
    removed = tree.delete_shelf(chinese.id)
    total_removed = sum(len(v) for v in removed.values())
    assert total_removed == 2, f"删除后应返回2本书ID: {total_removed}"
    assert mo_yan.id in removed, "莫言作品应在删除列表中"
    assert chinese.id in removed, "中国当代应在删除列表中"
    print(f"✓ 删除中国当代(含子书架), 返回 {total_removed} 本书")

    assert tree.get_node(chinese.id) is None, "中国当代应已删除"
    assert tree.get_node(mo_yan.id) is None, "莫言作品应已删除"
    print("✓ 确认节点已删除")

    assert tree.get_total_books() == 0, f"删除后总数应归零: {tree.get_total_books()}"
    print(f"✓ 总书籍计数已归零")

    return tree


def test_persistence():
    print("\n=== 测试4: 持久化存储 ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = ShelfStorage(tmpdir)

        tree = storage.load()
        lit = tree.create_shelf("测试文学", icon="📖")
        sci = tree.create_shelf("测试科技", icon="🔬")
        sub = tree.create_shelf("子分类", parent_id=lit.id)
        tree.set_shelf_color(lit.id, "#e74c3c")
        tree.set_expanded(lit.id, True)
        tree.set_expanded(sub.id, True)

        book = BookMeta(title="测试书", file_path="/path/test.epub")
        tree.add_book(lit.id, book.book_id)

        storage.mark_dirty()
        storage.save(tree, force=True)

        print("✓ 已保存到磁盘")

        storage2 = ShelfStorage(tmpdir)
        loaded_tree = storage2.load()

        lit_loaded = loaded_tree.find_by_path("全部书架 / 测试文学")
        assert lit_loaded is not None, "加载失败"
        assert lit_loaded.name == "测试文学"
        assert lit_loaded.icon == "📖"
        assert lit_loaded.color == "#e74c3c"
        assert lit_loaded.expanded == True
        assert lit_loaded.book_count == 1
        print("✓ 文学书架属性加载正确")

        sub_loaded = loaded_tree.find_by_path("全部书架 / 测试文学 / 子分类")
        assert sub_loaded is not None
        assert sub_loaded.expanded == True
        assert sub_loaded.parent_id == lit_loaded.id
        print("✓ 子书架加载正确")

        sci_loaded = loaded_tree.find_by_path("全部书架 / 测试科技")
        assert sci_loaded is not None
        assert sci_loaded.icon == "🔬"
        print("✓ 科技书架加载正确")

        books = loaded_tree.get_books_in_shelf(lit_loaded.id)
        assert len(books) == 1
        assert books[0] == book.book_id
        print("✓ 书籍关联加载正确")

        assert loaded_tree.validate_structure() == True
        print("✓ 结构验证通过")

        path = loaded_tree.get_full_path(sub_loaded.id)
        assert path == "全部书架 / 测试文学 / 子分类"
        print(f"✓ 路径重建正确: {path}")

    return tree


def test_rename_and_performance():
    print("\n=== 测试5: 重命名和大规模性能 ===")
    tree = ShelfTree()

    parent = SHELF_ROOT_ID
    nodes = []
    for i in range(10):
        node = tree.create_shelf(f"层级{i}", parent_id=parent)
        nodes.append(node)
        parent = node.id

    deep_node = nodes[-1]
    path = tree.get_full_path(deep_node.id)
    parts = tree.get_path_parts(deep_node.id)
    assert len(parts) == 11, f"路径段数应为11: {len(parts)}"
    print(f"✓ 10层深度嵌套创建成功, 路径: {path}")

    import time
    start = time.time()
    for i in range(1000):
        b = BookMeta(title=f"书{i}", file_path=f"/p/{i}.epub")
        target = nodes[i % len(nodes)].id
        tree.add_book(target, b.book_id)
    elapsed = time.time() - start
    print(f"✓ 1000本书添加耗时: {elapsed:.3f}s")

    start = time.time()
    count = 0
    for _ in range(100):
        desc = tree.get_descendant_ids(SHELF_ROOT_ID)
        count += len(desc)
    elapsed = time.time() - start
    print(f"✓ 100次后代查询耗时: {elapsed:.3f}s (总节点数{count/100})")

    start = time.time()
    for node in nodes:
        tree.is_descendant(nodes[0].id, node.id)
    elapsed = time.time() - start
    print(f"✓ 后代关系判断(路径前缀法): {elapsed:.6f}s/10次")

    tree.rename_shelf(nodes[5].id, "重命名层")
    new_path = tree.get_full_path(deep_node.id)
    assert "重命名层" in new_path, f"重命名应级联更新路径: {new_path}"
    print(f"✓ 重命名级联路径更新: {new_path}")

    data = tree.to_dict()
    restored = ShelfTree.from_dict(data)
    assert restored.validate_structure(), "序列化后结构验证失败"
    restored_path = restored.get_full_path(deep_node.id)
    assert restored_path == new_path, f"序列化路径不匹配: {restored_path}"
    print(f"✓ 序列化/反序列化正确")

    return tree


def test_book_model_extension():
    print("\n=== 测试6: 书籍模型扩展 ===")
    b1 = BookMeta(title="测试1", file_path="/a/b/book1.epub")
    b2 = BookMeta(title="测试2", file_path="/a/b/book1.epub")

    assert b1.book_id == b2.book_id, "同路径应生成相同ID"
    print(f"✓ 基于路径的ID生成一致: {b1.book_id}")

    b3 = BookMeta(title="测试3", file_path="/c/d/book3.pdf")
    assert b3.book_id != b1.book_id, "不同路径应生成不同ID"
    print(f"✓ 不同路径的ID不同")

    b1.add_to_shelf("shelf1")
    b1.add_to_shelf("shelf2")
    b1.add_to_shelf("shelf1")
    assert len(b1.shelf_ids) == 2, "去重添加"
    assert b1.is_in_shelf("shelf1") == True
    assert b1.is_in_shelf("shelf99") == False
    print("✓ 书架关联方法工作正常")

    b1.remove_from_shelf("shelf1")
    assert len(b1.shelf_ids) == 1
    print("✓ 移除书架工作正常")

    d = b1.to_dict()
    restored = BookMeta.from_dict(d)
    assert restored.book_id == b1.book_id
    assert restored.shelf_ids == ["shelf2"]
    print("✓ 序列化/反序列化完整保留所有字段")

    return b1


def run_all_tests():
    print("=" * 60)
    print("多级书架管理系统 - 核心逻辑测试")
    print("=" * 60)

    all_passed = True
    tests = [
        test_shelf_tree_basic,
        test_book_operations,
        test_shelf_move_delete,
        test_persistence,
        test_rename_and_performance,
        test_book_model_extension,
    ]

    for test_fn in tests:
        try:
            test_fn()
        except AssertionError as e:
            print(f"\n❌ 测试失败 [{test_fn.__name__}]: {e}")
            all_passed = False
            import traceback
            traceback.print_exc()
        except Exception as e:
            print(f"\n❌ 测试异常 [{test_fn.__name__}]: {e}")
            all_passed = False
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有测试通过！")
    else:
        print("❌ 部分测试失败！")
    print("=" * 60)
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
