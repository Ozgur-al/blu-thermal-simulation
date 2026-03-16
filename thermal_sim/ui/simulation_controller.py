"""SimulationController — QObject managing QThread worker lifecycle.

Encapsulates the worker-object threading pattern so that MainWindow
is not polluted with QThread management code and so the controller
can be tested independently.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

# Legacy (Phase <=10) imports — removed in Phase 11 Plan 03.
# Wrapped so the controller file stays importable for VoxelMainWindow.
try:
    from thermal_sim.models.project import DisplayProject
except ImportError:
    DisplayProject = None  # type: ignore[assignment,misc]

try:
    from thermal_sim.solvers.steady_state import SteadyStateSolver
    from thermal_sim.solvers.transient import TransientSolver
except ImportError:
    SteadyStateSolver = TransientSolver = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# _VoxelSimWorker
# ---------------------------------------------------------------------------

class _VoxelSimWorker(QObject):
    """Runs the voxel solver (steady or transient) in a background thread.

    Signals
    -------
    finished : Signal(object)
        Emitted with VoxelSteadyStateResult or VoxelTransientResult.
    error : Signal(str)
        Emitted with an error message string if an exception occurs.
    progress : Signal(int, str)
        Emitted with (percent 0-100, status message).
    """

    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int, str)

    def __init__(self, project: object, mode: str) -> None:
        super().__init__()
        self._project = project
        self._mode = mode
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._mode == "steady":
                from thermal_sim.solvers.steady_state_voxel import VoxelSteadyStateSolver

                def _progress(phase: str) -> None:
                    if phase == "building":
                        self.progress.emit(-1, "Building voxel network…")
                    elif phase == "solving":
                        self.progress.emit(-1, "Solving voxel steady-state…")

                result = VoxelSteadyStateSolver().solve(
                    self._project, on_progress=_progress
                )
                self.progress.emit(100, "Complete")
            else:
                from thermal_sim.solvers.transient_voxel import VoxelTransientSolver

                def _t_progress(step: int, n_steps: int, t_max_c: float) -> None:
                    pct = int(100 * step / max(n_steps, 1))
                    self.progress.emit(pct, f"Step {step}/{n_steps} | T_max: {t_max_c:.1f} C")

                result = VoxelTransientSolver().solve(
                    self._project, on_progress=_t_progress
                )
                if self._cancel_requested:
                    self.progress.emit(0, "Cancelled")
                else:
                    self.progress.emit(100, "Complete")
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# _SweepWorker
# ---------------------------------------------------------------------------

class _SweepWorker(QObject):
    """Runs SweepEngine in a background thread.

    Signals
    -------
    finished : Signal(object)
        Emitted with the SweepResult when the sweep completes.
    error : Signal(str)
        Emitted with an error message string if an exception occurs.
    progress : Signal(int, str)
        Emitted after each completed run with (percent 0-100, "Run N of M").
    """

    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int, str)

    def __init__(self, project: DisplayProject, config: object) -> None:
        super().__init__()
        self._project = project
        self._config = config
        self._cancel_requested = False

    def request_cancel(self) -> None:
        """Set the cancel flag (for future cooperative cancellation)."""
        self._cancel_requested = True

    def run(self) -> None:
        """Entry point called by QThread.started signal."""
        from thermal_sim.core.sweep_engine import SweepEngine

        try:
            result = SweepEngine().run(
                self._project,
                self._config,
                on_progress=self._on_progress,
            )
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))

    def _on_progress(self, run_n: int, total: int) -> None:
        pct = int(100 * run_n / max(total, 1))
        self.progress.emit(pct, f"Run {run_n} of {total}")


class _SimWorker(QObject):
    """Runs the solver in a background thread.

    Signals
    -------
    finished : Signal(object)
        Emitted with the result object when the solver completes.
    error : Signal(str)
        Emitted with the error message string when an exception occurs.
    progress : Signal(int, str)
        Emitted during a transient run with (percent 0-100, status message).
    """

    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int, str)

    def __init__(self, project: DisplayProject, mode: str) -> None:
        super().__init__()
        self._project = project
        self._mode = mode
        self._cancel_requested = False

    def request_cancel(self) -> None:
        """Set the cancel flag; the solver will stop at the next check point."""
        self._cancel_requested = True

    def run(self) -> None:
        """Entry point called by QThread.started signal."""
        try:
            if self._mode == "steady":
                def _steady_progress(phase: str) -> None:
                    if phase == "building":
                        self.progress.emit(-1, "Building thermal network…")
                    elif phase == "solving":
                        self.progress.emit(-1, "Solving steady-state…")

                result = SteadyStateSolver().solve(
                    self._project, on_progress=_steady_progress
                )
                self.progress.emit(100, "Complete")
            else:
                result = TransientSolver().solve(
                    self._project,
                    on_progress=self._on_progress,
                    cancel_check=lambda: self._cancel_requested,
                )
                if self._cancel_requested:
                    self.progress.emit(0, "Cancelled")
                else:
                    self.progress.emit(100, "Complete")
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))

    def _on_progress(self, step: int, n_steps: int, t_max_c: float) -> None:
        pct = int(100 * step / max(n_steps, 1))
        self.progress.emit(pct, f"Step {step}/{n_steps} | T_max: {t_max_c:.1f} C")


class SimulationController(QObject):
    """Manages the simulation worker thread lifecycle.

    Signals
    -------
    progress_updated : Signal(int, str)
        Forwarded from the worker: percent (0-100) and a status message.
    run_finished : Signal(object)
        Emitted with the result object after a successful run.
    run_error : Signal(str)
        Emitted with an error message string when the solver raises.
    run_started : Signal()
        Emitted just before the background thread is started.
    run_ended : Signal()
        Emitted after a run completes (success, error, or cancel).
    sweep_finished : Signal(object)
        Emitted with a SweepResult after a successful parametric sweep.
    """

    progress_updated = Signal(int, str)
    run_finished = Signal(object)
    run_error = Signal(str)
    run_started = Signal()
    run_ended = Signal()
    sweep_finished = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _SimWorker | None = None
        self._sweep_thread: QThread | None = None
        self._sweep_worker: _SweepWorker | None = None
        self._voxel_thread: QThread | None = None
        self._voxel_worker: _VoxelSimWorker | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """True while a background thread is active."""
        return self._thread is not None and self._thread.isRunning()

    def start_run(self, project: DisplayProject, mode: str) -> None:
        """Start a simulation run.

        If a run is already in progress, this call is silently ignored
        (no crash, no duplicate threads).

        Parameters
        ----------
        project:
            The project to simulate.
        mode:
            ``"steady"`` or ``"transient"``.
        """
        if self.is_running:
            return

        self._worker = _SimWorker(project, mode)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)

        # Wire signals.
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress_updated)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        # Thread must quit when the worker signals completion or error.
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        # Defer cleanup until the thread event loop has fully stopped.
        self._thread.finished.connect(self._cleanup)

        self.run_started.emit()
        self._thread.start()

    def start_sweep(self, project: DisplayProject, config: object) -> None:
        """Start a parametric sweep in a background thread.

        If a run or sweep is already in progress, this call is silently ignored.

        Parameters
        ----------
        project:
            The base project to sweep over.
        config:
            A SweepConfig describing the parameter path, values, and mode.
        """
        if self.is_running or (
            self._sweep_thread is not None and self._sweep_thread.isRunning()
        ):
            return

        self._sweep_worker = _SweepWorker(project, config)
        self._sweep_thread = QThread()
        self._sweep_worker.moveToThread(self._sweep_thread)

        self._sweep_thread.started.connect(self._sweep_worker.run)
        self._sweep_worker.progress.connect(self.progress_updated)
        self._sweep_worker.finished.connect(self._on_sweep_finished)
        self._sweep_worker.error.connect(self._on_sweep_error)
        self._sweep_worker.finished.connect(self._sweep_thread.quit)
        self._sweep_worker.error.connect(self._sweep_thread.quit)
        self._sweep_thread.finished.connect(self._cleanup_sweep)

        self.run_started.emit()
        self._sweep_thread.start()

    def start_voxel_run(self, project: object, mode: str) -> None:
        """Start a voxel simulation (steady or transient) in a background thread.

        Uses VoxelSteadyStateSolver or VoxelTransientSolver.
        Emits the same signals as start_run(): run_started, progress_updated,
        run_finished, run_error, run_ended.

        Parameters
        ----------
        project:
            A VoxelProject instance.
        mode:
            ``"steady"`` or ``"transient"``.
        """
        if self.is_running or (
            self._voxel_thread is not None and self._voxel_thread.isRunning()
        ):
            return

        self._voxel_worker = _VoxelSimWorker(project, mode)
        self._voxel_thread = QThread()
        self._voxel_worker.moveToThread(self._voxel_thread)

        self._voxel_thread.started.connect(self._voxel_worker.run)
        self._voxel_worker.progress.connect(self.progress_updated)
        self._voxel_worker.finished.connect(self._on_voxel_finished)
        self._voxel_worker.error.connect(self._on_voxel_error)
        self._voxel_worker.finished.connect(self._voxel_thread.quit)
        self._voxel_worker.error.connect(self._voxel_thread.quit)
        self._voxel_thread.finished.connect(self._cleanup_voxel)

        self.run_started.emit()
        self._voxel_thread.start()

    def cancel(self) -> None:
        """Request cooperative cancellation of the current run.

        Safe to call when no run is active — does nothing in that case.
        """
        if self._worker is not None:
            self._worker.request_cancel()
        if self._sweep_worker is not None:
            self._sweep_worker.request_cancel()
        if self._voxel_worker is not None:
            self._voxel_worker.request_cancel()

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _on_finished(self, result: object) -> None:
        self.run_finished.emit(result)
        self.run_ended.emit()

    def _on_error(self, message: str) -> None:
        self.run_error.emit(message)
        self.run_ended.emit()

    def _cleanup(self) -> None:
        """Release worker and thread objects after the thread stops."""
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None

    def _on_sweep_finished(self, result: object) -> None:
        self.sweep_finished.emit(result)
        self.run_ended.emit()

    def _on_sweep_error(self, message: str) -> None:
        self.run_error.emit(message)
        self.run_ended.emit()

    def _cleanup_sweep(self) -> None:
        """Release sweep worker and thread objects after the thread stops."""
        if self._sweep_worker is not None:
            self._sweep_worker.deleteLater()
            self._sweep_worker = None
        if self._sweep_thread is not None:
            self._sweep_thread.deleteLater()
            self._sweep_thread = None

    def _on_voxel_finished(self, result: object) -> None:
        self.run_finished.emit(result)
        self.run_ended.emit()

    def _on_voxel_error(self, message: str) -> None:
        self.run_error.emit(message)
        self.run_ended.emit()

    def _cleanup_voxel(self) -> None:
        """Release voxel worker and thread objects after the thread stops."""
        if self._voxel_worker is not None:
            self._voxel_worker.deleteLater()
            self._voxel_worker = None
        if self._voxel_thread is not None:
            self._voxel_thread.deleteLater()
            self._voxel_thread = None
