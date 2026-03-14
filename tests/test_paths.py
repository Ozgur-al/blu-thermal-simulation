"""Unit tests for thermal_sim.core.paths — resource path resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def test_get_resources_dir_returns_path() -> None:
    from thermal_sim.core.paths import get_resources_dir

    result = get_resources_dir()
    assert isinstance(result, Path)


def test_get_examples_dir_returns_path() -> None:
    from thermal_sim.core.paths import get_examples_dir

    result = get_examples_dir()
    assert isinstance(result, Path)


def test_get_output_dir_returns_path() -> None:
    from thermal_sim.core.paths import get_output_dir

    result = get_output_dir()
    assert isinstance(result, Path)


def test_get_crash_log_path_returns_path() -> None:
    from thermal_sim.core.paths import get_crash_log_path

    result = get_crash_log_path()
    assert isinstance(result, Path)


def test_app_version_is_string() -> None:
    from thermal_sim.core.paths import APP_VERSION

    assert isinstance(APP_VERSION, str)
    assert len(APP_VERSION) > 0


def test_get_resources_dir_exists_in_dev_mode() -> None:
    """In dev mode (not frozen), resources dir must exist on disk."""
    assert not getattr(sys, "frozen", False), "This test only runs in dev mode"
    from thermal_sim.core.paths import get_resources_dir

    result = get_resources_dir()
    assert result.exists(), f"Resources dir not found: {result}"
    assert result.is_dir()


def test_get_examples_dir_exists_in_dev_mode() -> None:
    """In dev mode (not frozen), examples dir must exist on disk."""
    assert not getattr(sys, "frozen", False), "This test only runs in dev mode"
    from thermal_sim.core.paths import get_examples_dir

    result = get_examples_dir()
    assert result.exists(), f"Examples dir not found: {result}"
    assert result.is_dir()


def test_get_output_dir_contains_documents_thermalsim() -> None:
    from thermal_sim.core.paths import get_output_dir

    result = get_output_dir()
    parts = result.parts
    assert "Documents" in parts
    assert "ThermalSim" in parts
    assert "outputs" in parts


def test_get_crash_log_path_ends_with_crash_log() -> None:
    from thermal_sim.core.paths import get_crash_log_path

    result = get_crash_log_path()
    assert result.name == "crash.log"


def test_frozen_mode_bundle_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When sys.frozen=True and sys._MEIPASS set, _bundle_root returns _MEIPASS."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    # Must reimport to pick up monkeypatched sys values
    import importlib
    import thermal_sim.core.paths as paths_mod

    importlib.reload(paths_mod)
    result = paths_mod._bundle_root()
    assert result == tmp_path


def test_frozen_mode_exe_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When sys.frozen=True, _exe_dir returns directory of sys.executable."""
    fake_exe = tmp_path / "ThermalSim.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe), raising=False)

    import importlib
    import thermal_sim.core.paths as paths_mod

    importlib.reload(paths_mod)
    result = paths_mod._exe_dir()
    assert result == tmp_path
