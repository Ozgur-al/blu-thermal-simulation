"""Centralized resource path resolution for frozen (PyInstaller) and dev modes.

All code that needs to locate a resource file (JSON, example project, crash log)
should import from this module rather than using bare relative Path() calls or
importlib.resources directly.

Reference: https://pyinstaller.org/en/stable/runtime-information.html
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_VERSION = "1.0"


def _bundle_root() -> Path:
    """Root of the PyInstaller bundle (_internal dir), or project root in dev.

    In a PyInstaller --onedir build:
      - sys.frozen is True
      - sys._MEIPASS points to <bundle>/_internal/ (the runtime files dir)

    In dev mode:
      - Returns three levels up from this file (thermal_sim/core/paths.py)
        which is the project root (G:/blu-thermal-simulation/).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


def _exe_dir() -> Path:
    """Directory containing ThermalSim.exe; project root in dev mode.

    In a PyInstaller --onedir build:
      - sys.executable points to <bundle>/ThermalSim.exe
      - This returns <bundle>/ (one level above _internal/)

    Examples go next to the exe, not inside _internal.
    In dev mode this is the same as _bundle_root().
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def get_resources_dir() -> Path:
    """Path to thermal_sim/resources/ — always inside _internal in bundle.

    In dev mode:    <project_root>/thermal_sim/resources/
    In frozen mode: <bundle>/_internal/thermal_sim/resources/
    """
    return _bundle_root() / "thermal_sim" / "resources"


def get_examples_dir() -> Path:
    """Path to examples/ — sits next to ThermalSim.exe in the bundle.

    In dev mode:    <project_root>/examples/
    In frozen mode: <bundle>/examples/
    """
    return _exe_dir() / "examples"


def get_output_dir() -> Path:
    """Default output directory: ~/Documents/ThermalSim/outputs/.

    Always user-writable without admin access. Survives re-extraction of the
    bundle because it lives outside the install directory.
    """
    return Path.home() / "Documents" / "ThermalSim" / "outputs"


def get_crash_log_path() -> Path:
    """Path for crash.log — sits next to ThermalSim.exe.

    In dev mode:    <project_root>/crash.log
    In frozen mode: <bundle>/crash.log
    """
    return _exe_dir() / "crash.log"
