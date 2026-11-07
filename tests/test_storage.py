import json
import pytest
from rc_track_designer.model import Point, TrackElement, TrackProject
from rc_track_designer.storage import load_project, save_project

def test_project_roundtrip(tmp_path):
    project = TrackProject(42, 23, [TrackElement("left", Point(4, 6), 15, 2, radius=7, angle_deg=55)])
    target = tmp_path / "track.rct.json"
    save_project(project, target)
    assert load_project(target) == project
    assert json.loads(target.read_text(encoding="utf-8"))["app_version"] == "0.1.0"

def test_unknown_format_is_rejected(tmp_path):
    target = tmp_path / "future.json"
    target.write_text('{"format":"rc-track-designer","format_version":99}', encoding="utf-8")
    with pytest.raises(ValueError, match="Projektformat"): load_project(target)

