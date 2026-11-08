import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

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
