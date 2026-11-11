import os
from copy import deepcopy
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from rc_track_designer.model import ConnectorRef, Point, TrackElement, TrackProject
from rc_track_designer.printing import (
    LayoutPrintPreviewDialog,
    PrintOptions,
    configure_printer,
    pdf_printer,
    render_project,
    render_project_to_printer,
)
from rc_track_designer.ui import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module", autouse=True)
def application():
    app = _app()
    yield app


def _classic_project(length=30.0, width=20.0):
    return TrackProject(
        length,
        width,
        [
            TrackElement("straight", Point(3, 5), length=8, width=2),
            TrackElement(
                "left", Point(11, 5), radius=4, angle_deg=90, width=2
            ),
        ],
    )


def _indoor_project():
    return TrackProject(
        25,
        12,
        [
            TrackElement(
                "straight",
                Point(2, 2),
                length=12,
                width=0.1,
                element_type="boundary",
            ),
            TrackElement(
                "left",
                Point(8, 7),
                radius=2,
                angle_deg=90,
                width=0.1,
                element_type="boundary",
            ),
        ],
        editor_mode="indoor",
    )


def _render(project, options, size=(1200, 800)):
    image = QImage(size[0], size[1], QImage.Format.Format_ARGB32)
    image.fill(QColor("#cc00cc"))
    painter = QPainter(image)
    metrics = render_project(
        painter,
        QRectF(image.rect()),
        project,
        options,
        title="Test layout",
        dpi=96,
    )
    painter.end()
    return image, metrics


@pytest.mark.parametrize(
    ("paper", "orientation", "page_id", "page_orientation"),
    [
        ("A4", "portrait", QPageSize.PageSizeId.A4, QPageLayout.Orientation.Portrait),
        ("A4", "landscape", QPageSize.PageSizeId.A4, QPageLayout.Orientation.Landscape),
        ("A3", "portrait", QPageSize.PageSizeId.A3, QPageLayout.Orientation.Portrait),
        ("A3", "landscape", QPageSize.PageSizeId.A3, QPageLayout.Orientation.Landscape),
    ],
)
def test_printer_supports_a4_a3_and_both_orientations(
    paper, orientation, page_id, page_orientation
):
    printer = QPrinter()
    configure_printer(printer, PrintOptions(paper_size=paper, orientation=orientation))

    assert printer.pageLayout().pageSize().id() == page_id
    assert printer.pageLayout().orientation() == page_orientation


@pytest.mark.parametrize("project", [_classic_project(), _indoor_project()])
@pytest.mark.parametrize("size", [(700, 1000), (1400, 700)])
def test_complete_layout_is_fitted_without_distortion(project, size):
    _, metrics = _render(project, PrintOptions(), size)

    x_scale = metrics.layout_rect.width() / project.hall_length
    y_scale = metrics.layout_rect.height() / project.hall_width
    assert x_scale == pytest.approx(y_scale)
    assert metrics.content_rect.contains(metrics.layout_rect)


def test_indoor_color_and_grayscale_use_expected_page_backgrounds():
    project = _indoor_project()
    color_image, color_metrics = _render(
        project, PrintOptions(grayscale=False, show_grid=False)
    )
    gray_image, gray_metrics = _render(
        project, PrintOptions(grayscale=True, show_grid=False)
    )
    color_center = color_metrics.layout_rect.center().toPoint()
    gray_center = gray_metrics.layout_rect.center().toPoint()

    assert color_image.pixelColor(color_center) == QColor("#34383E")
    assert gray_image.pixelColor(gray_center) == QColor("#ffffff")


def test_classic_grayscale_prints_only_dark_road_contours_on_white():
    project = TrackProject(
        20,
        10,
        [TrackElement("straight", Point(3, 5), length=10, width=2)],
    )
    image, metrics = _render(
        project,
        PrintOptions(
            grayscale=True,
            show_grid=False,
            show_title=False,
            show_dimensions=False,
        ),
    )

    def screen(point):
        return (
            round(metrics.layout_rect.left() + point.x * metrics.units_per_metre),
            round(
                metrics.layout_rect.top()
                + (project.hall_width - point.y) * metrics.units_per_metre
            ),
        )

    clear_road_surface = screen(Point(7, 5.4))
    centerline = screen(Point(7, 5))
    upper_edge = screen(Point(7, 6))
    assert image.pixelColor(*clear_road_surface) == QColor("#ffffff")
    centerline_samples = [
        image.pixelColor(centerline[0] + offset, centerline[1]).lightness()
        for offset in range(-8, 9)
    ]
    assert min(centerline_samples) < 150
    edge_samples = [
        image.pixelColor(upper_edge[0], upper_edge[1] + offset).lightness()
        for offset in range(-2, 3)
    ]
    assert min(edge_samples) < 150


def test_classic_grayscale_removes_internal_seam_at_connected_elements():
    straight = TrackElement("straight", Point(3, 5), length=8, width=2)
    curve = TrackElement("left", Point(11, 5), radius=4, angle_deg=90, width=2)
    project = TrackProject(20, 12, [straight, curve])
    project.connect(
        ConnectorRef(straight.id, "end"),
        ConnectorRef(curve.id, "start"),
    )
    image, metrics = _render(
        project,
        PrintOptions(
            grayscale=True,
            show_grid=False,
            show_title=False,
            show_dimensions=False,
        ),
    )

    def screen(point):
        return (
            round(metrics.layout_rect.left() + point.x * metrics.units_per_metre),
            round(
                metrics.layout_rect.top()
                + (project.hall_width - point.y) * metrics.units_per_metre
            ),
        )

    # The former per-element contour drew a vertical end cap through the road
    # at x=11.  Away from the dashed centreline that connected surface is white.
    for point in (Point(11, 4.4), Point(11, 5.6)):
        x, y = screen(point)
        assert image.pixelColor(x, y).lightness() > 240


def test_grid_option_changes_output_but_not_layout_geometry():
    project = TrackProject(30, 20, editor_mode="indoor")
    with_grid, first = _render(project, PrintOptions(show_grid=True))
    without_grid, second = _render(project, PrintOptions(show_grid=False))

    assert first.layout_rect == second.layout_rect
    assert with_grid != without_grid


def test_track_area_dimensions_can_be_toggled_in_classic_mode():
    project = _classic_project()
    _, visible = _render(
        project,
        PrintOptions(show_title=False, show_dimensions=True),
    )
    _, hidden = _render(
        project,
        PrintOptions(show_title=False, show_dimensions=False),
    )

    assert visible.content_rect.top() > hidden.content_rect.top()


def test_print_output_is_independent_of_canvas_zoom_pan_and_selection():
    _app()
    window = MainWindow()
    project = _classic_project()
    window.canvas.set_project(project)
    first_image, _ = _render(window.canvas.project, PrintOptions())

    window.canvas.scale = 173
    window.canvas.pan.setX(-450)
    window.canvas.pan.setY(800)
    window.canvas.selected = project.elements[0]
    window.canvas.selected_ids = {project.elements[0].id}
    window.canvas.snap_preview = []
    second_image, _ = _render(window.canvas.project, PrintOptions())

    assert first_image == second_image
    window.close()


@pytest.mark.parametrize("project", [_classic_project(8, 6), _classic_project(400, 240), _indoor_project()])
def test_pdf_export_creates_nonempty_vector_document(tmp_path, project):
    path = tmp_path / "layout.pdf"
    options = PrintOptions(paper_size="A3", orientation="landscape")

    render_project_to_printer(
        pdf_printer(path, options), project, options, title="PDF test"
    )

    assert path.is_file()
    assert path.stat().st_size > 1000
    assert path.read_bytes().startswith(b"%PDF")


def test_preview_settings_update_printer_and_preview_options():
    _app()
    dialog = LayoutPrintPreviewDialog(
        _indoor_project(), PrintOptions(), "Preview", lambda text, **values: text.format(**values)
    )
    dialog.settings_widget.paper_combo.setCurrentIndex(
        dialog.settings_widget.paper_combo.findData("A3")
    )
    dialog.settings_widget.orientation_combo.setCurrentIndex(
        dialog.settings_widget.orientation_combo.findData("portrait")
    )
    dialog.settings_widget.grayscale_check.setChecked(True)

    assert dialog.options().paper_size == "A3"
    assert dialog.options().orientation == "portrait"
    assert dialog.options().grayscale
    assert dialog.printer.pageLayout().pageSize().id() == QPageSize.PageSizeId.A3
    assert dialog.printer.pageLayout().orientation() == QPageLayout.Orientation.Portrait
    dialog.close()


def test_classic_preview_allows_dimension_toggle():
    dialog = LayoutPrintPreviewDialog(
        _classic_project(),
        PrintOptions(show_dimensions=True),
        "Classic",
        lambda text, **values: text.format(**values),
    )

    assert dialog.settings_widget.dimensions_check.isEnabled()
    dialog.settings_widget.dimensions_check.setChecked(False)
    assert not dialog.options().show_dimensions
    dialog.close()


def test_file_menu_contains_print_actions_and_german_translations():
    _app()
    window = MainWindow()
    actions = window.file_menu.actions()

    assert window.print_preview_action in actions
    assert window.print_action in actions
    assert window.export_pdf_action in actions
    assert window.print_preview_action.text() == "Druckvorschau"
    assert window.print_action.text() == "Drucken…"
    assert window.export_pdf_action.text() == "Als PDF exportieren…"
    window.close()


def test_cancelled_print_settings_leave_project_and_undo_unchanged(monkeypatch):
    _app()
    window = MainWindow()
    window.canvas.set_project(_classic_project())
    before = deepcopy(window.canvas.project)
    undo_count = window.canvas.undo_stack.count()
    monkeypatch.setattr(
        "rc_track_designer.ui.PrintOptionsDialog.exec",
        lambda self: QDialog.DialogCode.Rejected,
    )

    assert not window.print_project()
    assert window.canvas.project == before
    assert window.canvas.undo_stack.count() == undo_count
    window.close()


def test_cancelled_pdf_file_dialog_leaves_project_unchanged(monkeypatch):
    _app()
    window = MainWindow()
    window.canvas.set_project(_indoor_project())
    before = deepcopy(window.canvas.project)
    monkeypatch.setattr(window, "_choose_print_options", lambda: PrintOptions())
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: ("", ""))

    assert not window.export_pdf()
    assert window.canvas.project == before
    window.close()


def test_pdf_is_not_overwritten_without_confirmation(tmp_path, monkeypatch):
    _app()
    path = tmp_path / "existing.pdf"
    path.write_bytes(b"keep me")
    window = MainWindow()
    monkeypatch.setattr(window, "_choose_print_options", lambda: PrintOptions())
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *args: (str(path), "PDF files (*.pdf)")
    )
    monkeypatch.setattr(
        QMessageBox,
        "exec",
        lambda self: QMessageBox.StandardButton.No,
    )

    assert not window.export_pdf()
    assert path.read_bytes() == b"keep me"
    window.close()
