import uuid
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


def _generate_book_id(file_path: str = "") -> str:
    if file_path:
        hash_obj = hashlib.md5(file_path.encode("utf-8"))
        return f"book_{hash_obj.hexdigest()[:16]}"
    return f"book_{uuid.uuid4().hex[:16]}"


@dataclass
class BookMeta:
    title: str = ""
    author: str = ""
    publisher: str = ""
    publish_date: str = ""
    isbn: str = ""
    language: str = ""
    description: str = ""
    tags: list = field(default_factory=list)
    cover_path: Optional[str] = None
    file_path: str = ""
    file_format: str = ""
    file_size: int = 0
    book_id: str = ""
    shelf_ids: list = field(default_factory=list)

    def __post_init__(self):
        if not self.book_id:
            self.book_id = _generate_book_id(self.file_path)

    def to_dict(self):
        return {
            "title": self.title,
            "author": self.author,
            "publisher": self.publisher,
            "publish_date": self.publish_date,
            "isbn": self.isbn,
            "language": self.language,
            "description": self.description,
            "tags": self.tags,
            "cover_path": self.cover_path,
            "file_path": self.file_path,
            "file_format": self.file_format,
            "file_size": self.file_size,
            "book_id": self.book_id,
            "shelf_ids": self.shelf_ids,
        }

    @classmethod
    def from_dict(cls, d: dict):
        obj = cls(
            title=d.get("title", ""),
            author=d.get("author", ""),
            publisher=d.get("publisher", ""),
            publish_date=d.get("publish_date", ""),
            isbn=d.get("isbn", ""),
            language=d.get("language", ""),
            description=d.get("description", ""),
            tags=d.get("tags", []),
            cover_path=d.get("cover_path"),
            file_path=d.get("file_path", ""),
            file_format=d.get("file_format", ""),
            file_size=d.get("file_size", 0),
            book_id=d.get("book_id", ""),
            shelf_ids=d.get("shelf_ids", []),
        )
        if not obj.book_id:
            obj.book_id = _generate_book_id(obj.file_path)
        return obj

    @staticmethod
    def format_size(size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def add_to_shelf(self, shelf_id: str):
        if shelf_id not in self.shelf_ids:
            self.shelf_ids.append(shelf_id)

    def remove_from_shelf(self, shelf_id: str):
        if shelf_id in self.shelf_ids:
            self.shelf_ids.remove(shelf_id)

    def is_in_shelf(self, shelf_id: str) -> bool:
        return shelf_id in self.shelf_ids
