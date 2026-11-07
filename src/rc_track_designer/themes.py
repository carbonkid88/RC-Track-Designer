"""Anwendungsweite Themes."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


THEMES = {
    "dark": {
        "window": "#242526", "panel": "#333536", "panel_alt": "#292b2c",
        "text": "#f3f5f7", "muted": "#aeb5bd", "border": "#151617",
        "blue_top": "#1769a4", "blue_bottom": "#084c83", "blue_hover": "#2183c5",
        "field": "#202223", "canvas": "#202326", "hall": "#e8e8e4",
        "grid": "#c9c9c4", "track": "#555b62", "centerline": "#f7f7f7"
    },
    "light": {
        "window": "#e5e8eb", "panel": "#f5f6f7", "panel_alt": "#d9dde1",
        "text": "#17202a", "muted": "#52606d", "border": "#aeb5bd",
        "blue_top": "#2582c4", "blue_bottom": "#0860a0", "blue_hover": "#3396d7",
        "field": "#ffffff", "canvas": "#c9ced3", "hall": "#ffffff",
        "grid": "#d8dce0", "track": "#5c6269", "centerline": "#ffffff"
    },
}


def apply_theme(app: QApplication, name: str) -> dict[str, str]:
    colors = THEMES.get(name, THEMES["dark"])
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["field"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["panel_alt"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["panel"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["blue_top"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(f"""
        QMainWindow, QDialog {{ background: {colors['window']}; }}
        QMenuBar {{ background: {colors['panel_alt']}; color: {colors['text']}; padding: 3px; }}
        QMenuBar::item {{ padding: 5px 9px; border-radius: 3px; }}
        QMenuBar::item:selected, QMenu::item:selected {{ background: {colors['blue_top']}; color: white; }}
        QMenu {{ background: {colors['panel']}; color: {colors['text']}; border: 1px solid {colors['border']}; }}
        QMenu::item {{ padding: 7px 28px 7px 12px; }}
        QToolBar {{ background: {colors['panel_alt']}; border: 1px solid {colors['border']}; spacing: 4px; padding: 5px; }}
        QToolBar QLabel {{ color: {colors['text']}; font-weight: 600; padding: 0 3px; }}
        QToolButton, QPushButton {{
            color: white; min-height: 26px; padding: 4px 10px; border-radius: 4px;
            border: 1px solid {colors['border']};
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {colors['blue_top']}, stop:1 {colors['blue_bottom']});
        }}
        QToolButton:hover, QPushButton:hover {{ background: {colors['blue_hover']}; }}
        QToolButton:pressed, QPushButton:pressed {{ background: {colors['blue_bottom']}; padding-top: 5px; }}
        QToolButton:disabled, QPushButton:disabled {{ background: {colors['panel']}; color: {colors['muted']}; }}
        QWidget#elementPalette QToolButton {{ min-height: 22px; padding: 2px 6px; }}
        QDoubleSpinBox, QComboBox {{ background: {colors['field']}; color: {colors['text']}; border: 1px solid {colors['border']}; border-radius: 3px; padding: 4px; min-height: 22px; }}
        QStatusBar {{ background: {colors['panel_alt']}; color: {colors['muted']}; border-top: 1px solid {colors['border']}; }}
        QGroupBox {{ font-weight: 600; border: 1px solid {colors['border']}; border-radius: 4px; margin-top: 10px; padding-top: 10px; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; }}
        QDialogButtonBox QPushButton {{ min-width: 80px; }}
        QToolBar::separator {{ background: {colors['border']}; width: 1px; margin: 3px 5px; }}
    """)
    return colors
