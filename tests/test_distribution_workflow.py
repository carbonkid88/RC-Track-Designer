import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialog

import rc_track_designer.ui as ui_module
from rc_track_designer.model import Point, TrackElement, TrackProject
from rc_track_designer.storage import load_project
from rc_track_designer.ui import MainWindow


def test_beta_workflow_uses_user_settings_and_external_project_path(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    settings_path = tmp_path / "settings.ini"
    monkeypatch.setattr(
        ui_module, "QSettings",
        lambda: QSettings(str(settings_path), QSettings.Format.IniFormat),
    )
    window = MainWindow()

    class ValueField:
        def __init__(self, value):
            self._value = value

        def value(self):
            return self._value

    class AcceptedNewProjectDialog:
        def __init__(self, _tr, _parent):
            self.length = ValueField(25)
            self.width = ValueField(12)

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ui_module, "NewProjectDialog", AcceptedNewProjectDialog)
    window.new_project()
    assert window.canvas.project.hall_length == 25
    assert window.canvas.project.hall_width == 12

    window.translations.set_language("en")
    window.retranslate_ui()
    assert window.file_menu.title() == "File"
    window.translations.set_language("de")
    window.retranslate_ui()
    assert window.file_menu.title() == "Datei"

    for theme in ("light", "dark"):
        window.theme = theme
        window.apply_appearance()
        assert window.theme == theme

    straight = TrackElement("straight", Point(3, 4), length=5)
    window.canvas.project.elements.append(straight)
    window.canvas.selected = straight
    window.canvas.selected_ids = {straight.id}
    window.canvas.rotate_selected(5)
    assert window.canvas.undo_stack.count() == 1
    window.canvas.undo_stack.undo()
    assert window.canvas.selected.heading_deg == 0
    window.canvas.undo_stack.redo()
    assert window.canvas.selected.heading_deg == 5

    project_path = tmp_path / "beta-workflow.rct.json"
    monkeypatch.setattr(
        ui_module.QFileDialog, "getSaveFileName",
        lambda *args: (str(project_path), "RC Track Designer (*.rct.json)"),
    )
    window.current_path = None
    assert window.save_as()
    assert load_project(project_path) == window.canvas.project
    assert project_path.parent != Path(__file__).resolve().parents[1]

    monkeypatch.setattr(
        ui_module.QFileDialog, "getOpenFileName",
        lambda *args: (str(project_path), "RC Track Designer (*.rct.json *.json)"),
    )
    window.canvas.set_project(TrackProject())
    window.current_path = None
    window.open_project()
    assert len(window.canvas.project.elements) == 1
    assert window.canvas.project.elements[0].heading_deg == 5

    window.settings.setValue("theme", "dark")
    window.settings.sync()
    assert settings_path.is_file()
    assert settings_path.parent != Path(__file__).resolve().parents[1]
    window.close()
