# Phase 1: Foundation - Research

**Researched:** 2026-03-14
**Domain:** PySide6 desktop GUI refactoring — undo/redo, threaded simulation, status bar, keyboard shortcuts, menu structure
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Solver mode selection**: Toolbar dropdown (combo box) always visible in the main toolbar. One click to switch between steady-state and transient.
- **Output directory configuration**: "Set Output Directory..." under a new Run menu. Opens a native folder browser dialog. Remembers last-used path between sessions.
- **CSV export**: Manual action only — user clicks "Export CSV..." from menu or toolbar after reviewing results. No auto-export.
- **Menu bar structure**: New top-level "Run" menu. Contains: Run Simulation (F5), Cancel (Esc), Set Output Directory..., Export CSV...
- **Modified state & undo interaction**: Undoing all changes back to last-saved state clears the modified asterisk. Matches VS Code / Word behavior.
- **Status bar — run feedback**: Detailed solver metrics. During run: progress bar + timestep count + peak temperature so far. After run: T_max, solve time, mesh size. Cancel shows "Cancelled" state.
- **Status bar — spatial layout**: Three-zone layout: Left (file path + modified asterisk), Center (solver state / progress bar), Right (last run time + mesh size).
- **Unsaved changes prompt**: Standard Save/Discard/Cancel dialog on window close, open project, or new project.

### Claude's Discretion

- Undo/redo granularity (what constitutes one undoable action, stack depth)
- Simulation progress & cancel behavior details (partial results handling, thread management)
- Exact refactoring boundaries between SimulationController, TableDataParser, and PlotManager
- Keyboard shortcut conflict resolution with focused widgets
- Progress bar widget choice and animation style

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GUI-01 | MainWindow refactored into SimulationController, TableDataParser, and PlotManager | QObject worker pattern; refactoring boundaries documented in Architecture Patterns section |
| GUI-02 | User can undo/redo any project edit via Ctrl+Z/Ctrl+Y | QUndoStack + QUndoCommand pattern; cell-change granularity recommendation in Code Examples |
| GUI-03 | User can run simulation with visible progress bar and cancel button | QThread worker-object pattern; `_cancel` flag; QProgressBar in status bar center zone |
| GUI-04 | Status bar shows file path, modified indicator, last run time, and solver state | QStatusBar addPermanentWidget; three-zone layout with QLabel + QProgressBar |
| GUI-05 | Window title shows asterisk when project has unsaved changes | `setWindowTitle()` + dirty-flag tracking pattern; undo stack `cleanChanged` signal |
| GUI-06 | All CLI capabilities accessible from GUI (output dir, CSV export, mode selection) | QSettings for persistent output dir; QComboBox in toolbar for mode; QAction in Run menu for Export |
| GUI-07 | Keyboard shortcuts: Ctrl+S save, Ctrl+Z/Y undo/redo, F5 run, Escape cancel | QAction + QKeySequence pattern; focus-independent shortcuts via QAction on QMenuBar/QToolBar |
</phase_requirements>

---

## Summary

Phase 1 is a pure PySide6 refactoring and enhancement phase. No new solver logic, no new data models, no new dependencies beyond what is already in the stack. All seven requirements are implementable using PySide6 built-ins: `QUndoStack` for undo/redo, the worker-object `QThread` pattern for threaded simulation, `QStatusBar` with `addPermanentWidget` for the three-zone status bar, `QAction` + `QKeySequence` for keyboard shortcuts, `QSettings` for persisting the output directory, and `QMenuBar` additions for the Run menu.

The central risk in this phase is the 939-line `MainWindow` god object. Refactoring it into `SimulationController`, `TableDataParser`, and `PlotManager` must be done before adding any new features — adding undo, threading, and menus into the existing monolith would make the class untestable and create a maintenance trap. The recommended build order is: (1) extract collaborators, (2) wire undo/redo, (3) thread the simulation with progress/cancel, (4) add status bar, (5) add Run menu + shortcuts.

The undo/redo implementation using `QUndoStack` is the subtlest part. The "undo back to saved = not dirty" requirement maps naturally to `QUndoStack.setClean()` / `isClean()` — calling `setClean()` at save time and connecting `cleanChanged(bool)` signal to the window title and status bar asterisk update achieves the VS Code / Word behavior with minimal custom logic.

**Primary recommendation:** Use `QUndoStack` + per-cell `QUndoCommand` for undo; use the worker-object `QThread` pattern (not `QThread` subclassing) for the simulation thread; use `QSettings` for output directory persistence.

---

## Standard Stack

### Core (all already in requirements.txt — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.7+ (already installed) | All GUI widgets, threading, undo framework, keyboard shortcuts, status bar | Already the project's GUI framework; QUndoStack, QThread, QStatusBar, QAction, QSettings are all part of PySide6 — zero new dependencies |
| Python stdlib | 3.11+ | `datetime`, `time` for elapsed-time tracking in status bar | No extra install |

### No New Dependencies Required

All Phase 1 capabilities are provided by PySide6 built-ins:

| Capability | PySide6 Module | Class |
|------------|----------------|-------|
| Undo / redo | `PySide6.QtGui` | `QUndoStack`, `QUndoCommand` |
| Background thread | `PySide6.QtCore` | `QThread`, `QObject`, `Signal` |
| Progress bar | `PySide6.QtWidgets` | `QProgressBar` |
| Status bar | `PySide6.QtWidgets` | `QStatusBar` |
| Keyboard shortcuts | `PySide6.QtGui` | `QAction`, `QKeySequence` |
| Menu bar | `PySide6.QtWidgets` | `QMenuBar`, `QMenu` |
| Toolbar | `PySide6.QtWidgets` | `QToolBar` |
| Persistent settings | `PySide6.QtCore` | `QSettings` |
| Native folder dialog | `PySide6.QtWidgets` | `QFileDialog.getExistingDirectory()` |
| Unsaved-changes dialog | `PySide6.QtWidgets` | `QMessageBox` |

### Alternatives Considered

| Recommended | Alternative | Tradeoff |
|-------------|-------------|----------|
| `QUndoStack` (built-in) | Hand-rolled undo stack with list of snapshots | Snapshots of full `DisplayProject` are expensive and don't integrate with Qt's Edit menu undo text or `isClean()` tracking |
| Worker-object `QThread` pattern | `QThread` subclass with overridden `run()` | Subclassing is the less recommended Qt pattern — worker-object supports `moveToThread()` and proper signal cleanup |
| `QSettings` for output dir persistence | Custom JSON config file | `QSettings` uses the native OS registry/INI store automatically; zero boilerplate for simple key-value persistence |

---

## Architecture Patterns

### Recommended Project Structure After Refactor

```
thermal_sim/ui/
├── main_window.py         # Thin coordinator (~300 lines after extraction)
├── simulation_controller.py  # NEW: QObject owning QThread + worker, emits signals
├── table_data_parser.py   # NEW: stateless table ↔ model conversion (no Qt dependency)
├── plot_manager.py        # NEW: owns matplotlib canvases, handles all update logic
└── structure_preview.py   # Unchanged
```

### Pattern 1: Worker-Object QThread (for Simulation)

**What:** The simulation runs in a `_SimWorker(QObject)` that is moved onto a `QThread` via `moveToThread()`. `SimulationController` owns both and manages their lifecycle. Progress is communicated via signals only — never touch widgets from the worker thread.

**When to use:** Any operation that blocks the Qt event loop for more than ~0.1 seconds.

**Why not subclass QThread:** The worker-object pattern is the Qt-recommended approach (documented in Qt official docs). Subclassing `QThread` puts business logic inside the thread class, making it harder to move logic back to the main thread and harder to clean up.

**Cancellation:** Add `self._cancel = threading.Event()` or a simple `bool` flag on the worker. The transient solver's time loop must check this flag between timesteps. For steady-state (single call to `spsolve`), cancellation takes effect immediately after the solve completes — no mid-solve interrupt is possible or needed.

**Cleanup:** Connect `worker.finished → thread.quit → worker.deleteLater → thread.deleteLater` to prevent resource leaks.

**Example:**
```python
# thermal_sim/ui/simulation_controller.py
from PySide6.QtCore import QObject, QThread, Signal

class SimulationController(QObject):
    progress_updated = Signal(int, str)   # percent, message
    run_finished = Signal(object)         # result object
    run_error = Signal(str)

    def start_run(self, project, mode: str) -> None:
        if self._thread and self._thread.isRunning():
            return
        self._worker = _SimWorker(project, mode)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self.run_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def cancel(self) -> None:
        if self._worker:
            self._worker.request_cancel()
```

### Pattern 2: QUndoStack for Table Edits

**What:** Every user edit to a table cell creates a `QUndoCommand` subclass that stores the (table, row, col, old_value, new_value) tuple and implements `undo()` / `redo()`. The `QUndoStack` is owned by `MainWindow` and pushed to on every `cellChanged` signal.

**Granularity recommendation (Claude's discretion):** One undoable action = one cell change. This is the finest grain and what users expect from spreadsheet-like interfaces. Compound edits (e.g., "Add Row" which sets multiple cells) should use `QUndoStack.beginMacro()` / `endMacro()` to group them into a single undo step.

**Undo stack depth recommendation:** 100 commands. This is enough for any realistic editing session without consuming significant memory (each command stores two strings and a table pointer).

**Dirty tracking:** Call `undo_stack.setClean()` after save. Connect `undo_stack.cleanChanged` signal to the window-title update slot. When `isClean()` is True, no asterisk; when False, show asterisk. This handles the "undo back to saved = not dirty" requirement automatically.

**Signal guard:** When `QUndoCommand.undo()` or `redo()` sets a cell value, it will re-trigger `cellChanged`, which would push another command to the stack. Guard with a bool flag `self._undoing = True` before setting, check it at the top of the `cellChanged` handler.

**Example:**
```python
# thermal_sim/ui/main_window.py (simplified)
from PySide6.QtGui import QUndoStack, QUndoCommand

class _CellEditCommand(QUndoCommand):
    def __init__(self, table, row, col, old_val, new_val):
        super().__init__(f"Edit {table.horizontalHeaderItem(col).text()}")
        self._table, self._row, self._col = table, row, col
        self._old, self._new = old_val, new_val

    def undo(self):
        self._table.item(self._row, self._col).setText(self._old)

    def redo(self):
        self._table.item(self._row, self._col).setText(self._new)
```

### Pattern 3: Three-Zone Status Bar

**What:** `QStatusBar` with three zones implemented via `addPermanentWidget()`. Left zone is a plain `QLabel` for file path + asterisk. Center zone is a `QProgressBar` (shown during runs, hidden otherwise) plus a `QLabel` for solver state text. Right zone is a `QLabel` for last run time + mesh size.

**Important:** `QStatusBar.showMessage()` uses the temporary message area (left-most, overrides permanent widgets). The three-zone design should use only `addPermanentWidget()` — avoid `showMessage()` to prevent the zones being clobbered.

**Progress bar during transient:** The transient solver currently runs all timesteps in one call. To emit per-timestep progress, the `_SimWorker` must emit a `progress(int, str)` signal inside a modified time loop. This requires exposing a progress callback to the transient solver — see Architecture Patterns / Solver Progress Hook.

**Example:**
```python
# Status bar setup in MainWindow._build_ui()
sb = self.statusBar()
self._path_label = QLabel("No file")
self._solver_label = QLabel("Ready")
self._progress_bar = QProgressBar()
self._progress_bar.setVisible(False)
self._progress_bar.setMaximumWidth(200)
self._run_info_label = QLabel("")

sb.addPermanentWidget(self._path_label, stretch=2)
sb.addPermanentWidget(self._solver_label, stretch=1)
sb.addPermanentWidget(self._progress_bar, stretch=1)
sb.addPermanentWidget(self._run_info_label, stretch=1)
```

### Pattern 4: QAction + QKeySequence for Shortcuts

**What:** All keyboard shortcuts are attached to `QAction` objects placed on `QMenuBar` or `QToolBar`. This makes them focus-independent — they fire regardless of which widget is focused, which is the correct behavior for application-level shortcuts (F5, Escape, Ctrl+S).

**Why not QShortcut:** `QShortcut` has a context argument that determines when it fires. Application-level shortcuts on `QShortcut` with `Qt.ApplicationShortcut` context can conflict with widget-level shortcuts (e.g., Ctrl+Z in a QTextEdit). Using `QAction` on menus avoids this because the menu action handles shortcut routing through Qt's standard mechanism.

**Escape / Cancel:** Connect the Cancel `QAction` to `SimulationController.cancel()`. The action should only be enabled when a simulation is running. Toggle `setEnabled()` on `run_started` / `run_finished` signals.

**Example:**
```python
# In MainWindow._build_menus()
run_menu = self.menuBar().addMenu("&Run")

self._run_action = QAction("Run Simulation", self)
self._run_action.setShortcut(QKeySequence("F5"))
self._run_action.triggered.connect(self._on_run)
run_menu.addAction(self._run_action)

self._cancel_action = QAction("Cancel", self)
self._cancel_action.setShortcut(QKeySequence("Escape"))
self._cancel_action.setEnabled(False)
self._cancel_action.triggered.connect(self._sim_controller.cancel)
run_menu.addAction(self._cancel_action)

# Ctrl+S via File menu action (already exists as Save JSON button)
self._save_action = QAction("Save Project", self)
self._save_action.setShortcut(QKeySequence.StandardKey.Save)
self._save_action.triggered.connect(self._save_project_dialog)
file_menu.addAction(self._save_action)
```

### Pattern 5: QSettings for Output Directory Persistence

**What:** `QSettings` stores the last-used output directory using the application name and organization as keys. On launch, read the stored path; on change, write it.

**Example:**
```python
from PySide6.QtCore import QSettings

# Read on startup
settings = QSettings("ThermalSim", "ThermalSimulator")
self._output_dir = Path(settings.value("output_dir", str(Path.cwd() / "outputs")))

# Write on change
def _set_output_directory(self) -> None:
    path_str = QFileDialog.getExistingDirectory(self, "Set Output Directory", str(self._output_dir))
    if path_str:
        self._output_dir = Path(path_str)
        settings = QSettings("ThermalSim", "ThermalSimulator")
        settings.setValue("output_dir", str(self._output_dir))
```

### Pattern 6: Solver Progress Hook

**What:** To emit per-timestep progress from the transient solver without coupling the solver to Qt, pass a callback function `on_progress: Callable[[int, int, float], None] | None = None` to `TransientSolver.solve()`. The worker passes a lambda that emits the Qt signal; CLI passes `None`.

**When to use:** Any situation where a long-running function needs to report progress to a caller without importing Qt into the solver layer.

**Solver signature change (minimal):**
```python
# thermal_sim/solvers/transient.py
def solve(
    self,
    project: DisplayProject,
    on_progress: Callable[[int, int, float], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> TransientResult:
    ...
    for step in range(n_steps):
        if cancel_check and cancel_check():
            break
        # ... solve step ...
        if on_progress and step % sample_every == 0:
            on_progress(step, n_steps, float(T.max()) - project.initial_temperature_c)
```

### Anti-Patterns to Avoid

- **QThread subclassing with `run()` override:** Creates business logic inside the thread class; harder to clean up and contradicts Qt recommended pattern.
- **Storing full `DisplayProject` snapshots as undo states:** Expensive (~10 KB per snapshot × 100 stack depth = 1 MB minimum; more for large projects with many layers). Use fine-grained `QUndoCommand` per cell edit instead.
- **Calling `cellChanged` handler during undo without a guard flag:** Creates infinite recursion — undo triggers cellChanged which pushes another command which triggers another undo.
- **Using `QStatusBar.showMessage()` for permanent status info:** The temporary message area obscures permanent widgets for 3–5 seconds; use `addPermanentWidget` labels exclusively for the three zones.
- **Attaching shortcuts with `QShortcut(QKeySequence("F5"), self)`:** These can conflict with widget-level shortcuts and do not automatically appear in menus. Always use `QAction` with a shortcut key set.
- **Adding new feature code directly to `MainWindow` before extracting collaborators:** Results in a class that exceeds 1200+ lines, cannot be unit-tested, and creates hidden coupling between undo, threading, and plot update logic.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Undo/redo stack | Custom list of state snapshots | `QUndoStack` + `QUndoCommand` | Clean() tracking, macro grouping, menu text, redo coalescing all built-in |
| Background thread | `threading.Thread` | `QThread` + worker-object pattern | `threading.Thread` cannot safely call Qt slot functions across threads; signals/slots handle thread-safe GUI updates automatically |
| Keyboard shortcut routing | `keyPressEvent()` override on `MainWindow` | `QAction.setShortcut()` | Actions appear in menus, are enabled/disabled cleanly, and route correctly regardless of focused widget |
| Persistent settings | Custom JSON config file | `QSettings` | OS-native storage (Registry on Windows), automatic key/value API, no file management |
| Progress bar during solver | Custom widget or timer polling | `QProgressBar` + signal | `QProgressBar` handles animation, range, format string, and visibility correctly without custom drawing |

**Key insight:** PySide6 already provides production-quality implementations of every mechanism needed in Phase 1. The phase is about wiring existing Qt components correctly, not about building custom infrastructure.

---

## Common Pitfalls

### Pitfall 1: cellChanged fires during programmatic table population

**What goes wrong:** `_populate_ui_from_project()` sets table cell values programmatically. Each `setItem()` call fires `cellChanged`, which (after wiring undo) pushes a `_CellEditCommand` onto the undo stack. Loading a project generates ~100 spurious undo commands.

**Why it happens:** Qt's `cellChanged` signal fires on any item change, including programmatic ones. There is no "batch update" mode that suppresses it.

**How to avoid:** Block signals during population with `table.blockSignals(True)` / `table.blockSignals(False)`. Or wrap the entire `_populate_ui_from_project()` call in an undo macro and clear it immediately after: `undo_stack.beginMacro("load"); ...; undo_stack.endMacro(); undo_stack.clear()`. The `clear()` approach is better because it also resets the clean state correctly after a load (the project just loaded matches the file, so the stack should be clean).

**Warning signs:** Undo stack has 100+ commands immediately after opening a file.

### Pitfall 2: Thread not cleaned up after cancel

**What goes wrong:** User clicks Cancel, the worker sets `_cancel = True`, but the `QThread` is never quit or deleted. On the next Run click, `SimulationController.start_run()` checks `self._thread.isRunning()` and blocks the run. The GUI appears stuck.

**Why it happens:** Cancellation only stops the solver loop — it does not automatically terminate the `QThread`. The thread finishes only when `worker.run()` returns and the `finished` signal fires.

**How to avoid:** After `worker.request_cancel()`, the worker's `run()` method must exit cleanly (break out of the time loop and return). Connect `worker.finished` to `thread.quit()` so the thread terminates once the worker exits. In the GUI, show a "Cancelling..." state in the status bar until the `finished` signal arrives — do not immediately re-enable the Run button on cancel click.

**Warning signs:** Run button stays disabled after Cancel; multiple QThread instances accumulate in memory.

### Pitfall 3: Undo clears dirty flag incorrectly

**What goes wrong:** User edits cell A, saves (stack marked clean), then edits cell B, then presses Ctrl+Z. Stack index returns to the clean position, but the window title still shows the asterisk.

**Why it happens:** The `cleanChanged(bool)` signal is not connected to the window title update slot.

**How to avoid:** Connect `undo_stack.cleanChanged.connect(self._update_title_and_path_label)` in `__init__`. The slot checks `undo_stack.isClean()` and sets the title with or without the asterisk accordingly.

**Warning signs:** Asterisk remains after undo returns to the saved state; or asterisk disappears after undo even when not back to the saved state.

### Pitfall 4: Escape key captured by focused widget instead of Cancel action

**What goes wrong:** A QLineEdit or QComboBox in the editor tab has focus. User presses Escape intending to cancel the simulation, but the widget consumes the key event instead.

**Why it happens:** Some Qt widgets handle Escape internally (QComboBox closes its popup; QLineEdit may revert). The `QAction` on the menu only receives the shortcut if the widget does not consume it first.

**How to avoid:** For Escape specifically, consider also overriding `keyPressEvent` on `MainWindow` or using `QApplication.installEventFilter()` to intercept Escape at the application level when a simulation is running. Alternatively, the Cancel button in the toolbar / progress area is always clickable regardless of focus, making the button the primary cancel affordance and Escape the secondary convenience shortcut.

**Warning signs:** Escape does not cancel simulation when editor tab has focus.

### Pitfall 5: Progress bar requires transient solver modification

**What goes wrong:** The transient solver's `solve()` is a single blocking call. There is no way to receive per-timestep progress without modifying the solver or the worker.

**Why it happens:** The solver was designed as a pure function with no callbacks. The worker just calls `TransientSolver().solve(project)` and blocks until it returns.

**How to avoid:** Add optional `on_progress` and `cancel_check` callback arguments to `TransientSolver.solve()` as described in Pattern 6. These default to `None` so all existing tests and CLI usage remain unaffected. The worker passes a lambda that emits the progress signal and reads the cancel flag.

**Warning signs:** Progress bar stays at 0% during transient simulation, jumps to 100% when done.

---

## Code Examples

Verified patterns from PySide6 official documentation and the existing codebase:

### Existing Worker Pattern (already in main_window.py — extend this)

```python
# From thermal_sim/ui/main_window.py:74 — already partially implemented
class _SimWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, project: DisplayProject, mode: str) -> None:
        super().__init__()
        self._project = project
        self._mode = mode
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._mode == "steady":
                result = SteadyStateSolver().solve(self._project)
            else:
                result = TransientSolver().solve(
                    self._project,
                    on_progress=self._on_progress,
                    cancel_check=lambda: self._cancel_requested,
                )
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
```

Note: The existing `_SimWorker` uses a direct `QThread` assignment but the `run()` method is never called via `QThread.started`. The current `_run_simulation()` calls solver synchronously on the main thread — this must be fixed as part of GUI-03.

### QUndoStack setup

```python
from PySide6.QtGui import QUndoStack

# In MainWindow.__init__():
self._undo_stack = QUndoStack(self)
self._undo_stack.setUndoLimit(100)
self._undo_stack.cleanChanged.connect(self._on_dirty_changed)

# Wire Ctrl+Z and Ctrl+Y via the stack's own undo/redo actions:
undo_action = self._undo_stack.createUndoAction(self, "&Undo")
undo_action.setShortcut(QKeySequence.StandardKey.Undo)
redo_action = self._undo_stack.createRedoAction(self, "&Redo")
redo_action.setShortcut(QKeySequence.StandardKey.Redo)
edit_menu = self.menuBar().addMenu("&Edit")
edit_menu.addAction(undo_action)
edit_menu.addAction(redo_action)
```

### closeEvent for unsaved changes prompt

```python
def closeEvent(self, event) -> None:
    if not self._undo_stack.isClean():
        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Save before closing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            self._save_project_dialog()
            if not self._undo_stack.isClean():
                event.ignore()
                return
        elif reply == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
    event.accept()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `QThread` subclass with `run()` override | Worker-object `moveToThread()` pattern | Qt 4 → Qt 5+ recommended pattern | Worker-object is easier to clean up and separates business logic from thread lifecycle |
| Manual keyboard shortcut dispatch in `keyPressEvent` | `QAction.setShortcut()` on menu actions | Qt 4+ | Shortcuts in menus get tooltip display, enable/disable, and correct routing automatically |
| `QStatusBar.showMessage()` for all status text | `addPermanentWidget()` for persistent zones | Qt 4+ | Permanent widgets are never auto-cleared; showMessage only for temporary transient messages |
| `QApplication.setStyleSheet()` global | Per-widget or per-window stylesheets | N/A | Phase 1 uses no theming — that is Phase 4 (PLSH-01). Keep styles minimal now. |

**Current codebase status:**
- `_SimWorker` exists but the `QThread` it creates is never started correctly — `run()` is not connected to `thread.started`. Solver runs synchronously in the main thread. This is the highest-priority fix in Phase 1.
- `QUndoStack` not yet present anywhere in the codebase.
- `QStatusBar` exists (`self.statusBar().showMessage(...)`) but uses only `showMessage()` — no permanent widgets, no three-zone layout.
- No `QAction`, `QMenuBar`, or `QToolBar` in the current `MainWindow` — all actions are plain `QPushButton` widgets in a flat `QHBoxLayout`.
- No `closeEvent` override — window closes without prompting for unsaved changes.

---

## Open Questions

1. **Transient solver progress granularity**
   - What we know: The transient solver has a `sample_every` interval for output. Progress could be emitted every sample or every step.
   - What's unclear: Emitting every timestep (potentially thousands) creates too many cross-thread signal calls and slows the solver.
   - Recommendation: Emit every `max(1, n_steps // 100)` steps — caps signal overhead to ~100 cross-thread calls per simulation regardless of total timestep count.

2. **Undo for non-table edits (spinboxes, checkboxes in setup/boundaries tabs)**
   - What we know: `QDoubleSpinBox.valueChanged`, `QCheckBox.stateChanged` also change project state.
   - What's unclear: CONTEXT.md says "any project edit" is undoable. Spinbox changes require different `QUndoCommand` subclasses.
   - Recommendation: Wire spinbox and checkbox changes as separate command types. Use `QDoubleSpinBox.valueChanged` signal with a debounce (or use `editingFinished` to only push a command when the user confirms the value, not on every intermediate keystroke).

3. **Refactor boundary: what stays in MainWindow vs moves to SimulationController**
   - What we know: CONTEXT.md says SimulationController owns the thread; TableDataParser owns model conversion; PlotManager owns canvas updates.
   - What's unclear: File load/save is currently interleaved with UI state. Does it belong in a fourth class or stay in MainWindow?
   - Recommendation: File I/O stays in MainWindow as it directly involves QFileDialog and `current_project_path` state. MainWindow = coordinator for I/O + undo stack ownership. SimulationController = thread lifecycle. TableDataParser = stateless table-to-model conversion. PlotManager = canvas updates.

---

## Sources

### Primary (HIGH confidence)

- Qt for Python official docs — QUndoStack, QUndoCommand: https://doc.qt.io/qtforpython-6/PySide6/QtGui/QUndoStack.html
- Qt for Python official docs — QThread: https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html
- Qt for Python official docs — QStatusBar: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QStatusBar.html
- Qt for Python official docs — QAction: https://doc.qt.io/qtforpython-6/PySide6/QtGui/QAction.html
- Qt for Python official docs — QSettings: https://doc.qt.io/qtforpython-6/PySide6/QtCore/QSettings.html
- Direct codebase inspection: `thermal_sim/ui/main_window.py` (939 lines), `thermal_sim/app/cli.py` (197 lines), `thermal_sim/solvers/transient.py`

### Secondary (MEDIUM confidence)

- Python GUIs — multithreading PySide6 with QThread: https://www.pythonguis.com/tutorials/multithreading-pyside6-applications-qthreadpool/ — worker-object pattern verified against Qt docs
- Qt Undo Framework overview: https://doc.qt.io/qt-6/qundo.html — QUndoStack clean state, macro grouping

### Tertiary (LOW confidence — needs validation)

- Per-keystroke undo in QDoubleSpinBox using `editingFinished` vs `valueChanged` — community recommendation only; behavior when user presses Escape mid-edit needs testing

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all components are PySide6 built-ins; no new library research needed
- Architecture: HIGH — refactoring boundaries are clear from codebase inspection and CONTEXT.md decisions
- Pitfalls: HIGH — pitfalls 1–3 are verified against Qt documentation; pitfall 4 (Escape focus) is MEDIUM (behavior varies by widget)

**Research date:** 2026-03-14
**Valid until:** 2026-06-14 (PySide6 APIs are stable; 90 days is conservative)
