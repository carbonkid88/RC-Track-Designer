import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QFormLayout

from rc_track_designer.model import ConnectorRef, Point, TrackElement
from rc_track_designer.ui import MainWindow


def test_logo_is_scaled_and_placed_at_right_end_of_main_toolbar():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    app.processEvents()
    window._position_logo_panel()
    pixmap = window.logo_label.pixmap()

    assert pixmap is not None
    assert not pixmap.isNull()
    assert pixmap.width() > pixmap.height()
    assert window.logo_panel.geometry().right() == window.width() - 1
    assert window.logo_panel.geometry().top() == window.main_toolbar.geometry().top()
    assert window.logo_panel.geometry().bottom() == window.palette_toolbar.geometry().bottom()
    assert window.logo_label.isVisible()
    source_ratio = window.logo_source.width() / window.logo_source.height()
    rendered_ratio = window.logo_label.pixmap().width() / window.logo_label.pixmap().height()
    assert abs(source_ratio - rendered_ratio) / source_ratio < 0.02
    window.close()


def test_main_toolbar_keeps_edit_buttons_visible_at_laptop_width():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    app.processEvents()

    for button in (window.rotate_left_button, window.rotate_right_button, window.delete_button):
        assert button.isVisible()
        assert button.geometry().right() < window.logo_panel.geometry().left()
    assert window.rotate_left_button.width() >= 86
    assert window.rotate_right_button.width() >= 86
    assert window.area_dimensions_label.isVisible()
    assert window.area_dimensions_label.text() == "Streckenbereich"
    window.close()


def test_edit_button_labels_do_not_change_with_action_state():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    labels = (window.rotate_left_button.text(), window.rotate_right_button.text())

    window.rotate_left_action.setEnabled(not window.rotate_left_action.isEnabled())
    window.rotate_right_action.setEnabled(not window.rotate_right_action.isEnabled())
    app.processEvents()

    assert (window.rotate_left_button.text(), window.rotate_right_button.text()) == labels
    assert labels == ("5° links", "5° rechts")
    window.close()


def test_curve_angle_is_first_property_below_element_type():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    form = window.properties_dock.widget().layout()

    assert isinstance(form, QFormLayout)
    row, role = form.getWidgetPosition(window.property_spins["angle_deg"])
    assert row == 1
    assert role == QFormLayout.ItemRole.FieldRole
    assert not window.property_spins["angle_deg"].isHidden()
    assert window.property_spins["angle_deg"].value() == 0

    window._sync_properties(TrackElement("straight", Point(1, 1)))
    assert not window.property_spins["angle_deg"].isHidden()
    assert window.property_spins["angle_deg"].value() == 0
    assert not window.property_spins["angle_deg"].isEnabled()
    window._sync_properties(TrackElement("left", Point(1, 1), angle_deg=30))
    assert window.property_spins["angle_deg"].value() == 30
    assert window.property_spins["angle_deg"].isEnabled()
    window.close()


def test_palette_offers_one_neutral_curve_row_and_properties_hide_bend_side():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.curve_label.text().strip() == "Kurven:"
    assert len(window.curve_actions) == 18
    window.curve_actions[6].trigger()
    assert window.canvas.placement == ("curve", 35)

    window._sync_properties(TrackElement("left", Point(4, 4), angle_deg=35))
    assert window.element_type_value.text() == "Kurve"
    window._sync_properties(TrackElement("right", Point(4, 4), angle_deg=35))
    assert window.element_type_value.text() == "Kurve"
    window.close()


def test_properties_dock_can_be_restored_from_view_menu():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    app.processEvents()

    assert window.properties_dock.isVisible()
    window.properties_toggle_action.trigger()
    app.processEvents()
    assert not window.properties_dock.isVisible()
    window.properties_toggle_action.trigger()
    app.processEvents()
    assert window.properties_dock.isVisible()
    assert window.properties_toggle_action in window.view_menu.actions()
    window.close()


def test_window_branding_and_project_name_are_kept_separate():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.windowTitle() == "RC Track Designer"
    assert not window.windowIcon().isNull()
    assert window.canvas.project_name == ""

    window.current_path = Path("Herrenhaide2.rct.json")
    window.dirty = True
    window._update_title()

    assert window.windowTitle() == "RC Track Designer"
    assert window.canvas.project_name == "Herrenhaide2"
    window.dirty = False
    window.close()


def test_view_menu_is_presented_as_settings_menu():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.view_menu.title() == window.tr_text("Settings")
    assert window.settings_action in window.view_menu.actions()
    window.close()


def test_about_dialog_identifies_beta_two(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    captured = {}
    monkeypatch.setattr(
        "rc_track_designer.ui.QMessageBox.about",
        lambda parent, title, text: captured.update(title=title, text=text),
    )

    window.about()

    assert "RC Track Designer 0.4.0 Beta 2" in captured["text"]
    window.close()


def test_copy_paste_shortcuts_and_half_metre_straight_steps():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.copy_action.shortcut() == QKeySequence(QKeySequence.StandardKey.Copy)
    assert window.paste_action.shortcut() == QKeySequence(QKeySequence.StandardKey.Paste)
    assert window.length_spin.singleStep() == 0.5
    assert window.radius_spin.singleStep() == 0.5
    assert window.property_spins["length"].singleStep() == 0.5
    assert window.property_spins["radius"].singleStep() == 0.5
    window.close()


def test_track_width_keeps_curve_radius_above_valid_inner_edge():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.width_spin.setValue(6)

    assert window.radius_spin.minimum() == 3.0
    assert window.radius_spin.value() >= 3.0
    assert window.canvas.default_radius >= 3.0

    curve = TrackElement("left", Point(5, 5), width=2, radius=2, angle_deg=45)
    window.canvas.project.elements.append(curve)
    window.canvas.selected = curve
    window.canvas.selected_ids = {curve.id}
    window._sync_properties(curve)
    assert window.property_spins["radius"].minimum() == 1.0
    window.close()


def test_escape_clears_selection_even_when_toolbar_control_has_focus():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    element = TrackElement("straight", Point(4, 5), length=4)
    window.canvas.project.elements.append(element)
    window.canvas.selected = element
    window.canvas.selected_ids = {element.id}
    window.show()
    window.width_spin.setFocus()
    app.processEvents()

    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    QTest.keyClick(window.width_spin, Qt.Key.Key_Escape)
    app.processEvents()

    assert window.canvas.selected is None
    assert window.canvas.selected_ids == set()
    window.close()


def test_help_menu_contains_user_guide_with_f1_shortcut():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.guide_action in window.help_menu.actions()
    assert window.guide_action.text() == "Bedienungsanleitung"
    assert window.guide_action.shortcut() == QKeySequence("F1")
    assert window.license_action in window.help_menu.actions()
    assert window.license_action.text() == "Lizenz"
    window.close()


def test_integrated_license_uses_repository_license_file():
    license_path = Path(__file__).resolve().parents[1] / "LICENSE.txt"

    assert MainWindow._license_text() == license_path.read_text(encoding="utf-8")
    assert "nicht-kommerzielle Zwecke" in MainWindow._license_text()
    assert "non-commercial purposes" in MainWindow._license_text()


def test_close_track_action_requires_two_selected_free_connectors():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    first = TrackElement("straight", Point(4, 5), length=3)
    second = TrackElement("straight", Point(12, 5), length=3)
    window.canvas.project.elements.extend([first, second])

    assert not window.close_track_action.isEnabled()
    window.canvas.toggle_closure_connector(ConnectorRef(first.id, "start"))
    assert not window.close_track_action.isEnabled()
    window.canvas.toggle_closure_connector(ConnectorRef(second.id, "end"))
    assert window.close_track_action.isEnabled()
    window.close()
