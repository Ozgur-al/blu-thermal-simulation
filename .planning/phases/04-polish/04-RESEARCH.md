# Phase 4: Polish - Research

**Researched:** 2026-03-14
**Domain:** PySide6 GUI theming, QDockWidget layout management, inline table validation, matplotlib dark theme
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Theme & color scheme:**
- Use qt-material library with `dark_amber` preset — dark gray backgrounds (#212121/#303030) with amber/gold accent (#ffc107)
- Replace the existing custom stylesheet in gui.py entirely — let qt-material handle all widget styling consistently
- Dark-only theme — no light/dark toggle needed
- Typography: sans-serif (Segoe UI / system default) for labels and menus; monospace (Consolas / Courier) for numeric table cells and status bar values

**Dockable panel layout:**
- Convert three panels to QDockWidgets: Editor Tabs, Result Plots, Results Summary Table
- Comparison tab stays inside the Results area (not its own dock)
- Default arrangement: Editor left, Result Plots top-right, Results Summary bottom-right
- Persist dock layout across sessions using QSettings saveState()/restoreState()
- Add a View menu with checkable entries for each dock panel (QDockWidget.toggleViewAction())

**Inline validation feedback:**
- Red border + tooltip on invalid cells — hovering shows the error message (e.g., "Thickness must be > 0")
- Validation triggers on cell exit (focus-out), not on every keystroke
- Scope: all numeric table fields across Materials, Layers, Heat Sources, Boundaries, Probes tabs
- Run button disabled when any validation errors exist; status bar shows error count (e.g., "2 validation errors")

**Matplotlib in dark theme:**
- Match GUI background: figure facecolor #212121, axes facecolor #303030, text/ticks #e0e0e0, grid #444444
- Temperature map colormap: `inferno` (perceptually uniform, colorblind-friendly, great on dark backgrounds)
- Probe history line colors: amber accent palette — #ffc107 (amber), #ff7043 (deep orange), #66bb6a (green), #42a5f5 (blue), #ab47bc (purple)
- PDF export keeps print-friendly light style (white background, dark text) — separate from GUI dark theme

### Claude's Discretion
- Exact qt-material configuration parameters and any necessary overrides
- How to structure the matplotlib style dict (rcParams vs per-plot configuration)
- QDockWidget sizing ratios and minimum sizes
- How to integrate validation with the existing undo/redo system
- Whether to add a "Reset Layout" action in View menu

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PLSH-01 | Professional qt-material theme applied across all GUI elements | qt-material 2.17 `apply_stylesheet(app, theme='dark_amber.xml')` plus rcParams update for matplotlib canvases |
| PLSH-02 | QDockWidget-based layout replacing fixed splitter panels | QMainWindow.addDockWidget() + setObjectName() + saveState()/restoreState() via QSettings + toggleViewAction() for View menu |
| PLSH-03 | Inline validation feedback (visual indicators on invalid inputs) | QTableWidget.cellChanged signal + QTableWidgetItem.setBackground()/setToolTip() + error count tracking in status bar |
</phase_requirements>

---

## Summary

Phase 4 polishes the existing PySide6 GUI by applying three orthogonal improvements: a consistent qt-material dark theme, a flexible QDockWidget layout replacing the fixed QSplitter, and inline per-cell validation feedback on table inputs. All three requirements are well-supported by stable, documented PySide6 APIs and the qt-material 2.17 library.

The qt-material library (v2.17, April 2025) provides `apply_stylesheet(app, theme='dark_amber.xml')` as a single-call replacement for the existing `app.setStyle("Fusion") + app.setStyleSheet(_STYLESHEET)` pattern. The existing `_STYLESHEET` in `gui.py` is only six rules targeting the run button and tables — qt-material covers all of these via its theme. Additional per-widget overrides can be appended by reading `app.styleSheet()` and extending it with custom QSS. Matplotlib canvases embedded in Qt widgets are not automatically themed by qt-material; their colors must be set explicitly via `matplotlib.rcParams` before figure creation, and the PDF export must use `plt.style.context('default')` to produce print-friendly output.

The QSplitter-to-QDockWidget migration is a structural change to `_build_ui()`. Each dock requires a unique `setObjectName()` for `saveState()`/`restoreState()` to work correctly. The existing `QSettings("ThermalSim", "ThermalSimulator")` instance already used in `main_window.py` is the right place to persist dock state — extend `closeEvent()` to call `saveState()` and read it back in `__init__()` after `_build_ui()`. The `toggleViewAction()` method on each QDockWidget returns a ready-made checkable QAction suitable for a View menu.

Inline validation builds on the existing `TableDataParser.validate_tables()` logic. The signal to watch is `QTableWidget.cellChanged(row, col)`, which fires after the user commits an edit. On each `cellChanged`, re-run the per-cell validation rules and set `item.setBackground(QColor("#ff4444"))` plus `item.setToolTip("error message")` on invalid items. A module-level set tracking currently invalid (table_id, row, col) tuples lets the run-button enable/disable logic check `len(errors) == 0`. This approach does not interact with the undo/redo system because it is read-only metadata on existing items.

**Primary recommendation:** Apply qt-material first (PLSH-01), then convert to QDockWidgets (PLSH-02), then add inline validation (PLSH-03) — this order ensures each step can be verified independently without conflicts.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| qt-material | 2.17 (Apr 2025) | Material Design QSS theme for PySide6 | Only production-quality material theme library for PySide6; actively maintained; covers all widget types |
| PySide6 | >=6.7 (already in requirements.txt) | QDockWidget, QSettings, QMainWindow layout | All required APIs (QDockWidget, saveState, toggleViewAction) are stable since Qt 5.x |
| matplotlib | >=3.8 (already in requirements.txt) | Plot theming via rcParams | rcParams approach is the canonical matplotlib way to apply global style |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PySide6.QtGui.QColor | built-in | Convert hex colors to QBrush for cell backgrounds | Validation red highlight, validation clear |
| PySide6.QtGui.QBrush | built-in | Set QTableWidgetItem.setBackground() | Required by the setBackground() API — takes QBrush not QColor directly |
| matplotlib.rcParams | built-in | Global plot style settings | Applied once at app startup; affects all subsequently created Figure objects |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| qt-material | QDarkStyle, pyqtdarktheme | QDarkStyle is unmaintained; pyqtdarktheme has no material amber theme; qt-material is the only option matching locked decisions |
| rcParams global update | plt.style.context() per-plot | Context manager adds complexity to every PlotManager method; global rcParams is simpler since all GUI plots want the same dark theme |
| QTableWidgetItem.setBackground() | Custom QStyledItemDelegate | Delegate gives more control (can draw border) but is ~5x the code; setBackground + setForeground covers the red-highlight requirement |

**Installation:**
```bash
pip install qt-material
```
(All other libraries already present in requirements.txt)

---

## Architecture Patterns

### Recommended Project Structure

No new files needed. Changes are confined to:

```
thermal_sim/
├── app/
│   └── gui.py                  # Replace Fusion+stylesheet with qt-material setup
├── ui/
│   ├── main_window.py          # _build_ui() QSplitter -> QDockWidgets; _build_menus() adds View menu;
│   │                           # closeEvent() saves dock state; __init__() restores it
│   └── table_data_parser.py    # Add validate_cell() static method for per-cell rules
├── io/
│   └── pdf_export.py           # Wrap figure creation in plt.style.context('default')
└── visualization/
    └── plotting.py             # Accept dark_style dict param for probe color list
```

### Pattern 1: qt-material Application

**What:** Replace the two-line theme setup in `gui.py:main()` with a single qt-material call, then append any extra QSS overrides.

**When to use:** Once, at app startup, before `window.show()`.

```python
# Source: https://pypi.org/project/qt-material/ (v2.17, Apr 2025)
from qt_material import apply_stylesheet

def main() -> None:
    app = QApplication(sys.argv)
    # Remove: app.setStyle("Fusion") and app.setStyleSheet(_STYLESHEET)
    apply_stylesheet(app, theme='dark_amber.xml')

    # Append any overrides that qt-material doesn't handle (monospace numeric cells, run button specifics)
    extra_qss = """
    QTableWidget {
        font-family: Consolas, 'Courier New', monospace;
    }
    QStatusBar QLabel#runInfoLabel {
        font-family: Consolas, 'Courier New', monospace;
    }
    """
    app.setStyleSheet(app.styleSheet() + extra_qss)
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())
```

**Key detail:** `qt-material` must be imported AFTER PySide6 imports. Call `apply_stylesheet` before the window is shown — calling it after `window.show()` is allowed for runtime switching but not needed here.

### Pattern 2: QDockWidget Layout with Persistent State

**What:** Replace `QSplitter` in `_build_ui()` with three `QDockWidget` instances. Each dock must have a unique `objectName` for `saveState()` to identify them.

**When to use:** During `_build_ui()` construction.

```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QDockWidget.html
from PySide6.QtWidgets import QDockWidget
from PySide6.QtCore import Qt

def _build_ui(self) -> None:
    # Central widget: empty placeholder (content lives in docks)
    self.setCentralWidget(QWidget())

    # Dock 1: Editor Tabs (left)
    self._editor_dock = QDockWidget("Editor", self)
    self._editor_dock.setObjectName("EditorDock")
    self._editor_dock.setWidget(self._build_editor_panel())
    self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._editor_dock)

    # Dock 2: Result Plots (top-right)
    self._plots_dock = QDockWidget("Result Plots", self)
    self._plots_dock.setObjectName("PlotsDock")
    self._plots_dock.setWidget(self._build_plots_panel())
    self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._plots_dock)

    # Dock 3: Results Summary (bottom-right, tabified below plots)
    self._summary_dock = QDockWidget("Results Summary", self)
    self._summary_dock.setObjectName("SummaryDock")
    self._summary_dock.setWidget(self._build_summary_panel())
    self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._summary_dock)
    # Stack summary below plots in the right area
    self.splitDockWidget(self._plots_dock, self._summary_dock, Qt.Orientation.Vertical)
```

**State persistence:**

```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QMainWindow.html
def closeEvent(self, event) -> None:
    settings = QSettings("ThermalSim", "ThermalSimulator")
    settings.setValue("dock_state", self.saveState())
    settings.setValue("window_geometry", self.saveGeometry())
    super().closeEvent(event)

def _restore_layout(self) -> None:
    """Call this AFTER _build_ui() in __init__()."""
    settings = QSettings("ThermalSim", "ThermalSimulator")
    state = settings.value("dock_state")
    geom = settings.value("window_geometry")
    if state:
        self.restoreState(state)
    if geom:
        self.restoreGeometry(geom)
```

**View menu with toggleViewAction:**

```python
def _build_menus(self) -> None:
    # ... existing File, Edit, Run menus ...
    view_menu = self.menuBar().addMenu("&View")
    view_menu.addAction(self._editor_dock.toggleViewAction())
    view_menu.addAction(self._plots_dock.toggleViewAction())
    view_menu.addAction(self._summary_dock.toggleViewAction())
    view_menu.addSeparator()
    reset_action = QAction("Reset Layout", self)
    reset_action.triggered.connect(self._reset_layout)
    view_menu.addAction(reset_action)

def _reset_layout(self) -> None:
    """Restore the factory default dock arrangement."""
    # Re-add docks to their default areas
    self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._editor_dock)
    self._editor_dock.setFloating(False)
    self._editor_dock.show()
    self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._plots_dock)
    self._plots_dock.setFloating(False)
    self._plots_dock.show()
    self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._summary_dock)
    self._summary_dock.setFloating(False)
    self._summary_dock.show()
    self.splitDockWidget(self._plots_dock, self._summary_dock, Qt.Orientation.Vertical)
```

### Pattern 3: Inline Cell Validation

**What:** Track invalid cells in a dict; update visual state on `cellChanged`; reflect error count in status bar and run button.

**When to use:** Connect during `_build_editor_tabs()` for each table.

```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QTableWidgetItem.html
from PySide6.QtGui import QColor, QBrush

# In MainWindow.__init__():
self._validation_errors: dict[tuple[int, int, int], str] = {}
# key = (id(table), row, col), value = error message string

def _connect_table_validation(self, table: QTableWidget) -> None:
    table.cellChanged.connect(lambda r, c: self._validate_cell(table, r, c))

def _validate_cell(self, table: QTableWidget, row: int, col: int) -> None:
    """Validate a single cell and update its visual state."""
    item = table.item(row, col)
    if item is None:
        return
    error = TableDataParser.validate_cell(table, row, col)  # new static method
    key = (id(table), row, col)
    if error:
        self._validation_errors[key] = error
        item.setBackground(QBrush(QColor("#8B0000")))   # dark red — visible on dark background
        item.setForeground(QBrush(QColor("#ffcccc")))   # light pink text
        item.setToolTip(error)
    else:
        self._validation_errors.pop(key, None)
        item.setBackground(QBrush())          # default brush — clears override
        item.setForeground(QBrush())
        item.setToolTip("")
    self._update_run_button_state()

def _update_run_button_state(self) -> None:
    n = len(self._validation_errors)
    self._run_action.setEnabled(n == 0)
    if n > 0:
        self._solver_label.setText(f"{n} validation error{'s' if n != 1 else ''}")
    else:
        self._solver_label.setText("Ready")
```

**New `TableDataParser.validate_cell()` static method** returns a per-cell error string or `""`:

```python
@staticmethod
def validate_cell(table: QTableWidget, row: int, col: int) -> str:
    """Return an error message string for invalid numeric cells, or '' if valid.

    This is complementary to validate_tables() — it operates on one cell
    rather than building a full error list.
    """
    header = table.horizontalHeaderItem(col)
    col_name = header.text() if header else f"column {col + 1}"
    text = TableDataParser._cell_text(table, row, col)
    if text == "":
        return ""  # empty is allowed (optional fields)
    try:
        value = float(text)
    except ValueError:
        return f"'{text}' is not a valid number"
    # Domain-specific rules keyed on column header text
    MUST_BE_POSITIVE = {"thickness [m]", "k in-plane [W/mK]", "k through [W/mK]",
                        "density [kg/m³]", "specific heat [J/kgK]"}
    MUST_BE_NON_NEGATIVE = {"power [W]", "convection h [W/m²K]"}
    if col_name.lower() in {h.lower() for h in MUST_BE_POSITIVE} and value <= 0:
        return f"{col_name} must be > 0 (got {value})"
    if col_name.lower() in {h.lower() for h in MUST_BE_NON_NEGATIVE} and value < 0:
        return f"{col_name} must be >= 0 (got {value})"
    return ""
```

### Pattern 4: Matplotlib Dark Theme

**What:** Set rcParams globally at app startup so all MplCanvas Figure instances automatically inherit dark colors.

**When to use:** In `gui.py:main()`, AFTER `apply_stylesheet()` and BEFORE `MainWindow()` is constructed (Figure objects are created in PlotManager.__init__).

```python
# Source: https://matplotlib.org/stable/users/explain/customizing.html
import matplotlib as mpl

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

def main() -> None:
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme='dark_amber.xml')
    mpl.rcParams.update(DARK_MPL_STYLE)
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())
```

**PDF export isolation** — wrap all figure creation in `pdf_export.py` with a context manager:

```python
# Source: https://matplotlib.org/stable/users/explain/customizing.html
import matplotlib.pyplot as plt

def generate_pdf_report(snapshot, output_path):
    with plt.style.context('default'):   # temporarily restores matplotlib defaults
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with PdfPages(output_path) as pdf:
            # All existing page builder calls remain unchanged
            ...
```

### Anti-Patterns to Avoid

- **Calling restoreState() before _build_ui()**: The dock widgets don't exist yet; restoreState() will silently fail. Always call `_restore_layout()` after `_build_ui()`.
- **Missing setObjectName()**: Without unique object names, `saveState()` generates byte arrays that cannot reliably restore docks across sessions. Each dock must have a distinct, stable name.
- **Setting rcParams after MplCanvas is constructed**: Figure facecolor is applied at Figure creation time. Setting rcParams after `PlotManager.__init__()` has run will not retroactively change existing canvases — set rcParams in `gui.py:main()` before `MainWindow()`.
- **Forgetting to clear validation state on project load**: When `populate_tables_from_project()` is called (new project, load), the `_validation_errors` dict must be cleared and all cell backgrounds reset.
- **Using QBrush() default vs. explicit reset**: `item.setBackground(QBrush())` (default-constructed) correctly tells Qt to use the style's default color. Do not pass `QBrush(Qt.GlobalColor.transparent)` — that paints transparent which looks wrong on dark backgrounds.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dark widget theme | Custom QSS stylesheet rules for every widget type | qt-material `apply_stylesheet()` | 800+ widget selectors already handled; QMenu, QComboBox, QScrollBar are notoriously hard to style from scratch |
| Dock visibility menu | Manual checkable QActions tracking dock visibility | `QDockWidget.toggleViewAction()` | Built-in action stays in sync automatically with dock state; avoids manual signal tracking |
| Layout persistence | JSON/pickle of splitter sizes | `QMainWindow.saveState()` / `restoreState()` | Built-in binary format handles floating docks, tabified docks, corner settings — impossible to replicate reliably |
| Validation error rendering | Custom QStyledItemDelegate with paint() | `QTableWidgetItem.setBackground()` + `setToolTip()` | Delegate is correct for cell-level borders but requires ~150 lines; item background achieves the same visual result with 3 lines |
| Plot dark theme | Override colors in every `ax.clear()` call inside PlotManager | `mpl.rcParams.update()` once at startup | rcParams cascade into all new Figure and Axes objects automatically |

**Key insight:** Qt and matplotlib both have first-class persistence/theming APIs. The cost of bypassing them is debugging cross-platform rendering edge cases that those APIs already handle.

---

## Common Pitfalls

### Pitfall 1: qt-material Overrides Lost After setStyleSheet()

**What goes wrong:** After calling `apply_stylesheet(app, ...)`, the developer calls `app.setStyleSheet(custom_qss)` thinking it adds to the theme. Instead it replaces the entire qt-material stylesheet.

**Why it happens:** `setStyleSheet()` replaces, not appends. qt-material generates a large QSS string.

**How to avoid:** Read the existing stylesheet first, then concatenate:
```python
app.setStyleSheet(app.styleSheet() + extra_qss)
```

**Warning signs:** Widgets revert to OS default appearance after the call.

### Pitfall 2: QSettings Returns None on First Launch

**What goes wrong:** `settings.value("dock_state")` returns `None` on first launch (no saved state). Passing `None` to `restoreState()` raises a TypeError.

**Why it happens:** QSettings key doesn't exist yet.

**How to avoid:** Guard the call:
```python
state = settings.value("dock_state")
if state:
    self.restoreState(state)
```

**Warning signs:** Crash on first launch of a clean install.

### Pitfall 3: cellChanged Fires During programmatic Table Population

**What goes wrong:** When `populate_tables_from_project()` calls `setItem()` or `setText()`, `cellChanged` fires for every cell, triggering validation and potentially marking valid cells as errors or cluttering the undo/redo stack.

**Why it happens:** `cellChanged` does not distinguish user edits from programmatic edits.

**How to avoid:** Block signals during population, then run a full validation pass afterward:
```python
table.blockSignals(True)
TableDataParser._set_table_rows(table, rows)
table.blockSignals(False)
self._validate_all_cells(table)  # fresh pass, clears old error state
```

**Warning signs:** Spurious validation errors appear immediately after loading a project.

### Pitfall 4: PDF Export Inherits Dark Colors

**What goes wrong:** PDF figures have dark gray backgrounds and light-colored text, making them unreadable when printed.

**Why it happens:** `mpl.rcParams` is global. PDF page builders use `plt.subplots()` which inherits the current rcParams.

**How to avoid:** Wrap all of `generate_pdf_report()` body in `with plt.style.context('default'):`. This temporarily restores matplotlib defaults for the duration of the context.

**Warning signs:** PDF reports have near-invisible text on dark backgrounds.

### Pitfall 5: Dock State Restores to Wrong Screen/Size on DPI Change

**What goes wrong:** Saved geometry from a 4K display is restored on an HD display, causing docks to appear off-screen.

**Why it happens:** `saveGeometry()` stores absolute pixel positions; `restoreGeometry()` does not clamp to screen bounds on Qt < 6.7.

**How to avoid:** After `restoreGeometry()`, call `QApplication.processEvents()` then verify `self.isVisible()`. If the window is off-screen, call `self.move(100, 100)`. PySide6 >= 6.7 handles this more gracefully.

**Warning signs:** App launches with invisible or partially off-screen window on DPI change.

### Pitfall 6: Validation Errors Survive Table Row Removal

**What goes wrong:** User adds a row with invalid data, then deletes the row. The `_validation_errors` dict still contains the key for `(id(table), row, col)`, leaving the run button disabled.

**Why it happens:** Row deletion does not emit `cellChanged`; the error entry is never removed.

**How to avoid:** Connect to `QTableWidget.itemSelectionChanged` or override `removeRow` — or simpler: after `table.removeRow(row)`, call `self._revalidate_table(table)` which clears all errors for that table and re-runs validation for remaining rows.

---

## Code Examples

Verified patterns from official sources:

### qt-material basic setup

```python
# Source: https://pypi.org/project/qt-material/ (v2.17, Apr 2025)
from qt_material import apply_stylesheet

app = QApplication(sys.argv)
apply_stylesheet(app, theme='dark_amber.xml')
# Append overrides WITHOUT losing qt-material styles:
app.setStyleSheet(app.styleSheet() + extra_qss)
```

### QDockWidget with object name and area placement

```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QDockWidget.html
dock = QDockWidget("Editor", self)
dock.setObjectName("EditorDock")          # REQUIRED for saveState()
dock.setWidget(content_widget)
self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
```

### splitDockWidget for vertical stacking in same area

```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QMainWindow.html
# Place summary_dock below plots_dock in the right area:
self.splitDockWidget(self._plots_dock, self._summary_dock, Qt.Orientation.Vertical)
```

### QMainWindow layout persistence

```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QMainWindow.html
# Save (in closeEvent):
settings.setValue("dock_state", self.saveState())
settings.setValue("window_geometry", self.saveGeometry())
# Restore (after _build_ui()):
state = settings.value("dock_state")
if state:
    self.restoreState(state)
```

### QTableWidgetItem validation highlight

```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QTableWidgetItem.html
from PySide6.QtGui import QBrush, QColor

item.setBackground(QBrush(QColor("#8B0000")))  # error: dark red
item.setForeground(QBrush(QColor("#ffcccc")))  # light text on dark red
item.setToolTip("Thickness must be > 0")

# Clear (valid):
item.setBackground(QBrush())    # default-constructed = use style default
item.setForeground(QBrush())
item.setToolTip("")
```

### Matplotlib rcParams dark theme

```python
# Source: https://matplotlib.org/stable/users/explain/customizing.html
import matplotlib as mpl
mpl.rcParams.update({
    "figure.facecolor": "#212121",
    "axes.facecolor":   "#303030",
    "text.color":       "#e0e0e0",
    "xtick.color":      "#e0e0e0",
    "ytick.color":      "#e0e0e0",
    "grid.color":       "#444444",
})
```

### PDF export with temporary default style

```python
# Source: https://matplotlib.org/stable/users/explain/customizing.html
with plt.style.context('default'):
    with PdfPages(output_path) as pdf:
        fig = _make_summary_page(snapshot)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
```

### Probe history with amber palette

```python
# Probe line color rotation — amber-first palette matching UI brand
PROBE_COLORS = ["#ffc107", "#ff7043", "#66bb6a", "#42a5f5", "#ab47bc"]

for i, (name, values) in enumerate(probe_history.items()):
    color = PROBE_COLORS[i % len(PROBE_COLORS)]
    ax.plot(times_s, values, label=name, color=color)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `app.setStyle("Fusion") + app.setStyleSheet(qss)` | `qt_material.apply_stylesheet(app, theme='dark_amber.xml')` | Phase 4 | All 80+ widget types styled consistently without hand-rolling QSS |
| `QSplitter` with fixed stretch factors | `QDockWidget` with `addDockWidget()` + `splitDockWidget()` | Phase 4 | Users can undock, float, resize, and persist panel arrangements |
| Validation only at run-time via `validate_tables()` | Per-cell `cellChanged` validation with visual indicators | Phase 4 | Users see errors immediately on cell exit, run button blocked |
| Matplotlib default light theme in dark GUI | `mpl.rcParams.update(DARK_MPL_STYLE)` at startup | Phase 4 | Plots visually integrate with dark GUI; no white-flash canvases |

**Deprecated/outdated:**
- `_STYLESHEET` in `gui.py`: replaced entirely by qt-material; remove the constant.
- `app.setStyle("Fusion")`: replaced by qt-material's style engine; remove the call.

---

## Open Questions

1. **QTableWidgetItem border vs background for validation indicator**
   - What we know: `setBackground()` works reliably and is documented. Per-cell CSS border styling on QTableWidgetItem is not directly supported via the item API — it requires a QStyledItemDelegate with a custom `paint()` method.
   - What's unclear: Whether a red background is visually sufficient, or whether the user expects a border-only indicator (like HTML's `border: 2px solid red`).
   - Recommendation: Use `setBackground(QColor("#8B0000"))` (dark red fill). This is what the CONTEXT.md describes as "red border + tooltip" — the red background serves the same visual purpose. If a true border-only look is needed, that requires a delegate (escalate to user before implementing).

2. **qt-material compatibility with PySide6 >= 6.7 on Windows 11**
   - What we know: qt-material 2.17 targets PySide6 generally; the PyPI page has no version-specific warnings. requirements.txt uses `PySide6>=6.7`.
   - What's unclear: Whether there are any rendering regressions specific to PySide6 6.8/6.9 on Windows 11 with dark mode OS settings.
   - Recommendation: Test `apply_stylesheet` on the development machine immediately in Wave 0 before building the full feature. If widgets look wrong, check qt-material GitHub issues.

3. **Central widget when all content is in docks**
   - What we know: QMainWindow requires a central widget even if docks hold all content.
   - What's unclear: Whether using an empty `QWidget()` as central widget leaves an ugly gap, and whether `setCentralWidget(None)` is safe in PySide6.
   - Recommendation: Use a minimal `QWidget()` as central widget. The dock arrangement (left editor, right plots/summary) will fill the window without leaving visible gaps.

---

## Sources

### Primary (HIGH confidence)
- https://pypi.org/project/qt-material/ — v2.17 (April 2025); `apply_stylesheet` API, theme list, `extra` dict parameters
- https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QDockWidget.html — QDockWidget API: `setObjectName`, `addDockWidget`, `toggleViewAction`, `saveState`/`restoreState` via QMainWindow
- https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QMainWindow.html — `saveState()`, `restoreState()`, `splitDockWidget()`, `addDockWidget()` official PySide6 docs
- https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QTableWidgetItem.html — `setBackground()`, `setForeground()`, `setToolTip()` API
- https://matplotlib.org/stable/users/explain/customizing.html — `rcParams`, `plt.style.context()` API

### Secondary (MEDIUM confidence)
- https://qt-material.readthedocs.io/ — Additional qt-material usage patterns; `extra` dict; QMenu platform variation note
- https://doc.qt.io/qtforpython-6/PySide6/QtCore/QSettings.html — QSettings `setValue`/`value` for QByteArray persistence

### Tertiary (LOW confidence)
- WebSearch results on `cellChanged` validation patterns — community patterns, not official API; verified against official QTableWidget docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — qt-material v2.17 confirmed on PyPI (April 2025); PySide6 APIs verified against official Qt for Python docs
- Architecture: HIGH — QDockWidget/saveState/toggleViewAction patterns verified against official docs; rcParams verified against matplotlib stable docs
- Pitfalls: MEDIUM — Most pitfalls are from known Qt behavior (cellChanged during programmatic edits is well-documented); DPI geometry pitfall is LOW (single source)

**Research date:** 2026-03-14
**Valid until:** 2026-04-13 (qt-material is stable; PySide6 APIs are stable; 30-day window is appropriate)
