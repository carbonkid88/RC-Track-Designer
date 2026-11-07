"""Hauptfenster und Qt-Bedienelemente."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QTabWidget, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from . import __version__
from .canvas import TrackCanvas
from .i18n import TranslationManager
from .model import TrackElement, TrackProject
from .storage import load_project, save_project
from .themes import apply_theme


class NewProjectDialog(QDialog):
    def __init__(self, tr, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("New layout"))
        form = QFormLayout(self)
        self.length = QDoubleSpinBox(); self.length.setRange(1, 1000); self.length.setValue(30); self.length.setSuffix(" m")
        self.width = QDoubleSpinBox(); self.width.setRange(1, 1000); self.width.setValue(20); self.width.setSuffix(" m")
        form.addRow(tr("Hall length:"), self.length)
        form.addRow(tr("Hall width:"), self.width)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class SettingsDialog(QDialog):
    def __init__(self, translations: TranslationManager, theme: str, parent=None) -> None:
        super().__init__(parent)
        tr = translations.tr
        self.setWindowTitle(tr("Settings"))
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        appearance = QWidget(); appearance_form = QFormLayout(appearance)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem(tr("Dark"), "dark"); self.theme_combo.addItem(tr("Light"), "light")
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(theme)))
        appearance_form.addRow(tr("Theme:"), self.theme_combo)
        tabs.addTab(appearance, tr("Appearance"))
        language = QWidget(); language_layout = QVBoxLayout(language)
        language_form = QFormLayout(); self.language_combo = QComboBox()
        for item in translations.available_languages(): self.language_combo.addItem(item.name, item.code)
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(translations.language)))
        language_form.addRow(tr("Language:"), self.language_combo); language_layout.addLayout(language_form)
        hint = QLabel(tr("Additional languages can be added as JSON files in:") + f"\n{translations.user_locale_dir()}")
        hint.setWordWrap(True); hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        language_layout.addWidget(hint); language_layout.addStretch()
        tabs.addTab(language, tr("Language")); layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings()
        self.translations = TranslationManager(str(self.settings.value("language", "de")))
        self.theme = str(self.settings.value("theme", "dark"))
        self.tr_text = self.translations.tr
        self.resize(1200, 800)
        self.current_path: Path | None = None
        self.dirty = False
        self.canvas = TrackCanvas()
        self.setCentralWidget(self.canvas)
        self._create_actions()
        self._create_menu()
        self._create_toolbars()
        self.apply_appearance()
        self.canvas.project_changed.connect(self._mark_dirty)
        self.canvas.selection_changed.connect(self._selection_changed)
        self.canvas.status_message.connect(self.statusBar().showMessage)
        self.statusBar().showMessage(self.tr_text("Ready — choose an element or click an existing track"))
        self._update_title()

    def _action(self, text, slot, shortcut=None, icon_text=None) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(slot)
        if shortcut: action.setShortcut(shortcut)
        if icon_text: action.setIconText(icon_text)
        return action

    def _create_actions(self) -> None:
        tr = self.tr_text
        self.new_action = self._action(tr("New…"), self.new_project, QKeySequence.StandardKey.New)
        self.open_action = self._action(tr("Open…"), self.open_project, QKeySequence.StandardKey.Open)
        self.save_action = self._action(tr("Save"), self.save, QKeySequence.StandardKey.Save)
        self.save_as_action = self._action(tr("Save as…"), self.save_as, QKeySequence.StandardKey.SaveAs)
        self.exit_action = self._action(tr("Exit"), self.close, QKeySequence.StandardKey.Quit)
        self.delete_action = self._action(tr("Delete selection"), self.canvas.delete_selected, QKeySequence.StandardKey.Delete)
        self.delete_action.setEnabled(False)
        self.rotate_left_action = self._action(tr("Rotate 5° left"), lambda: self.canvas.rotate_selected(5), "Ctrl+Left")
        self.rotate_right_action = self._action(tr("Rotate 5° right"), lambda: self.canvas.rotate_selected(-5), "Ctrl+Right")
        self.fit_action = self._action(tr("Fit hall"), self.canvas.fit_to_view, "F")
        self.settings_action = self._action(tr("Settings…"), self.show_settings, "Ctrl+,")
        self.about_action = self._action(tr("About RC Track Designer"), self.about)

    def _create_menu(self) -> None:
        tr = self.tr_text
        self.file_menu = self.menuBar().addMenu(tr("File"))
        file_menu = self.file_menu
        file_menu.addActions([self.new_action, self.open_action, self.save_action, self.save_as_action])
        file_menu.addSeparator(); file_menu.addAction(self.exit_action)
        self.edit_menu = self.menuBar().addMenu(tr("Edit")); edit = self.edit_menu
        edit.addActions([self.rotate_left_action, self.rotate_right_action, self.delete_action])
        self.view_menu = self.menuBar().addMenu(tr("View")); self.view_menu.addAction(self.fit_action); self.view_menu.addAction(self.settings_action)
        self.help_menu = self.menuBar().addMenu(tr("Help")); self.help_menu.addAction(self.about_action)

    def _spin(self, value, minimum, maximum, suffix) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(); spin.setRange(minimum, maximum); spin.setValue(value); spin.setSuffix(suffix); spin.setDecimals(2)
        return spin

    def _create_toolbars(self) -> None:
        tr = self.tr_text
        main = QToolBar(tr("File and editing"), self); main.setMovable(False)
        self.addToolBar(main)
        main.addActions([self.new_action, self.open_action, self.save_action]); main.addSeparator()
        main.addActions([self.rotate_left_action, self.rotate_right_action, self.delete_action, self.fit_action])
        palette = QToolBar(tr("Element palette"), self); palette.setMovable(False)
        self.addToolBarBreak(); self.addToolBar(palette)
        self.elements_label = QLabel(f" {tr('Elements:')} ")
        self.straight_action = QAction(tr("Straight"), self); self.straight_action.triggered.connect(lambda: self.canvas.set_placement("straight"))
        palette.addAction(self.straight_action)
        palette_widget = QWidget()
        palette_widget.setObjectName("elementPalette")
        palette_layout = QVBoxLayout(palette_widget)
        palette_layout.setContentsMargins(2, 1, 2, 1); palette_layout.setSpacing(3)
        left_row = QHBoxLayout(); left_row.setContentsMargins(0, 0, 0, 0); left_row.setSpacing(4)
        right_row = QHBoxLayout(); right_row.setContentsMargins(0, 0, 0, 0); right_row.setSpacing(4)
        self.left_label = QLabel(f" {tr('Left curves:')} "); self.left_label.setFixedWidth(105); left_row.addWidget(self.left_label)
        for angle in range(5, 91, 5):
            action = QAction(f"{angle}°", self); action.triggered.connect(lambda checked=False, a=angle: self.canvas.set_placement("left", a))
            button = QToolButton(); button.setFixedWidth(38); button.setDefaultAction(action); left_row.addWidget(button)
        left_row.addStretch()
        self.right_label = QLabel(f" {tr('Right curves:')} ")
        # Einrückung richtet beide Winkelreihen optisch aneinander aus.
        self.right_label.setFixedWidth(105); right_row.addWidget(self.right_label)
        for angle in range(5, 91, 5):
            action = QAction(f"{angle}°", self); action.triggered.connect(lambda checked=False, a=angle: self.canvas.set_placement("right", a))
            button = QToolButton(); button.setFixedWidth(38); button.setDefaultAction(action); right_row.addWidget(button)
        right_row.addStretch()
        palette_layout.addLayout(left_row); palette_layout.addLayout(right_row)
        palette.addWidget(palette_widget)
        palette.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        options = QToolBar(tr("Element dimensions"), self); options.setMovable(False); self.addToolBarBreak(); self.addToolBar(options)
        self.width_spin = self._spin(2, 0.1, 20, " m")
        self.length_spin = self._spin(5, 0.1, 200, " m")
        self.radius_spin = self._spin(5, 0.1, 200, " m")
        self.width_label = QLabel(f" {tr('Track width:')} "); self.length_label = QLabel(f" {tr('Straight length:')} "); self.radius_label = QLabel(f" {tr('Centerline radius:')} ")
        for label, spin in ((self.width_label, self.width_spin), (self.length_label, self.length_spin), (self.radius_label, self.radius_spin)):
            options.addWidget(label); options.addWidget(spin)
        self.width_spin.valueChanged.connect(self._width_changed)
        self.length_spin.valueChanged.connect(self._length_changed)
        self.radius_spin.valueChanged.connect(self._radius_changed)

    def _selection_changed(self, element: TrackElement | None) -> None:
        self.delete_action.setEnabled(element is not None)
        self.rotate_left_action.setEnabled(element is not None); self.rotate_right_action.setEnabled(element is not None)
        if element:
            for spin, value in ((self.width_spin, element.width), (self.length_spin, element.length), (self.radius_spin, element.radius)):
                spin.blockSignals(True); spin.setValue(value); spin.blockSignals(False)

    def _width_changed(self, value: float) -> None:
        self.canvas.default_width = value
        if self.canvas.selected: self.canvas.selected.width = value; self.canvas.project_changed.emit(); self.canvas.update()

    def _length_changed(self, value: float) -> None:
        self.canvas.default_length = value
        if self.canvas.selected: self.canvas.selected.length = value; self.canvas.project_changed.emit(); self.canvas.update()

    def _radius_changed(self, value: float) -> None:
        self.canvas.default_radius = value
        if self.canvas.selected: self.canvas.selected.radius = value; self.canvas.project_changed.emit(); self.canvas.update()

    def _mark_dirty(self) -> None:
        self.dirty = True; self._update_title()

    def _update_title(self) -> None:
        name = self.current_path.name if self.current_path else self.tr_text("Untitled")
        self.setWindowTitle(f"{'*' if self.dirty else ''}{name} — RC Track Designer {__version__}")

    def apply_appearance(self) -> None:
        app = QApplication.instance()
        if app:
            colors = apply_theme(app, self.theme)
            self.canvas.set_appearance(colors, self.tr_text)

    def show_settings(self) -> None:
        dialog = SettingsDialog(self.translations, self.theme, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_theme = str(dialog.theme_combo.currentData())
        new_language = str(dialog.language_combo.currentData())
        language_changed = new_language != self.translations.language
        self.theme = new_theme
        self.translations.set_language(new_language)
        self.tr_text = self.translations.tr
        self.settings.setValue("theme", new_theme)
        self.settings.setValue("language", new_language)
        if language_changed:
            self.retranslate_ui()
        self.apply_appearance()
        self.statusBar().showMessage(self.tr_text("Ready — choose an element or click an existing track"), 4000)

    def retranslate_ui(self) -> None:
        tr = self.tr_text
        actions = (
            (self.new_action, "New…"), (self.open_action, "Open…"), (self.save_action, "Save"),
            (self.save_as_action, "Save as…"), (self.exit_action, "Exit"),
            (self.delete_action, "Delete selection"), (self.rotate_left_action, "Rotate 5° left"),
            (self.rotate_right_action, "Rotate 5° right"), (self.fit_action, "Fit hall"),
            (self.settings_action, "Settings…"), (self.about_action, "About RC Track Designer"),
            (self.straight_action, "Straight"),
        )
        for action, source in actions: action.setText(tr(source))
        for menu, source in ((self.file_menu, "File"), (self.edit_menu, "Edit"),
                             (self.view_menu, "View"), (self.help_menu, "Help")):
            menu.setTitle(tr(source))
        self.elements_label.setText(f" {tr('Elements:')} ")
        self.left_label.setText(f" {tr('Left curves:')} ")
        self.right_label.setText(f" {tr('Right curves:')} ")
        self.width_label.setText(f" {tr('Track width:')} ")
        self.length_label.setText(f" {tr('Straight length:')} ")
        self.radius_label.setText(f" {tr('Centerline radius:')} ")
        self.canvas.set_appearance({}, tr)
        self._update_title()

    def _can_discard(self) -> bool:
        if not self.dirty: return True
        answer = QMessageBox.question(self, self.tr_text("Unsaved changes"), self.tr_text("Save changes before continuing?"),
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Cancel: return False
        if answer == QMessageBox.StandardButton.Save: return self.save()
        return True

    def new_project(self) -> None:
        if not self._can_discard(): return
        dialog = NewProjectDialog(self.tr_text, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.canvas.set_project(TrackProject(dialog.length.value(), dialog.width.value()))
            self.current_path = None; self.dirty = False; self._update_title()

    def open_project(self) -> None:
        if not self._can_discard(): return
        filename, _ = QFileDialog.getOpenFileName(self, self.tr_text("Open project"), "", "RC Track Designer (*.rct.json *.json)")
        if not filename: return
        try: project = load_project(filename)
        except Exception as error: QMessageBox.critical(self, self.tr_text("Open failed"), str(error)); return
        self.canvas.set_project(project); self.current_path = Path(filename); self.dirty = False; self._update_title()

    def save(self) -> bool:
        return self._save_to(self.current_path) if self.current_path else self.save_as()

    def save_as(self) -> bool:
        filename, _ = QFileDialog.getSaveFileName(self, self.tr_text("Save project"), str(self.current_path or "layout.rct.json"), "RC Track Designer (*.rct.json)")
        if not filename: return False
        if not filename.lower().endswith(".json"): filename += ".rct.json"
        return self._save_to(Path(filename))

    def _save_to(self, path: Path) -> bool:
        try: save_project(self.canvas.project, path)
        except Exception as error: QMessageBox.critical(self, self.tr_text("Save failed"), str(error)); return False
        self.current_path = path; self.dirty = False; self._update_title(); self.statusBar().showMessage(self.tr_text("Saved: {path}", path=path), 4000); return True

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        event.accept() if self._can_discard() else event.ignore()

    def about(self) -> None:
        description = self.tr_text("2D layout editor for RC race tracks.\nInternal unit: metres.")
        QMessageBox.about(self, self.tr_text("About RC Track Designer"), f"RC Track Designer {__version__}\n\n{description}")
