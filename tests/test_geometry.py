from math import isclose
import pytest
from rc_track_designer.model import Point, TrackElement, TrackProject


def test_curve_radius_may_equal_half_track_width_without_crossing_center():
    curve = TrackElement("left", Point(5, 5), width=2, radius=1, angle_deg=90)

    assert curve.minimum_centerline_radius == 1
    assert curve.has_valid_road_geometry

def assert_point(point, x, y):
    assert isclose(point.x, x, abs_tol=1e-9)
    assert isclose(point.y, y, abs_tol=1e-9)

def test_straight_end_pose_uses_heading_and_metres():
    element = TrackElement("straight", Point(1, 2), heading_deg=90, length=6)
    assert_point(element.end_pose.point, 1, 8)
    assert element.end_pose.heading_deg == 90

def test_left_quarter_circle_uses_centerline_radius():
    element = TrackElement("left", Point(0, 0), heading_deg=0, radius=5, angle_deg=90)
    assert_point(element.end_pose.point, 5, 5)
    assert element.end_pose.heading_deg == 90

def test_right_quarter_circle():
    element = TrackElement("right", Point(0, 0), heading_deg=0, radius=5, angle_deg=90)
    assert_point(element.end_pose.point, 5, -5)
    assert element.end_pose.heading_deg == 270

def test_curve_chaining_matches_start_and_end_tangents():
    first = TrackElement("left", Point(2, 3), heading_deg=30, radius=4, angle_deg=45)
    second = TrackElement("straight", first.end_pose.point, heading_deg=first.end_pose.heading_deg, length=3)
    assert second.start_pose == first.end_pose

def test_centerline_samples_include_exact_endpoints():
    element = TrackElement("right", Point(3, 4), heading_deg=12, radius=7, angle_deg=35)
    points = element.centerline_points()
    assert points[0] == element.start
    assert points[-1] == element.end_pose.point
    assert len(points) > 2

@pytest.mark.parametrize("kind", ["straight", "left", "right"])
def test_element_json_roundtrip(kind):
    original = TrackElement(kind, Point(1.25, 9.5), 17, 2.4, 8, 3.2, 25)
    assert TrackElement.from_dict(original.to_dict()) == original


@pytest.mark.parametrize("kind", ["straight", "left", "right"])
def test_rotation_keeps_centerline_midpoint_fixed(kind):
    element = TrackElement(kind, Point(7, 8), heading_deg=23, radius=4, angle_deg=35)
    before = element.centerline_midpoint
    element.rotate(137)
    after = element.centerline_midpoint
    assert isclose(after.x, before.x, abs_tol=1e-9)
    assert isclose(after.y, before.y, abs_tol=1e-9)


def test_old_element_without_rotation_reference_uses_loaded_heading():
    data = TrackElement("left", Point(1, 2), heading_deg=137, angle_deg=35).to_dict()
    data.pop("rotation_reference_deg")
    loaded = TrackElement.from_dict(data)
    assert loaded.rotation_reference_deg == 137

def test_invalid_dimensions_are_rejected():
    with pytest.raises(ValueError): TrackProject(0, 20)
    with pytest.raises(ValueError): TrackElement("straight", Point(0, 0), width=-1)
