"""GUI launcher for the thermal simulator."""

from __future__ import annotations

import sys


def main() -> None:
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError as exc:
        print("PySide6 is required for GUI mode. Install dependencies from requirements.txt.")
        raise SystemExit(2) from exc

    try:
        from thermal_sim.ui.main_window import MainWindow
    except ModuleNotFoundError as exc:
        print("GUI dependencies are missing. Install dependencies from requirements.txt.")
        raise SystemExit(2) from exc

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
