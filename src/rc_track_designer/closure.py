"""General local geometry solver for closing two free track connectors."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import hypot, radians

from .model import ConnectorRef, Point, Pose, TrackElement, TrackProject


@dataclass
class ClosureProposal:
    project: TrackProject
    connectors: tuple[ConnectorRef, ConnectorRef]
    changed: list[tuple[str, str, float, float]]
    position_error: float
    angle_error: float


def _angle_delta(first: float, second: float) -> float:
    return (first - second + 180) % 360 - 180


def _other(connection, connector: ConnectorRef) -> ConnectorRef:
    return connection.second if connection.first == connector else connection.first


def _ordered_path(project: TrackProject, first: ConnectorRef,
                  second: ConnectorRef) -> list[tuple[TrackElement, str]] | None:
    """Return elements traversed from the first free connector to the second."""
    if first.element_id == second.element_id:
        return None
    result: list[tuple[TrackElement, str]] = []
    current = first
    visited: set[str] = set()
    while current.element_id not in visited:
        visited.add(current.element_id)
        element = project.element_by_id(current.element_id)
        if element is None:
            return None
        result.append((element, current.endpoint))
        exit_connector = ConnectorRef(
            element.id, "end" if current.endpoint == "start" else "start"
        )
        if exit_connector == second:
            return result
        connection = project.connection_for(exit_connector)
        if connection is None:
            return None
        current = _other(connection, exit_connector)
    return None


def _solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    size = len(vector)
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-14:
            return None
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if abs(factor) > 1e-16:
                augmented[row] = [a - factor * b for a, b in
                                  zip(augmented[row], augmented[column])]
    return [augmented[row][-1] for row in range(size)]


def _layout(elements: list[tuple[TrackElement, str]], anchor: Pose,
            variables: list[tuple[int, str]], values: list[float]) -> Pose:
    for (index, name), value in zip(variables, values):
        setattr(elements[index][0], name, value)
    pose = anchor
    previous_exit: ConnectorRef | None = None
    for element, entry in elements:
        entry_connector = ConnectorRef(element.id, entry)
        if previous_exit is not None:
            pose = TrackProject.connection_target_pose(
                entry_connector, previous_exit, pose
            )
        element.align_endpoint(entry, pose)
        exit_endpoint = "end" if entry == "start" else "start"
        pose = element.pose_at(exit_endpoint)
        previous_exit = ConnectorRef(element.id, exit_endpoint)
    return pose


def _bounds(element: TrackElement, name: str) -> tuple[float, float]:
    if name == "length":
        return 0.1, 200.0
    if name == "radius":
        return element.minimum_centerline_radius, 200.0
    return 1.0, 90.0


def _attempt(project: TrackProject, path: list[tuple[TrackElement, str]],
             target: Pose, window_size: int):
    working = deepcopy(project)
    ids = [element.id for element, _entry in path[-window_size:]]
    entries = [entry for _element, entry in path[-window_size:]]
    elements = [(working.element_by_id(element_id), entry)
                for element_id, entry in zip(ids, entries)]
    if any(element is None for element, _entry in elements):
        return None
    anchor = elements[0][0].pose_at(elements[0][1])
    variables: list[tuple[int, str]] = []
    initial: list[float] = []
    scales: list[float] = []
    limits: list[tuple[float, float]] = []
    for index, (element, _entry) in enumerate(elements):
        names = ("length",) if element.kind == "straight" else ("radius", "angle_deg")
        for name in names:
            lower, upper = _bounds(element, name)
            value = getattr(element, name)
            if value < lower - 1e-9:
                continue  # Preserve, but do not alter, legacy invalid geometry.
            variables.append((index, name))
            initial.append(value)
            scales.append(10.0 if name == "angle_deg" else max(0.5, value * 0.25))
            limits.append((lower, upper))
    if not variables:
        return None

    normalized = [0.0] * len(variables)

    def actual(z):
        return [max(lower, min(upper, base + scale * value))
                for value, base, scale, (lower, upper)
                in zip(z, initial, scales, limits)]

    def residual(z):
        end = _layout(elements, anchor, variables, actual(z))
        return [end.point.x - target.point.x,
                end.point.y - target.point.y,
                radians(_angle_delta(end.heading_deg, target.heading_deg)) * 2.0]

    damping = 1e-3
    current = residual(normalized)
    current_cost = sum(value * value for value in current)
    for _iteration in range(120):
        if current_cost < 1e-14:
            break
        epsilon = 1e-4
        jacobian = [[0.0] * len(normalized) for _ in range(3)]
        for column in range(len(normalized)):
            trial = normalized[:]
            trial[column] += epsilon
            shifted = residual(trial)
            for row in range(3):
                jacobian[row][column] = (shifted[row] - current[row]) / epsilon
        normal = [[sum(jacobian[row][i] * jacobian[row][j] for row in range(3))
                   + (damping if i == j else 0.0)
                   for j in range(len(normalized))] for i in range(len(normalized))]
        gradient = [-sum(jacobian[row][i] * current[row] for row in range(3))
                    for i in range(len(normalized))]
        step = _solve_linear(normal, gradient)
        if step is None:
            break
        candidate = [value + delta for value, delta in zip(normalized, step)]
        candidate_residual = residual(candidate)
        candidate_cost = sum(value * value for value in candidate_residual)
        if candidate_cost < current_cost:
            normalized, current, current_cost = candidate, candidate_residual, candidate_cost
            damping = max(1e-9, damping / 3)
        else:
            damping = min(1e9, damping * 10)

    final_values = actual(normalized)
    final_pose = _layout(elements, anchor, variables, final_values)
    position_error = hypot(final_pose.point.x - target.point.x,
                           final_pose.point.y - target.point.y)
    angle_error = abs(_angle_delta(final_pose.heading_deg, target.heading_deg))
    if position_error > 1e-5 or angle_error > 1e-4:
        return None
    if not all(working.element_fits_hall(element) for element, _entry in elements):
        return None
    own = ConnectorRef(elements[-1][0].id,
                       "end" if elements[-1][1] == "start" else "start")
    changed = []
    for (index, name), before, after in zip(variables, initial, final_values):
        if abs(before - after) > 1e-6:
            changed.append((elements[index][0].id, name, before, after))
    return working, own, changed, position_error, angle_error


def propose_closure(project: TrackProject, first: ConnectorRef,
                    second: ConnectorRef) -> ClosureProposal | None:
    if not project.is_free(first) or not project.is_free(second):
        return None
    for target_connector, adjustable_connector in ((first, second), (second, first)):
        path = _ordered_path(project, target_connector, adjustable_connector)
        if not path:
            continue
        target = project.connector_alignment_pose(
            adjustable_connector, target_connector
        )
        for size in range(1, min(8, len(path)) + 1):
            attempt = _attempt(project, path, target, size)
            if attempt is None:
                continue
            working, own, changed, position_error, angle_error = attempt
            try:
                working.connect(own, target_connector)
            except ValueError:
                continue
            return ClosureProposal(working, (first, second), changed,
                                   position_error, angle_error)
    return None
