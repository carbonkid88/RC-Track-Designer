"""Hauptfenster und Qt-Bedienelemente."""

from __future__ import annotations

from importlib.metadata import files as distribution_files
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox, QApplication, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QDockWidget, QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QTabWidget, QTextBrowser, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from . import __release_name__
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
        self.setWindowIcon(QIcon(str(Path(__file__).with_name("assets") / "software_icon_candidate.png")))
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
        self.canvas.project_changed.connect(self._project_changed)
        self.canvas.selection_changed.connect(self._selection_changed)
        self.canvas.status_message.connect(self.statusBar().showMessage)
        self.canvas.closure_connectors_changed.connect(
            lambda count: self.close_track_action.setEnabled(count == 2)
        )
        self.canvas.close_track_requested.connect(self.close_track)
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
        self.license_action = self._action(tr("License"), self.show_license)
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
        self.view_menu = self.menuBar().addMenu(tr("Settings")); self.view_menu.addAction(self.fit_action); self.view_menu.addAction(self.settings_action)
        self.help_menu = self.menuBar().addMenu(tr("Help"))
        self.help_menu.addAction(self.guide_action)
        self.help_menu.addAction(self.license_action)
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
        self.mode_label = QLabel(f" {tr('Editing mode:')} ")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(tr("Normal mode"), "normal")
        self.mode_combo.addItem(tr("Indoor mode"), "indoor")
        self.mode_combo.setMinimumWidth(135)
        self.mode_combo.setCurrentIndex(self.mode_combo.findData(self.canvas.project.editor_mode))
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
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
        palette_widget = QWidget()
        palette_widget.setObjectName("elementPalette")
        palette_layout = QVBoxLayout(palette_widget)
        palette_layout.setContentsMargins(4, 1, 2, 2); palette_layout.setSpacing(1)
        self.palette_mode_label = QLabel(tr("Normal mode"))
        self.palette_mode_label.setObjectName("paletteModeLabel")
        self.palette_mode_label.setFixedHeight(18)
        palette_layout.addWidget(self.palette_mode_label)
        element_row = QHBoxLayout()
        element_row.setContentsMargins(0, 0, 0, 0); element_row.setSpacing(3)
        self.straight_button = QToolButton()
        self.straight_button.setDefaultAction(self.straight_action)
        self.straight_button.setFixedWidth(78)
        element_row.addWidget(self.straight_button)
        self.curve_label = QLabel(f" {tr('Curves:')} ")
        self.curve_label.setFixedWidth(64)
        element_row.addWidget(self.curve_label)
        self.curve_actions = []
        self.curve_buttons = []
        for angle in range(5, 91, 5):
            action = QAction(f"{angle}°", self)
            action.triggered.connect(
                lambda checked=False, a=angle: self.canvas.set_placement("curve", a)
            )
            self.curve_actions.append(action)
            button = QToolButton(); button.setFixedWidth(34); button.setDefaultAction(action)
            self.curve_buttons.append(button)
            element_row.addWidget(button)
        element_row.addStretch()
        palette_layout.addLayout(element_row)
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
        options.addWidget(self.mode_label)
        options.addWidget(self.mode_combo)
        options.addSeparator()
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
        self._apply_mode_ui()
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
            label = QLabel(label_text); label.setFixedWidth(125)
            spin = self._spin(value, minimum, maximum, suffix)
            if name in {"length", "radius"}:
                spin.setSingleStep(0.5)
            spin.valueChanged.connect(lambda new_value, key=name: self._property_changed(key, new_value))
            self.property_labels[name] = label; self.property_spins[name] = spin
            form.addRow(label, spin)
        self.properties_dock.setWidget(panel); self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        self.properties_dock.setMinimumWidth(285)
        self.properties_dock.setMaximumWidth(285)
        panel.setEnabled(False)
        self.properties_toggle_action = self.properties_dock.toggleViewAction()
        self.properties_toggle_action.setText(tr("Properties"))
        self.view_menu.insertAction(self.settings_action, self.properties_toggle_action)
        self.view_menu.insertSeparator(self.settings_action)

    def _property_changed(self, name: str, value: float) -> None:
        element = self.canvas.selected
        if name == "width" and element and element.element_type == "boundary":
            allowed = (5.0, 10.0, 15.0, 20.0, 25.0)
            value = min(allowed, key=lambda item: abs(item - value)) / 100.0
        values = {name: value}
        if name == "width" and element and element.kind != "straight":
            values["radius"] = max(element.radius, value / 2)
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
        width_spin = self.property_spins["width"]
        width_spin.blockSignals(True)
        if element.element_type == "boundary":
            width_spin.setRange(5, 25); width_spin.setSingleStep(5)
            width_spin.setDecimals(0); width_spin.setSuffix(" cm")
        else:
            width_spin.setRange(0.1, 20); width_spin.setSingleStep(0.1)
            width_spin.setDecimals(2); width_spin.setSuffix(" m")
        width_spin.blockSignals(False)
        self.property_labels["width"].setText(self.tr_text(
            "Boundary width:" if element.element_type == "boundary" else "Track width:"
        ))
        self.element_type_value.setText(
            self.tr_text(("Boundary straight" if element.kind == "straight" else "Boundary curve")
                         if element.element_type == "boundary"
                         else ("Straight" if element.kind == "straight" else "Curve"))
        )
        values = {"x": element.start.x, "y": element.start.y, "heading_deg": element.heading_deg,
                  "width": element.width * 100 if element.element_type == "boundary" else element.width,
                  "length": element.length, "radius": element.radius,
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
        expected_type = "boundary" if self.canvas.project.editor_mode == "indoor" else "track"
        if element and element.element_type == expected_type:
            width_value = element.width * 100 if element.element_type == "boundary" else element.width
            for spin, value in ((self.width_spin, width_value), (self.length_spin, element.length), (self.radius_spin, element.radius)):
                spin.blockSignals(True); spin.setValue(value); spin.blockSignals(False)
        self._sync_properties(element)

    def _width_changed(self, value: float) -> None:
        if self.canvas.project.editor_mode == "indoor":
            allowed = (5.0, 10.0, 15.0, 20.0, 25.0)
            snapped = min(allowed, key=lambda item: abs(item - value))
            if abs(snapped - value) > 1e-9:
                self.width_spin.blockSignals(True); self.width_spin.setValue(snapped); self.width_spin.blockSignals(False)
            value_metres = snapped / 100.0
        else:
            value_metres = value
        self.canvas.default_width = value_metres
        minimum_radius = value_metres / 2
        self.radius_spin.setMinimum(minimum_radius)
        radius = max(self.radius_spin.value(), minimum_radius)
        if radius != self.radius_spin.value():
            self.radius_spin.blockSignals(True)
            self.radius_spin.setValue(radius)
            self.radius_spin.blockSignals(False)
        self.canvas.default_radius = radius
        if self.canvas.selected:
            values = {"width": value_metres}
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

    def _mode_changed(self) -> None:
        mode = str(self.mode_combo.currentData())
        if mode == self.canvas.project.editor_mode:
            return
        if self.dirty:
            box = QMessageBox(
                QMessageBox.Icon.Question,
                self.tr_text("Unsaved changes"),
                self.tr_text("Save changes before continuing?"),
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
                self,
            )
            box.button(QMessageBox.StandardButton.Save).setText(self.tr_text("Save"))
            box.button(QMessageBox.StandardButton.Cancel).setText(self.tr_text("Cancel"))
            if (QMessageBox.StandardButton(box.exec()) != QMessageBox.StandardButton.Save
                    or not self.save()):
                self._apply_mode_ui()
                return
        length = self.canvas.project.hall_length
        width = self.canvas.project.hall_width
        self.canvas.set_project(TrackProject(length, width, editor_mode=mode))
        self.current_path = None
        self.dirty = False
        self._sync_hall_controls()
        self._apply_mode_ui()
        self._update_title()

    def _apply_mode_ui(self) -> None:
        indoor = self.canvas.project.editor_mode == "indoor"
        if hasattr(self, "mode_combo"):
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(self.canvas.project.editor_mode)))
            self.mode_combo.blockSignals(False)
        self.palette_mode_label.setText(self.tr_text("Indoor mode" if indoor else "Normal mode"))
        self.straight_action.setText(self.tr_text("Straight"))
        self.curve_label.setText(f" {self.tr_text('Curves:')} ")
        self.width_label.setText(f" {self.tr_text('Boundary width:' if indoor else 'Track width:')} ")
        self.width_spin.blockSignals(True)
        if indoor:
            self.width_spin.setRange(5, 25); self.width_spin.setSingleStep(5)
            self.width_spin.setDecimals(0); self.width_spin.setSuffix(" cm"); self.width_spin.setValue(10)
            self.canvas.default_width = 0.10
        else:
            self.width_spin.setRange(0.1, 20); self.width_spin.setSingleStep(0.1)
            self.width_spin.setDecimals(2); self.width_spin.setSuffix(" m"); self.width_spin.setValue(2)
            self.canvas.default_width = 2.0
        self.width_spin.blockSignals(False)
        if hasattr(self, "property_labels") and self.canvas.selected is None:
            self.property_labels["width"].setText(self.tr_text(
                "Boundary width:" if indoor else "Track width:"
            ))
            property_width = self.property_spins["width"]
            property_width.blockSignals(True)
            if indoor:
                property_width.setRange(5, 25); property_width.setSingleStep(5)
                property_width.setDecimals(0); property_width.setSuffix(" cm")
                property_width.setValue(10)
            else:
                property_width.setRange(0.1, 20); property_width.setSingleStep(0.1)
                property_width.setDecimals(2); property_width.setSuffix(" m")
                property_width.setValue(2)
            property_width.blockSignals(False)
        self.canvas.update()

    def _mark_dirty(self) -> None:
        self.dirty = True; self._update_title()

    def _project_changed(self) -> None:
        self._mark_dirty()
        if (hasattr(self, "mode_combo")
                and self.mode_combo.currentData() != self.canvas.project.editor_mode):
            self._apply_mode_ui()

    def _update_title(self) -> None:
        self.setWindowTitle(f"RC Track Designer {__release_name__}")
        project_name = ""
        if self.current_path:
            filename = self.current_path.name
            project_name = filename[:-9] if filename.lower().endswith(".rct.json") else self.current_path.stem
        self.canvas.set_project_name(project_name)

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
            element_name = tr("Straight" if element.kind == "straight" else "Curve")
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
            ("Choose an editing mode", "Normal mode creates filled track elements. Indoor mode replaces the palette with solid yellow barriers on an anthracite carpet. Before switching modes, unsaved work must be saved. The selected mode then starts with an empty track area using the same dimensions."),
            ("Add magnet points", "In indoor mode, right-click a straight barrier to add a magnet point. Multiple straights and curves may meet at every barrier connector, including already connected endpoints. Drag a connected endpoint to move the joint; adjacent elements adjust their geometry while their opposite connectors stay fixed. Added points can be dragged along their straight. Right-click an added magnet point to remove it."),
            ("Place and connect elements", "Choose a straight or neutral curve angle from the upper palette. Click an empty position for a free element, or click a blue free connector to continue the track automatically. Curves rotate through 360 degrees and can snap using either endpoint. Green connectors are connected; the orange connector is active."),
            ("Select and edit", "Click an element to select and drag it. Hold Shift while clicking, or draw a selection rectangle, to select several elements. Use the properties panel for exact dimensions and positions. A selected segment rotates 5 degrees with the Left and Right arrow keys; hold a key down for continuous rotation. Right-click a selected segment to delete the selection. Esc cancels placement or clears the selection."),
            ("Close gaps and move groups", "Drag the free connector of a one-sided connected element to change its length, radius or curve angle. Release it near a compatible connector to close the gap. A selected connected group moves as one rigid unit and can snap to an external free connector."),
            ("Close an open track", "Select the two free connectors of one open track with Ctrl+click. Choose Edit > Close track or use the right-click menu. The preview lists local length, radius and angle adjustments; nothing changes until you confirm."),
            ("Navigate and organise", "Zoom with the mouse wheel. Pan with the middle mouse button or Space plus the left mouse button. Drag guides from the rulers; remove a guide with the right mouse button."),
            ("Correct mistakes and save", "Use Ctrl+Z and Ctrl+Y for undo and redo. Ctrl+C and Ctrl+V copy and paste selected elements. Save projects as JSON files from the File menu. Older projects remain loadable; stale connection references are released without removing track elements."),
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

    @staticmethod
    def _license_text() -> str:
        source_license = Path(__file__).resolve().parents[2] / "LICENSE.txt"
        if source_license.is_file():
            return source_license.read_text(encoding="utf-8")
        try:
            candidates = distribution_files("rc-track-designer") or ()
            for candidate in candidates:
                if candidate.name == "LICENSE.txt":
                    installed_license = Path(candidate.locate())
                    if installed_license.is_file():
                        return installed_license.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            pass
        return "License file LICENSE.txt was not found."

    def show_license(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr_text("License"))
        dialog.resize(760, 650)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser(dialog)
        browser.setObjectName("licenseText")
        browser.setPlainText(self._license_text())
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.tr_text("Close")
        )
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
            (self.license_action, "License"),
            (self.about_action, "About RC Track Designer"),
            (self.straight_action, "Straight"), (self.undo_action, "Undo"), (self.redo_action, "Redo"),
        )
        for action, source in actions: action.setText(tr(source))
        self.mode_label.setText(f" {tr('Editing mode:')} ")
        current_mode = self.canvas.project.editor_mode
        self.mode_combo.blockSignals(True)
        self.mode_combo.setItemText(self.mode_combo.findData("normal"), tr("Normal mode"))
        self.mode_combo.setItemText(self.mode_combo.findData("indoor"), tr("Indoor mode"))
        self.mode_combo.setCurrentIndex(self.mode_combo.findData(current_mode))
        self.mode_combo.blockSignals(False)
        self.rotate_left_button.setText(tr("5° left"))
        self.rotate_left_button.setToolTip(tr("Rotate 5° left"))
        self.rotate_right_button.setText(tr("5° right"))
        self.rotate_right_button.setToolTip(tr("Rotate 5° right"))
        self.delete_button.setText(tr("Delete selection"))
        for menu, source in ((self.file_menu, "File"), (self.edit_menu, "Edit"),
                             (self.view_menu, "Settings"), (self.help_menu, "Help")):
            menu.setTitle(tr(source))
        self.elements_label.setText(f" {tr('Elements:')} ")
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
        self._apply_mode_ui()
        if self.canvas.selected and self.canvas.selected.element_type == "boundary":
            self.property_labels["width"].setText(tr("Boundary width:"))
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
            self._apply_mode_ui()
            self.current_path = None; self.dirty = False; self._update_title()

    def open_project(self) -> None:
        if not self._can_discard(): return
        filename, _ = QFileDialog.getOpenFileName(self, self.tr_text("Open project"), "", "RC Track Designer (*.rct.json *.json)")
        if not filename: return
        try: project = load_project(filename)
        except Exception as error: QMessageBox.critical(self, self.tr_text("Open failed"), str(error)); return
        self.canvas.set_project(project); self._sync_hall_controls(); self._apply_mode_ui(); self.current_path = Path(filename); self.dirty = False; self._update_title()

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
        QMessageBox.about(
            self,
            self.tr_text("About RC Track Designer"),
            f"RC Track Designer {__release_name__}\n\n{description}",
        )
