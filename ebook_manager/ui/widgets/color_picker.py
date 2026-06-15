from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QPushButton, QVBoxLayout, QGridLayout,
    QHBoxLayout, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QColorDialog


PRESET_COLORS = [
    "", "#e74c3c", "#e67e22", "#f1c40f", "#2ecc71",
    "#1abc9c", "#3498db", "#9b59b6", "#34495e", "#95a5a6"
]


class ShelfColorPickerDialog(QDialog):
    def __init__(self, current_color: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择颜色")
        self.setMinimumSize(320, 200)
        self._selected_color = current_color
        self._buttons = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("预设颜色:"))
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
            if color == self._selected_color:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, c=color: self._on_color_selected(c))
            grid.addWidget(btn, i // 5, i % 5)
            self._buttons.append((btn, color))
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
        for btn, c in self._buttons:
            btn.setChecked(c == color)

    def _pick_custom_color(self):
        initial = QColor(self._selected_color) if self._selected_color else QColor()
        color = QColorDialog.getColor(initial, self, "自定义颜色")
        if color.isValid():
            self._selected_color = color.name()
            for btn, c in self._buttons:
                btn.setChecked(False)

    def get_selected_color(self) -> str:
        return self._selected_color
