"""GUI launcher for the thermal simulator."""

from __future__ import annotations

import sys

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


def main() -> None:
    try:
        from PySide6.QtWidgets import QApplication
        from qt_material import apply_stylesheet
    except ModuleNotFoundError as exc:
        print("PySide6 is required for the GUI. Install it with: pip install -r requirements.txt")
        raise SystemExit(2) from exc

    try:
        from thermal_sim.ui.main_window import MainWindow
    except ModuleNotFoundError as exc:
        print("Some GUI dependencies are missing. Install them with: pip install -r requirements.txt")
        raise SystemExit(2) from exc

    import matplotlib as mpl

    app = QApplication(sys.argv)
    apply_stylesheet(app, theme="dark_amber.xml")
    app.setStyleSheet(app.styleSheet() + _EXTRA_QSS)
    mpl.rcParams.update(DARK_MPL_STYLE)
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
