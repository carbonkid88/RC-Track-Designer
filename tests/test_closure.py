from rc_track_designer.closure import propose_closure
from rc_track_designer.model import ConnectorRef, Point, TrackElement, TrackProject


def rounded_open_loop() -> tuple[TrackProject, ConnectorRef, ConnectorRef]:
    project = TrackProject(30, 20)
    specifications = [
        ("straight", {"length": 8}),
        ("left", {"radius": 2, "angle_deg": 90}),
        ("straight", {"length": 4}),
        ("left", {"radius": 2, "angle_deg": 90}),
        ("straight", {"length": 8}),
        ("left", {"radius": 2, "angle_deg": 90}),
        ("straight", {"length": 3.8}),
        ("left", {"radius": 2, "angle_deg": 90}),
    ]
    for index, (kind, values) in enumerate(specifications):
        if index == 0:
            element = TrackElement(kind, Point(5, 3), width=1, **values)
        else:
            previous = project.elements[-1]
            element = TrackElement(kind, previous.end_pose.point,
                                   previous.end_pose.heading_deg, width=1, **values)
        project.elements.append(element)
        if index:
            project.connect(ConnectorRef(project.elements[-2].id, "end"),
                            ConnectorRef(element.id, "start"))
    return (project, ConnectorRef(project.elements[0].id, "start"),
            ConnectorRef(project.elements[-1].id, "end"))


def test_general_solver_closes_open_loop_with_local_adjustments():
    project, first, second = rounded_open_loop()

    proposal = propose_closure(project, first, second)

    assert proposal is not None
    assert len(proposal.project.connections) == len(project.elements)
    assert proposal.position_error < 1e-5
    assert proposal.angle_error < 1e-4
    assert proposal.changed
    proposal.project.validate_connections()


def test_solver_does_not_modify_original_project_during_preview():
    project, first, second = rounded_open_loop()
    original_length = project.elements[-2].length

    proposal = propose_closure(project, first, second)

    assert proposal is not None
    assert project.elements[-2].length == original_length
    assert len(project.connections) == len(project.elements) - 1
