import json
import pytest
from rc_track_designer.model import ConnectorRef, Point, TrackElement, TrackProject
from rc_track_designer.storage import load_project, save_project

def test_project_roundtrip(tmp_path):
    first = TrackElement("left", Point(4, 6), 15, 2, radius=7, angle_deg=55)
    second = TrackElement("straight", first.end_pose.point, first.end_pose.heading_deg)
    project = TrackProject(42, 23, [first, second], guides_x=[3.5, 12.0], guides_y=[4.5])
    project.connect(ConnectorRef(first.id, "end"), ConnectorRef(second.id, "start"))
    target = tmp_path / "track.rct.json"
    save_project(project, target)
    assert load_project(target) == project
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["app_version"] == "0.3.0"
    assert data["format_version"] == 3
    assert data["guides"] == {"x": [3.5, 12.0], "y": [4.5]}

def test_v1_project_without_connections_remains_loadable(tmp_path):
    target = tmp_path / "old.rct.json"
    target.write_text(json.dumps({"format": "rc-track-designer", "format_version": 1,
        "hall": {"length": 30, "width": 20}, "elements": []}), encoding="utf-8")
    loaded = load_project(target)
    assert loaded.hall_length == 30
    assert loaded.connections == []
    assert loaded.guides_x == [] and loaded.guides_y == []

def test_v2_project_remains_loadable(tmp_path):
    target = tmp_path / "v2.rct.json"
    target.write_text(json.dumps({"format": "rc-track-designer", "format_version": 2,
        "hall": {"length": 30, "width": 20}, "elements": [],
        "connections": [], "guides": {"x": [2.5], "y": [3.0]}}), encoding="utf-8")
    loaded = load_project(target)
    assert loaded.guides_x == [2.5]
    assert loaded.guides_y == [3.0]

def test_same_end_connection_roundtrip(tmp_path):
    first = TrackElement("straight", Point(3, 4), heading_deg=0, length=4)
    second = TrackElement("straight", Point(3, 4), heading_deg=180, length=2)
    project = TrackProject(20, 12, [first, second])
    project.connect(ConnectorRef(first.id, "start"), ConnectorRef(second.id, "start"))
    target = tmp_path / "same-end.rct.json"

    save_project(project, target)

    loaded = load_project(target)
    assert loaded == project
    assert loaded.connections[0].first.endpoint == "start"
    assert loaded.connections[0].second.endpoint == "start"

def test_unknown_format_is_rejected(tmp_path):
    target = tmp_path / "future.json"
    target.write_text('{"format":"rc-track-designer","format_version":99}', encoding="utf-8")
    with pytest.raises(ValueError, match="Projektformat"): load_project(target)
