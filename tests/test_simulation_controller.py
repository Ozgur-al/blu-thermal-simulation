"""Tests for SimulationController signal API and worker lifecycle."""

from __future__ import annotations

import sys

import pytest

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    """Provide a QApplication instance for the test module."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_simulation_controller_can_be_instantiated(qapp):
    """SimulationController is importable and can be constructed without a parent."""
    from thermal_sim.ui.simulation_controller import SimulationController

    controller = SimulationController()
    assert controller is not None


def test_simulation_controller_signals_exist(qapp):
    """SimulationController exposes the expected signals."""
    from thermal_sim.ui.simulation_controller import SimulationController

    controller = SimulationController()
    # All five signals must be present.
    assert hasattr(controller, "progress_updated")
    assert hasattr(controller, "run_finished")
    assert hasattr(controller, "run_error")
    assert hasattr(controller, "run_started")
    assert hasattr(controller, "run_ended")


def test_is_running_false_when_idle(qapp):
    """is_running is False before any run is started."""
    from thermal_sim.ui.simulation_controller import SimulationController

    controller = SimulationController()
    assert controller.is_running is False


def test_cancel_on_idle_controller_does_not_crash(qapp):
    """Calling cancel() before start_run() must not raise."""
    from thermal_sim.ui.simulation_controller import SimulationController

    controller = SimulationController()
    controller.cancel()  # must not raise


def test_start_run_while_running_does_nothing(qapp):
    """Calling start_run() a second time while a run is in progress is a no-op."""
    from thermal_sim.ui.simulation_controller import SimulationController
    from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
    from thermal_sim.models.heat_source import HeatSource
    from thermal_sim.models.layer import Layer
    from thermal_sim.models.material import Material
    from thermal_sim.models.project import DisplayProject, MeshConfig, TransientConfig

    material = Material(
        name="M",
        k_in_plane=1.0,
        k_through=1.0,
        density=500.0,
        specific_heat=500.0,
        emissivity=0.9,
    )
    project = DisplayProject(
        name="Test",
        width=0.1,
        height=0.1,
        materials={"M": material},
        layers=[Layer(name="L", material="M", thickness=0.001)],
        heat_sources=[HeatSource(name="S", layer="L", power_w=1.0, shape="full")],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=25.0, convection_h=10.0, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=25.0, convection_h=10.0, include_radiation=False),
            side=SurfaceBoundary(ambient_c=25.0, convection_h=0.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=2, ny=2),
        transient=TransientConfig(
            time_step_s=0.1,
            total_time_s=0.5,
            output_interval_s=0.1,
        ),
        initial_temperature_c=25.0,
    )

    controller = SimulationController()
    results = []
    controller.run_finished.connect(lambda r: results.append(r))

    # First start_run
    controller.start_run(project, "steady")
    assert controller.is_running is True

    # Second start_run while running — must not raise, must not start a second thread.
    # We capture the thread reference before the call to verify it didn't change.
    thread_before = controller._thread
    controller.start_run(project, "steady")  # no-op
    assert controller._thread is thread_before


def test_worker_cancel_flag_set_by_cancel(qapp):
    """After cancel(), the worker's cancel flag is set."""
    from thermal_sim.ui.simulation_controller import _SimWorker
    from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
    from thermal_sim.models.heat_source import HeatSource
    from thermal_sim.models.layer import Layer
    from thermal_sim.models.material import Material
    from thermal_sim.models.project import DisplayProject, MeshConfig, TransientConfig

    material = Material(
        name="M",
        k_in_plane=1.0,
        k_through=1.0,
        density=500.0,
        specific_heat=500.0,
        emissivity=0.9,
    )
    project = DisplayProject(
        name="Test",
        width=0.1,
        height=0.1,
        materials={"M": material},
        layers=[Layer(name="L", material="M", thickness=0.001)],
        heat_sources=[HeatSource(name="S", layer="L", power_w=1.0, shape="full")],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=25.0, convection_h=10.0, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=25.0, convection_h=10.0, include_radiation=False),
            side=SurfaceBoundary(ambient_c=25.0, convection_h=0.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=1, ny=1),
        transient=TransientConfig(
            time_step_s=0.1,
            total_time_s=0.5,
            output_interval_s=0.1,
        ),
        initial_temperature_c=25.0,
    )

    worker = _SimWorker(project, "transient")
    assert worker._cancel_requested is False
    worker.request_cancel()
    assert worker._cancel_requested is True
