import json
import pytest
from rc_track_designer.model import ConnectorRef, Point, TrackElement, TrackProject
from rc_track_designer.storage import load_project, save_project

def test_project_roundtrip(tmp_path):
    first = TrackElement("left", Point(4, 6), 15, 2, radius=7, angle_deg=55)
    second = TrackElement("straight", first.end_pose.point, first.end_pose.heading_deg)
    project = TrackProject(42, 23, [first, second])
    project.connect(ConnectorRef(first.id, "end"), ConnectorRef(second.id, "start"))
    target = tmp_path / "track.rct.json"
    save_project(project, target)
    assert load_project(target) == project
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["app_version"] == "0.2.0"
    assert data["format_version"] == 2

def test_v1_project_without_connections_remains_loadable(tmp_path):
    target = tmp_path / "old.rct.json"
    target.write_text(json.dumps({"format": "rc-track-designer", "format_version": 1,
        "hall": {"length": 30, "width": 20}, "elements": []}), encoding="utf-8")
    loaded = load_project(target)
    assert loaded.hall_length == 30
    assert loaded.connections == []

def test_unknown_format_is_rejected(tmp_path):
    target = tmp_path / "future.json"
    target.write_text('{"format":"rc-track-designer","format_version":99}', encoding="utf-8")
    with pytest.raises(ValueError, match="Projektformat"): load_project(target)
