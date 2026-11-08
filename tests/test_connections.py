from math import isclose

import pytest

from rc_track_designer.model import ConnectorRef, Point, Pose, TrackElement, TrackProject


def test_connect_requires_free_opposite_endpoints():
    first = TrackElement("straight", Point(0, 0), length=5)
    second = TrackElement("straight", Point(5, 0), length=5)
    project = TrackProject(elements=[first, second])
    connection = project.connect(ConnectorRef(first.id, "end"), ConnectorRef(second.id, "start"))
    assert project.connection_for(ConnectorRef(first.id, "end")) == connection
    with pytest.raises(ValueError):
        project.connect(ConnectorRef(first.id, "end"), ConnectorRef(second.id, "start"))


def test_same_endpoint_direction_is_rejected():
    first = TrackElement("straight", Point(0, 0))
    second = TrackElement("straight", Point(5, 0))
    project = TrackProject(elements=[first, second])
    with pytest.raises(ValueError, match="start-to-end"):
        project.connect(ConnectorRef(first.id, "start"), ConnectorRef(second.id, "start"))


def test_contradictory_position_or_tangent_is_rejected():
    first = TrackElement("straight", Point(0, 0), length=5)
    displaced = TrackElement("straight", Point(5.1, 0), heading_deg=0)
    wrong_heading = TrackElement("straight", Point(5, 0), heading_deg=30)
    project = TrackProject(elements=[first, displaced, wrong_heading])
    with pytest.raises(ValueError, match="position and tangent"):
        project.connect(ConnectorRef(first.id, "end"), ConnectorRef(displaced.id, "start"))
    with pytest.raises(ValueError, match="position and tangent"):
        project.connect(ConnectorRef(first.id, "end"), ConnectorRef(wrong_heading.id, "start"))


def test_align_curve_end_to_arbitrary_pose():
    curve = TrackElement("left", Point(0, 0), radius=5, angle_deg=45)
    curve.align_endpoint("end", Pose(Point(12, 9), 120))
    assert isclose(curve.end_pose.point.x, 12, abs_tol=1e-9)
    assert isclose(curve.end_pose.point.y, 9, abs_tol=1e-9)
    assert isclose(curve.end_pose.heading_deg, 120, abs_tol=1e-9)


def test_removing_element_frees_neighbour_connector():
    first = TrackElement("straight", Point(0, 0))
    second = TrackElement("straight", Point(5, 0))
    project = TrackProject(elements=[first, second])
    neighbour = ConnectorRef(first.id, "end")
    project.connect(neighbour, ConnectorRef(second.id, "start"))
    project.remove_element(second)
    assert project.is_free(neighbour)


def test_complete_road_surface_must_fit_inside_hall():
    project = TrackProject(20, 12)
    assert project.element_fits_hall(TrackElement("straight", Point(1, 1), width=2, length=10))
    assert not project.element_fits_hall(TrackElement("straight", Point(0.99, 1), width=2, length=10))
    assert not project.element_fits_hall(TrackElement("straight", Point(15, 11), width=2, length=6))
    assert not project.element_fits_hall(TrackElement("left", Point(15, 6), width=2, radius=5, angle_deg=90))


def test_translation_is_clamped_to_complete_road_surface():
    project = TrackProject(20, 12)
    element = TrackElement("straight", Point(5, 6), heading_deg=0, width=2, length=5)
    dx, dy = project.clamp_translation(element, 100, -100)
    element.moved(dx, dy)
    assert element.start == Point(14, 1)
    assert project.element_fits_hall(element)
