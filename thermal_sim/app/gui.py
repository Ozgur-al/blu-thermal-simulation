"""GUI launcher for the thermal simulator.

Entry point for PyInstaller --windowed build.
Provides:
- Crash handler: catches unhandled exceptions, writes crash.log, shows Qt dialog
- Splash screen: dark-themed QPainter splash dismissed when MainWindow is ready
- Version display: window title set in main_window.py via APP_VERSION from paths
"""

from __future__ import annotations

import sys
import traceback

from thermal_sim.core.paths import APP_VERSION, get_crash_log_path

DARK_MPL_STYLE = {
    "figure.facecolor": "#212121",
    "axes.facecolor":   "#303030",
    "axes.edgecolor":   "#666666",
    "text.color":       "#e0e0e0",
    "axes.labelcolor":  "#e0e0e0",
    "xtick.color":      "#e0e0e0",
    "ytick.color":      "#e0e0e0",
    "grid.color":       "#444444",
    "grid.alpha":       0.5,
    "legend.facecolor": "#303030",
    "legend.edgecolor": "#666666",
}

_EXTRA_QSS = """\
QTableWidget { font-family: Consolas, 'Courier New', monospace; }
QStatusBar QLabel { font-family: Consolas, 'Courier New', monospace; }
"""


def _run_app() -> None:
    """Create QApplication, show splash, load MainWindow, run event loop."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication, QSplashScreen
    from qt_material import apply_stylesheet

    import matplotlib as mpl

    app = QApplication(sys.argv)
    apply_stylesheet(app, theme="dark_amber.xml")
    app.setStyleSheet(app.styleSheet() + _EXTRA_QSS)

    # Build splash pixmap with QPainter — no external asset file needed.
    # Dark background matches qt-material dark_amber theme (#212121).
    pixmap = QPixmap(480, 280)
    pixmap.fill(QColor("#212121"))
    painter = QPainter(pixmap)

    # Title: app name in dark_amber accent color
    painter.setPen(QColor("#FFB300"))
    title_font = QFont("Segoe UI", 22, QFont.Weight.Bold)
    painter.setFont(title_font)
    painter.drawText(
        pixmap.rect().adjusted(0, -30, 0, 0),
        Qt.AlignmentFlag.AlignCenter,
        "Thermal Simulator",
    )

    # Version line below title
    version_font = QFont("Segoe UI", 13)
    painter.setFont(version_font)
    painter.drawText(
        pixmap.rect().adjusted(0, 40, 0, 0),
        Qt.AlignmentFlag.AlignCenter,
        f"v{APP_VERSION}",
    )

    painter.end()

    splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint)
    splash.show()
    splash.showMessage(
        "Loading...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#e0e0e0"),
    )
    app.processEvents()

    # Apply dark matplotlib theme before MainWindow builds any canvases.
    mpl.rcParams.update(DARK_MPL_STYLE)

    # Import and construct MainWindow *after* splash is visible — this is the
    # slow part (scipy/numpy/PySide6 sub-imports happen here).
    from thermal_sim.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    splash.finish(window)

    raise SystemExit(app.exec())


def main() -> None:
    """Entry point with crash handler.

    Wraps _run_app() to catch any unhandled exception, write it to crash.log
    next to the exe, and show a Qt message box with a summary.

    Note: Do NOT use print() here — sys.stdout/sys.stderr are None in
    PyInstaller --windowed / --noconsole builds on Windows (Pitfall 8).
    """
    try:
        _run_app()
    except SystemExit:
        # Normal exit via app.exec() returning — do not treat as a crash.
        raise
    except Exception:
        tb = traceback.format_exc()

        # Write crash.log next to the exe (writable location).
        try:
            log_path = get_crash_log_path()
            log_path.write_text(tb, encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

        # Show Qt message box with truncated traceback summary.
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            _app = QApplication.instance() or QApplication([])
            QMessageBox.critical(
                None,
                "Thermal Simulator — Fatal Error",
                f"An unexpected error occurred.\n\n{tb[:800]}\n\nSee crash.log for full details.",
            )
        except Exception:  # noqa: BLE001
            pass

        raise SystemExit(1)


if __name__ == "__main__":
    main()
