"""Hauptfenster und Qt-Bedienelemente."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox, QApplication, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QDockWidget, QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QTabWidget, QTextBrowser, QToolBar, QToolButton, QVBoxLayout, QWidget,
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
        form.addRow(tr("Track area length:"), self.length)
        form.addRow(tr("Track area width:"), self.width)
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
        self._create_properties_dock()
        self.apply_appearance()
        self.canvas.project_changed.connect(self._mark_dirty)
        self.canvas.selection_changed.connect(self._selection_changed)
        self.canvas.status_message.connect(self.statusBar().showMessage)
        self.canvas.closure_connectors_changed.connect(
            lambda count: self.close_track_action.setEnabled(count == 2)
        )
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
        self.copy_action = self._action(tr("Copy selection"), self.canvas.copy_selected,
                                        QKeySequence.StandardKey.Copy)
        self.copy_action.setEnabled(False)
        self.paste_action = self._action(tr("Paste"), self.canvas.paste_copied,
                                         QKeySequence.StandardKey.Paste)
        self.close_track_action = self._action(tr("Close track…"), self.close_track)
        self.close_track_action.setEnabled(False)
        self.rotate_left_action = self._action(tr("Rotate 5° left"), lambda: self.canvas.rotate_selected(5), "Ctrl+Left")
        self.rotate_right_action = self._action(tr("Rotate 5° right"), lambda: self.canvas.rotate_selected(-5), "Ctrl+Right")
        self.fit_action = self._action(tr("Fit track area"), self.canvas.fit_to_view, "F")
        self.fit_action.setIcon(QIcon(str(Path(__file__).with_name("assets") / "fit_view.svg")))
        self.settings_action = self._action(tr("Settings…"), self.show_settings, "Ctrl+,")
        self.dismiss_action = self._action("", self.dismiss_current, "Esc")
        self.dismiss_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.addAction(self.dismiss_action)
        self.guide_action = self._action(tr("User guide"), self.show_user_guide, "F1")
        self.about_action = self._action(tr("About RC Track Designer"), self.about)
        self.undo_action = self.canvas.undo_stack.createUndoAction(self, tr("Undo")); self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.redo_action = self.canvas.undo_stack.createRedoAction(self, tr("Redo")); self.redo_action.setShortcut("Ctrl+Y")

    def _create_menu(self) -> None:
        tr = self.tr_text
        self.file_menu = self.menuBar().addMenu(tr("File"))
        file_menu = self.file_menu
        file_menu.addActions([self.new_action, self.open_action, self.save_action, self.save_as_action])
        file_menu.addSeparator(); file_menu.addAction(self.exit_action)
        self.edit_menu = self.menuBar().addMenu(tr("Edit")); edit = self.edit_menu
        edit.addActions([self.undo_action, self.redo_action]); edit.addSeparator()
        edit.addActions([self.copy_action, self.paste_action]); edit.addSeparator()
        edit.addAction(self.close_track_action); edit.addSeparator()
        edit.addActions([self.rotate_left_action, self.rotate_right_action, self.delete_action])
        self.view_menu = self.menuBar().addMenu(tr("View")); self.view_menu.addAction(self.fit_action); self.view_menu.addAction(self.settings_action)
        self.help_menu = self.menuBar().addMenu(tr("Help"))
        self.help_menu.addAction(self.guide_action)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.about_action)

    def _spin(self, value, minimum, maximum, suffix) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(); spin.setRange(minimum, maximum); spin.setValue(value); spin.setSuffix(suffix); spin.setDecimals(2)
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.PlusMinus)
        spin.setMinimumWidth(105)
        return spin

    def _create_toolbars(self) -> None:
        tr = self.tr_text
        main = QToolBar(tr("File and editing"), self); main.setMovable(False)
        self.main_toolbar = main
        main.setContentsMargins(0, 0, 198, 0)
        self.addToolBar(main)
        main.addActions([self.new_action, self.open_action, self.save_action]); main.addSeparator()
        main.addAction(self.fit_action)
        self.fit_action.setToolTip(tr("Reset zoom and pan so the complete track area is centred in the workspace."))
        main.addSeparator()
        self.hall_length_spin = self._spin(self.canvas.project.hall_length, 1, 1000, " m")
        self.hall_width_spin = self._spin(self.canvas.project.hall_width, 1, 1000, " m")
        self.hall_length_spin.setMinimumWidth(78); self.hall_length_spin.setMaximumWidth(82)
        self.hall_width_spin.setMinimumWidth(78); self.hall_width_spin.setMaximumWidth(82)
        self.hall_length_label = QLabel(f" {tr('L:')} ")
        self.hall_width_label = QLabel(f" {tr('W:')} ")
        self.hall_length_label.setFixedWidth(20)
        self.hall_width_label.setFixedWidth(20)
        self.hall_length_label.setToolTip(tr("Track area length:"))
        self.hall_width_label.setToolTip(tr("Track area width:"))
        self.hall_length_spin.setToolTip(tr("Track area length:"))
        self.hall_width_spin.setToolTip(tr("Track area width:"))
        self.area_dimensions_widget = QWidget()
        area_layout = QVBoxLayout(self.area_dimensions_widget)
        area_layout.setContentsMargins(2, 1, 2, 1)
        area_layout.setSpacing(0)
        self.area_dimensions_label = QLabel(tr("Track area"))
        self.area_dimensions_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        area_layout.addWidget(self.area_dimensions_label)
        area_inputs = QHBoxLayout()
        area_inputs.setContentsMargins(0, 0, 0, 0)
        area_inputs.setSpacing(2)
        area_inputs.addWidget(self.hall_length_label)
        area_inputs.addWidget(self.hall_length_spin)
        area_inputs.addWidget(self.hall_width_label)
        area_inputs.addWidget(self.hall_width_spin)
        area_layout.addLayout(area_inputs)
        main.addWidget(self.area_dimensions_widget)
        self.hall_length_spin.valueChanged.connect(self._hall_length_changed)
        self.hall_width_spin.valueChanged.connect(self._hall_width_changed)
        main.addSeparator()
        self.rotate_left_button = QToolButton()
        self.rotate_left_button.setText(tr("5° left"))
        self.rotate_left_button.setToolTip(tr("Rotate 5° left"))
        self.rotate_left_button.setFixedWidth(86)
        self.rotate_left_button.clicked.connect(self.rotate_left_action.trigger)
        self.rotate_right_button = QToolButton()
        self.rotate_right_button.setText(tr("5° right"))
        self.rotate_right_button.setToolTip(tr("Rotate 5° right"))
        self.rotate_right_button.setFixedWidth(86)
        self.rotate_right_button.clicked.connect(self.rotate_right_action.trigger)
        self.delete_button = QToolButton()
        self.delete_button.setText(tr("Delete selection"))
        self.delete_button.setFixedWidth(110)
        self.delete_button.clicked.connect(self.delete_action.trigger)
        for action, button in ((self.rotate_left_action, self.rotate_left_button),
                               (self.rotate_right_action, self.rotate_right_button),
                               (self.delete_action, self.delete_button)):
            button.setEnabled(action.isEnabled())
            action.changed.connect(lambda a=action, b=button: b.setEnabled(a.isEnabled()))
        main.addWidget(self.rotate_left_button)
        main.addWidget(self.rotate_right_button)
        main.addWidget(self.delete_button)
        palette = QToolBar(tr("Element palette"), self); palette.setMovable(False)
        self.palette_toolbar = palette
        palette.setContentsMargins(0, 0, 198, 0)
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
        self.logo_panel = QFrame(self)
        self.logo_panel.setObjectName("applicationLogoPanel")
        self.logo_panel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        logo_layout = QHBoxLayout(self.logo_panel)
        logo_layout.setContentsMargins(12, 8, 12, 8)
        self.logo_label = QLabel()
        self.logo_label.setObjectName("applicationLogo")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setToolTip("carbonKID")
        self.logo_source = QPixmap(str(Path(__file__).with_name("assets") / "carbonkid_logo.png"))
        logo_layout.addWidget(self.logo_label)
        options = QToolBar(tr("Element dimensions"), self); options.setMovable(False); self.addToolBarBreak(); self.addToolBar(options)
        self.width_spin = self._spin(2, 0.1, 20, " m")
        self.length_spin = self._spin(5, 0.1, 200, " m")
        self.length_spin.setSingleStep(0.5)
        self.radius_spin = self._spin(5, 0.1, 200, " m")
        self.radius_spin.setSingleStep(0.5)
        self.width_label = QLabel(f" {tr('Track width:')} "); self.length_label = QLabel(f" {tr('Straight length:')} "); self.radius_label = QLabel(f" {tr('Centerline radius:')} ")
        for label, spin in ((self.width_label, self.width_spin), (self.length_label, self.length_spin), (self.radius_label, self.radius_spin)):
            options.addWidget(label); options.addWidget(spin)
        self.width_spin.valueChanged.connect(self._width_changed)
        self.length_spin.valueChanged.connect(self._length_changed)
        self.radius_spin.valueChanged.connect(self._radius_changed)
        QTimer.singleShot(0, self._position_logo_panel)

    def _position_logo_panel(self) -> None:
        if not hasattr(self, "logo_panel"):
            return
        top = self.main_toolbar.geometry().top()
        bottom = self.palette_toolbar.geometry().bottom()
        panel_width = 190
        self.logo_panel.setGeometry(self.width() - panel_width, top,
                                    panel_width, max(1, bottom - top + 1))
        margins = self.logo_panel.layout().contentsMargins()
        available = QSize(
            max(1, self.logo_panel.width() - margins.left() - margins.right()),
            max(1, self.logo_panel.height() - margins.top() - margins.bottom()),
        )
        self.logo_label.setPixmap(self.logo_source.scaled(
            available, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))
        self.logo_panel.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        QTimer.singleShot(0, self._position_logo_panel)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        QTimer.singleShot(0, self._position_logo_panel)

    def _create_properties_dock(self) -> None:
        tr = self.tr_text
        self.properties_dock = QDockWidget(tr("Properties"), self)
        self.properties_dock.setObjectName("propertiesDock")
        panel = QWidget(); form = QFormLayout(panel)
        self.element_type_label = QLabel(tr("Element type:"))
        self.element_type_value = QLabel("—")
        form.addRow(self.element_type_label, self.element_type_value)
        self.property_spins = {}
        definitions = (
            ("angle_deg", tr("Curve angle:"), 0.0, 0, 90, "°"),
            ("x", tr("X position:"), 0.0, -10000, 10000, " m"),
            ("y", tr("Y position:"), 0.0, -10000, 10000, " m"),
            ("heading_deg", tr("Rotation:"), 0.0, -3600, 3600, "°"),
            ("width", tr("Track width:"), 2.0, 0.1, 20, " m"),
            ("length", tr("Length:"), 5.0, 0.1, 200, " m"),
            ("radius", tr("Radius:"), 5.0, 0.1, 200, " m"),
        )
        self.property_labels = {}
        for name, label_text, value, minimum, maximum, suffix in definitions:
            label = QLabel(label_text); spin = self._spin(value, minimum, maximum, suffix)
            if name in {"length", "radius"}:
                spin.setSingleStep(0.5)
            spin.valueChanged.connect(lambda new_value, key=name: self._property_changed(key, new_value))
            self.property_labels[name] = label; self.property_spins[name] = spin
            form.addRow(label, spin)
        self.properties_dock.setWidget(panel); self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        self.properties_dock.setMinimumWidth(260); panel.setEnabled(False)
        self.properties_toggle_action = self.properties_dock.toggleViewAction()
        self.properties_toggle_action.setText(tr("Properties"))
        self.view_menu.insertAction(self.settings_action, self.properties_toggle_action)
        self.view_menu.insertSeparator(self.settings_action)

    def _property_changed(self, name: str, value: float) -> None:
        values = {name: value}
        element = self.canvas.selected
        if name == "width" and element and element.kind != "straight":
            values["radius"] = max(element.radius, value / 2 + 0.1)
        self.canvas.change_selected(self.tr_text("Change properties"), **values)

    def _sync_properties(self, element: TrackElement | None) -> None:
        panel = self.properties_dock.widget(); panel.setEnabled(element is not None)
        if not element:
            self.element_type_value.setText("—")
            angle_spin = self.property_spins["angle_deg"]
            angle_spin.blockSignals(True)
            angle_spin.setValue(0)
            angle_spin.blockSignals(False)
            self.property_spins["radius"].setMinimum(0.1)
            return
        type_source = {"straight": "Straight", "left": "Left curve", "right": "Right curve"}
        self.element_type_value.setText(self.tr_text(type_source[element.kind]))
        values = {"x": element.start.x, "y": element.start.y, "heading_deg": element.heading_deg,
                  "width": element.width, "length": element.length, "radius": element.radius,
                  "angle_deg": element.angle_deg if element.kind != "straight" else 0.0}
        self.property_spins["radius"].setMinimum(
            element.minimum_centerline_radius if element.kind != "straight" else 0.1
        )
        for name, spin in self.property_spins.items():
            spin.blockSignals(True); spin.setValue(values[name]); spin.blockSignals(False)
        is_curve = element.kind != "straight"
        self.property_spins["heading_deg"].setEnabled(True)
        self.property_spins["length"].setEnabled(not is_curve)
        self.property_spins["radius"].setEnabled(is_curve)
        self.property_spins["angle_deg"].setEnabled(is_curve)

    def _selection_changed(self, element: TrackElement | None) -> None:
        self.delete_action.setEnabled(element is not None)
        self.copy_action.setEnabled(element is not None)
        self.rotate_left_action.setEnabled(self.canvas.can_rotate_selected(5))
        self.rotate_right_action.setEnabled(self.canvas.can_rotate_selected(-5))
        if element:
            for spin, value in ((self.width_spin, element.width), (self.length_spin, element.length), (self.radius_spin, element.radius)):
                spin.blockSignals(True); spin.setValue(value); spin.blockSignals(False)
        self._sync_properties(element)

    def _width_changed(self, value: float) -> None:
        self.canvas.default_width = value
        minimum_radius = value / 2 + 0.1
        self.radius_spin.setMinimum(minimum_radius)
        radius = max(self.radius_spin.value(), minimum_radius)
        if radius != self.radius_spin.value():
            self.radius_spin.blockSignals(True)
            self.radius_spin.setValue(radius)
            self.radius_spin.blockSignals(False)
        self.canvas.default_radius = radius
        if self.canvas.selected:
            values = {"width": value}
            if self.canvas.selected.kind != "straight":
                values["radius"] = max(self.canvas.selected.radius, minimum_radius)
            self.canvas.change_selected(self.tr_text("Change track width"), **values)

    def _length_changed(self, value: float) -> None:
        self.canvas.default_length = value
        if self.canvas.selected: self.canvas.change_selected(self.tr_text("Change length"), length=value)

    def _radius_changed(self, value: float) -> None:
        self.canvas.default_radius = value
        if self.canvas.selected: self.canvas.change_selected(self.tr_text("Change radius"), radius=value)

    def _hall_length_changed(self, value: float) -> None:
        previous = self.canvas.project.hall_length
        self.canvas.project.hall_length = value
        if (not self.canvas.project.all_elements_fit_hall()
                or any(guide > value for guide in self.canvas.project.guides_x)):
            self.canvas.project.hall_length = previous
            self.hall_length_spin.blockSignals(True); self.hall_length_spin.setValue(previous); self.hall_length_spin.blockSignals(False)
            self.statusBar().showMessage(self.tr_text("The track area would be too small for existing elements or guides."), 4000)
            return
        self.canvas.fit_to_view()
        self.canvas.project_changed.emit()

    def _hall_width_changed(self, value: float) -> None:
        previous = self.canvas.project.hall_width
        self.canvas.project.hall_width = value
        if (not self.canvas.project.all_elements_fit_hall()
                or any(guide > value for guide in self.canvas.project.guides_y)):
            self.canvas.project.hall_width = previous
            self.hall_width_spin.blockSignals(True); self.hall_width_spin.setValue(previous); self.hall_width_spin.blockSignals(False)
            self.statusBar().showMessage(self.tr_text("The track area would be too small for existing elements or guides."), 4000)
            return
        self.canvas.fit_to_view()
        self.canvas.project_changed.emit()

    def _sync_hall_controls(self) -> None:
        for spin, value in ((self.hall_length_spin, self.canvas.project.hall_length),
                            (self.hall_width_spin, self.canvas.project.hall_width)):
            spin.blockSignals(True); spin.setValue(value); spin.blockSignals(False)

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

    def dismiss_current(self) -> None:
        if self.canvas.placement:
            self.canvas.cancel_placement()
        else:
            self.canvas.clear_selection()
        self.canvas.setFocus()

    def close_track(self) -> None:
        tr = self.tr_text
        proposal = self.canvas.prepare_track_closure()
        if proposal is None:
            QMessageBox.information(
                self, tr("Close track"),
                tr("No valid local solution was found. Select two free connectors on the same open track with Ctrl+click, or add a suitable straight or curve."),
            )
            return
        parameter_names = {
            "length": tr("Length"), "radius": tr("Radius"),
            "angle_deg": tr("Curve angle"),
        }
        lines = []
        for element_id, name, before, after in proposal.changed:
            element = self.canvas.project.element_by_id(element_id)
            element_name = tr({"straight": "Straight", "left": "Left curve",
                               "right": "Right curve"}[element.kind])
            unit = "°" if name == "angle_deg" else " m"
            lines.append(
                f"• {element_name} — {parameter_names[name]}: "
                f"{before:.3f}{unit} → {after:.3f}{unit}"
            )
        details = "\n".join(lines) or tr("Only the final connection is required.")
        box = QMessageBox(
            QMessageBox.Icon.Question,
            tr("Close track"),
            tr("The following local adjustments close the track exactly:")
            + "\n\n" + details + "\n\n"
            + tr("Apply these changes?"),
            QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel,
            self,
        )
        box.button(QMessageBox.StandardButton.Apply).setText(tr("Apply"))
        box.button(QMessageBox.StandardButton.Cancel).setText(tr("Cancel"))
        if QMessageBox.StandardButton(box.exec()) == QMessageBox.StandardButton.Apply:
            self.canvas.apply_track_closure(proposal)
            self.statusBar().showMessage(tr("Track closed successfully."), 5000)

    def show_user_guide(self) -> None:
        tr = self.tr_text
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Using RC Track Designer"))
        dialog.resize(720, 620)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser(dialog)
        browser.setOpenExternalLinks(True)
        sections = (
            ("Create a track area", "Create a new project and enter the length and width of the available track area. The internal unit is metres."),
            ("Place and connect elements", "Choose a straight or curve from the upper palette. Click an empty position for a free element, or click a blue free connector to continue the track automatically. Green connectors are connected; the orange connector is active."),
            ("Select and edit", "Click an element to select and drag it. Hold Shift while clicking, or draw a selection rectangle, to select several elements. Use the properties panel for exact dimensions and positions. Esc cancels placement or clears the selection."),
            ("Close gaps and move groups", "Drag the free connector of a one-sided connected element to change its length, radius or curve angle. Release it near a compatible connector to close the gap. A selected connected group moves as one rigid unit and can snap to an external free connector."),
            ("Close an open track", "Select the two free connectors of one open track with Ctrl+click. Choose Edit > Close track. The preview lists local length, radius and angle adjustments; nothing changes until you confirm."),
            ("Navigate and organise", "Zoom with the mouse wheel. Pan with the middle mouse button or Space plus the left mouse button. Drag guides from the rulers; remove a guide with the right mouse button."),
            ("Correct mistakes and save", "Use Ctrl+Z and Ctrl+Y for undo and redo. Ctrl+C and Ctrl+V copy and paste selected elements. Save projects as JSON files from the File menu."),
        )
        html = [f"<h1>{tr('Using RC Track Designer')}</h1>"]
        for heading, body in sections:
            html.append(f"<h2>{tr(heading)}</h2><p>{tr(body)}</p>")
        browser.setHtml("".join(html))
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(tr("Close"))
        layout.addWidget(buttons)
        dialog.exec()

    def retranslate_ui(self) -> None:
        tr = self.tr_text
        actions = (
            (self.new_action, "New…"), (self.open_action, "Open…"), (self.save_action, "Save"),
            (self.save_as_action, "Save as…"), (self.exit_action, "Exit"),
            (self.delete_action, "Delete selection"), (self.rotate_left_action, "Rotate 5° left"),
            (self.rotate_right_action, "Rotate 5° right"), (self.fit_action, "Fit track area"),
            (self.copy_action, "Copy selection"), (self.paste_action, "Paste"),
            (self.close_track_action, "Close track…"),
            (self.settings_action, "Settings…"), (self.guide_action, "User guide"),
            (self.about_action, "About RC Track Designer"),
            (self.straight_action, "Straight"), (self.undo_action, "Undo"), (self.redo_action, "Redo"),
        )
        for action, source in actions: action.setText(tr(source))
        self.rotate_left_button.setText(tr("5° left"))
        self.rotate_left_button.setToolTip(tr("Rotate 5° left"))
        self.rotate_right_button.setText(tr("5° right"))
        self.rotate_right_button.setToolTip(tr("Rotate 5° right"))
        self.delete_button.setText(tr("Delete selection"))
        for menu, source in ((self.file_menu, "File"), (self.edit_menu, "Edit"),
                             (self.view_menu, "View"), (self.help_menu, "Help")):
            menu.setTitle(tr(source))
        self.elements_label.setText(f" {tr('Elements:')} ")
        self.left_label.setText(f" {tr('Left curves:')} ")
        self.right_label.setText(f" {tr('Right curves:')} ")
        self.width_label.setText(f" {tr('Track width:')} ")
        self.length_label.setText(f" {tr('Straight length:')} ")
        self.radius_label.setText(f" {tr('Centerline radius:')} ")
        self.hall_length_label.setText(f" {tr('L:')} ")
        self.hall_width_label.setText(f" {tr('W:')} ")
        self.area_dimensions_label.setText(tr("Track area"))
        self.hall_length_label.setToolTip(tr("Track area length:"))
        self.hall_width_label.setToolTip(tr("Track area width:"))
        self.hall_length_spin.setToolTip(tr("Track area length:"))
        self.hall_width_spin.setToolTip(tr("Track area width:"))
        self.fit_action.setToolTip(tr("Reset zoom and pan so the complete track area is centred in the workspace."))
        self.properties_dock.setWindowTitle(tr("Properties"))
        self.properties_toggle_action.setText(tr("Properties"))
        self.element_type_label.setText(tr("Element type:"))
        property_sources = {"x": "X position:", "y": "Y position:", "heading_deg": "Rotation:",
                            "width": "Track width:", "length": "Length:", "radius": "Radius:",
                            "angle_deg": "Curve angle:"}
        for name, source in property_sources.items(): self.property_labels[name].setText(tr(source))
        self._sync_properties(self.canvas.selected)
        self.canvas.set_appearance({}, tr)
        self._update_title()

    def _can_discard(self) -> bool:
        if not self.dirty: return True
        box = QMessageBox(QMessageBox.Icon.Question, self.tr_text("Unsaved changes"),
                          self.tr_text("Save changes before continuing?"),
                          QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                          self)
        box.button(QMessageBox.StandardButton.Save).setText(self.tr_text("Save"))
        box.button(QMessageBox.StandardButton.Discard).setText(self.tr_text("Discard"))
        box.button(QMessageBox.StandardButton.Cancel).setText(self.tr_text("Cancel"))
        answer = QMessageBox.StandardButton(box.exec())
        if answer == QMessageBox.StandardButton.Cancel: return False
        if answer == QMessageBox.StandardButton.Save: return self.save()
        return True

    def new_project(self) -> None:
        if not self._can_discard(): return
        dialog = NewProjectDialog(self.tr_text, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.canvas.set_project(TrackProject(dialog.length.value(), dialog.width.value()))
            self._sync_hall_controls()
            self.current_path = None; self.dirty = False; self._update_title()

    def open_project(self) -> None:
        if not self._can_discard(): return
        filename, _ = QFileDialog.getOpenFileName(self, self.tr_text("Open project"), "", "RC Track Designer (*.rct.json *.json)")
        if not filename: return
        try: project = load_project(filename)
        except Exception as error: QMessageBox.critical(self, self.tr_text("Open failed"), str(error)); return
        self.canvas.set_project(project); self._sync_hall_controls(); self.current_path = Path(filename); self.dirty = False; self._update_title()

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
