from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QPushButton, QVBoxLayout, QGridLayout
)
from PyQt6.QtCore import Qt


SHELF_ICONS = [
    "📁", "📂", "📚", "📖", "📕", "📗", "📘", "📙",
    "🏠", "🏛️", "🔬", "💻", "📐", "🧠", "🎨", "🎵",
    "⭐", "❤️", "🔥", "🌿", "🎯", "🎭", "📝", "🗂️",
    "📰", "📜", "📓", "📔", "📒", "📃", "📄", "✨",
]


class ShelfIconPickerDialog(QDialog):
    def __init__(self, current_icon: str = "📁", parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择图标")
        self.setMinimumSize(360, 320)
        self._selected_icon = current_icon
        self._buttons = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        grid = QGridLayout()
        grid.setSpacing(4)
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
            if icon == self._selected_icon:
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
