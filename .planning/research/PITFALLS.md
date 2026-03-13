# Pitfalls Research

**Domain:** Desktop engineering simulation tool — Python/PySide6, Phase 4 upgrade (prototype-to-professional)
**Researched:** 2026-03-14
**Confidence:** MEDIUM-HIGH (confirmed by official docs and community post-mortems; some claims cross-verified with multiple sources)

---

## Critical Pitfalls

### Pitfall 1: Running Simulation on the Main Qt Thread

**What goes wrong:**
The parametric sweep and power-cycling simulations are triggered by a GUI button click. If the solver runs synchronously in the main thread, the GUI freezes completely — the window stops painting, buttons become unresponsive, and on Windows the title bar shows "(Not Responding)". For a parametric sweep over 20+ parameter combinations, each potentially taking seconds, this freeze can last minutes.

**Why it happens:**
Qt's event loop runs in the main thread. Any long computation that blocks `exec_()` starves the event loop of cycles. The current codebase already calls solvers directly in button handlers inside `MainWindow`; adding parametric loops without threading multiplies the problem.

**How to avoid:**
Move all solver calls into a `QObject` worker, `moveToThread()` it onto a `QThread`, and communicate via signals only. Never call `QThread.run()` directly or subclass `QThread` with business logic — use the worker-object pattern. Progress updates must be emitted as signals (`progress_updated = Signal(int)`), not written to labels from the worker. Keep the worker as an instance attribute on `MainWindow` to prevent garbage collection killing the thread mid-run. Connect `finished` → `thread.quit()` → `worker.deleteLater()` → `thread.deleteLater()` to clean up correctly.

**Warning signs:**
- Any solver call not wrapped in a `QThread` worker
- Button handlers that call `SteadyStateSolver().solve()` or `TransientSolver().solve()` directly
- Parametric loops inside button slots

**Phase to address:** GUI overhaul / parametric sweep phase (Phase 4)

---

### Pitfall 2: Breaking Backward Compatibility on JSON Load

**What goes wrong:**
Phase 4 adds new model fields — power profiles for time-varying sources, sweep parameter definitions, material import metadata. If `from_dict()` is updated to require these new keys, every existing `.json` project file saved before Phase 4 will throw `KeyError` on load. Engineers who've been building project files for months suddenly cannot open their work.

**Why it happens:**
The current `from_dict()` already uses `.get(key, default)` correctly for optional fields, but it's easy to slip up when adding new required structure (like a new required sub-object for `power_profile`). The `TransientConfig.from_dict()` method validates `method != "implicit_euler"` and raises — adding a new method string value without checking for the old default is a migration trap. Any `__post_init__` validation that raises on missing new fields will silently break old files.

**How to avoid:**
Every new field added to `from_dict()` must use `.get(key, sensible_default)`, never `data[key]`. New sub-objects must be entirely optional with a factory default. Add a `schema_version` integer field to the JSON root and write a migration function that upgrades v1 → v2 → v3 sequentially. Test backward compatibility explicitly: load every file in `examples/` after any model change. Never rename existing keys — add new keys alongside old ones and deprecate.

**Warning signs:**
- Any `data["new_field"]` (bracket access, not `.get()`) in a new `from_dict()` path
- New `__post_init__` validation that checks for a field that didn't exist before
- No `examples/` load test after model changes
- `TransientConfig.from_dict()` accepting a new `method` value without a default fallback

**Phase to address:** Every phase that touches data models; especially power-cycling and parametric sweep additions

---

### Pitfall 3: PyInstaller onefile Mode Causes Antivirus Quarantine and Slow Startup

**What goes wrong:**
`--onefile` bundles everything into a self-extracting archive that unpacks to `%TEMP%` on every launch. Corporate Windows environments with endpoint protection (Defender, CrowdStrike, Cylance) routinely flag or quarantine freshly extracted executables from temp directories. Even when not quarantined, on cold startup with a large bundle (numpy + scipy + matplotlib + PySide6 ≈ 200-400 MB uncompressed) startup time is 15-30 seconds, which feels broken to a non-programmer user.

**Why it happens:**
`--onefile` is tempting because it produces a single file easy to share via email or Teams. But the temp-extraction pattern is exactly what malware does, and heuristic scanners trigger on it. The project's no-admin constraint means users cannot add exclusions to their AV software.

**How to avoid:**
Use `--onedir` (default PyInstaller mode) and distribute the entire `dist/app/` folder as a zip. Place the launcher `.exe` at the top level of the folder. Create a `launch.bat` or simple shortcut that points to `dist/app/app.exe`. This avoids temp-directory extraction, starts faster, and does not trigger AV heuristics. The folder looks messy but users only ever double-click one file. Do not use UPX compression — it triggers additional AV false positives.

**Warning signs:**
- Build spec using `--onefile` or `EXE(console=False, onefile=True)`
- UPX compression enabled in spec file
- No test on a machine with corporate AV before declaring packaging done

**Phase to address:** Packaging phase (Phase 4)

---

### Pitfall 4: MainWindow God Object Collapses Under Phase 4 Feature Weight

**What goes wrong:**
`main_window.py` is already 939 lines mixing UI construction, event handling, data validation, simulation dispatch, and plot management. Phase 4 adds parametric sweep UI, PDF export dialogs, power-profile editors, and improved results comparison — all of which are candidate for adding more methods to `MainWindow`. At ~1500+ lines, the class becomes impossible to test, impossible to reason about, and extremely difficult to extend without causing regressions.

**Why it happens:**
The prototype was built fast; everything went into `MainWindow` because it was the only class. Adding Phase 4 features without first extracting controllers makes each feature entangle with all the others through shared `self.last_*` state.

**How to avoid:**
Before adding Phase 4 features, extract three collaborators from `MainWindow`: (1) a `TableDataParser` that converts all table-widget data to/from model objects, (2) a `SimulationController` (a `QObject`) that owns the `QThread` worker and exposes signals for results, and (3) a `PlotManager` that owns the matplotlib canvases and update logic. `MainWindow` then becomes a thin coordinator. CONCERNS.md already identifies this decomposition as the right path. Extract before adding, not after.

**Warning signs:**
- Any new Phase 4 feature implemented directly as methods on `MainWindow`
- Methods longer than 50 lines in `main_window.py`
- `self.last_*` state being read by more than two distinct methods
- New signals connected inside `__init__` growing past ~20 connections

**Phase to address:** GUI overhaul phase (Phase 4, first task before adding features)

---

### Pitfall 5: PDF Report Missing Fonts at Runtime on Target Machines

**What goes wrong:**
ReportLab uses font lookup at PDF generation time. If the report uses a font that is not embedded in the PDF and is not installed on the end user's machine, the PDF renderer (Acrobat, Windows PDF viewer) either substitutes a wrong font or fails entirely. On restricted corporate machines, the font set is often non-standard. The PyInstaller bundle does not automatically bundle system fonts.

**Why it happens:**
Developers test PDF generation on their own dev machine where the font is installed. ReportLab's `registerFont()` with a `.ttf` path works fine during development. After packaging with PyInstaller, the `.ttf` path becomes invalid because data files must be explicitly added to the spec's `datas=[]` list and accessed via `sys._MEIPASS` at runtime.

**How to avoid:**
Either (a) use only ReportLab's 14 built-in Type1 fonts (Helvetica, Times, Courier and variants) which are always available without embedding — this is the safest path for an internal tool, or (b) embed a small subset of an open-source font (e.g., DejaVu Sans) as a data file in the package, add it to the PyInstaller `datas` list, and resolve the path with a helper that checks `sys._MEIPASS` vs. the normal module path. Option (a) is recommended unless engineering brand guidelines require a specific typeface.

**Warning signs:**
- `reportlab.pdfbase.pdfmetrics.registerFont(TTFont(...))` with a hardcoded path
- No `sys._MEIPASS` path resolution helper in the codebase
- PDF generation tested only on developer machine, not from a PyInstaller build
- Font file not listed in PyInstaller spec `datas`

**Phase to address:** PDF report phase (Phase 4)

---

### Pitfall 6: Parametric Sweep Accumulating Full Transient Arrays in Memory

**What goes wrong:**
A parametric sweep that varies 5 parameters × 4 values each produces up to 1024 runs. If each transient run stores the full `temperatures_time_c` array (currently `[nt, n_layers, ny, nx]`), and a 500×500 mesh with 1000 timesteps produces ~4 GB per run, the sweep either exhausts RAM or swaps to disk and becomes unusably slow — even at default mesh (30×20) with 1200 timesteps, 10-run sweeps already store ~350 MB of numpy arrays before results are aggregated.

**Why it happens:**
`TransientResult` stores the complete 4-D array in memory (confirmed in `transient.py` line 56-68). This is fine for single runs. Parametric sweeps naively iterate and collect results the same way, holding all of them in memory simultaneously.

**How to avoid:**
The sweep engine must define its result summary at design time: it only needs peak temperature per layer, probe max/mean, and final temperature map — not the full time history. Extract summary statistics immediately after each run inside the worker, release the full array, and store only the summary dict. The sweep result is a list of `{params: dict, summary: dict}` — never a list of `TransientResult`. The full transient result of a single run can optionally be exported to CSV if the user flags it.

**Warning signs:**
- Parametric sweep that stores a `list[TransientResult]` or `list[SteadyStateResult]`
- No `summary()` extraction step between run completion and result storage
- Memory profiling not part of sweep integration test

**Phase to address:** Parametric sweep phase (Phase 4)

---

### Pitfall 7: Power Cycling Timestep / LU Factorization Invalidation

**What goes wrong:**
The current transient solver pre-factors the LHS matrix with `splu()` once before the time loop because the matrix `A + C/dt` is constant when `dt` is fixed. Power cycling (varying heat source power over time) changes `b_vector` each timestep but not the matrix — so this is safe. However, if power cycling is implemented by rebuilding the thermal network each step (re-calling `build_thermal_network()`) or by modifying boundary conditions that affect the matrix, the LU factor is stale and results are silently wrong.

**Why it happens:**
The distinction between "right-hand side changes" (power input, boundary temperatures) and "matrix changes" (topology, boundary condition coefficients, geometry) is subtle. Developers adding power cycling may call `build_thermal_network()` in the time loop to update `b_vector`, which also regenerates the matrix, invalidating the pre-factored LU without triggering an error.

**How to avoid:**
Power profiles must only update `b_vector` (the forcing term), never the matrix. Separate `build_thermal_network()` into two concerns: `build_matrix()` (topology, BCs, capacitance — called once) and `build_forcing(t)` (heat source power at time t — called each step). Assert inside the solver that the matrix shape does not change between steps. Document this invariant explicitly.

**Warning signs:**
- Any call to `build_thermal_network()` inside a time-stepping loop
- Power profile implementation that modifies `BoundaryConditions` objects at runtime
- No assertion or test that LU factorization remains valid through a duty-cycle run

**Phase to address:** Power cycling / time-varying heat source phase (Phase 4)

---

### Pitfall 8: Resource Path Resolution Breaks After PyInstaller Packaging

**What goes wrong:**
The application calls `_load_startup_project()` from a hardcoded relative path (e.g., `"examples/steady_uniform.json"`). When packaged with PyInstaller, the working directory is wherever the user double-clicks the exe, and relative paths to bundled data files no longer resolve. The startup project silently fails to load (currently caught by a bare `except Exception` on line 383), leaving the user with a blank — confusing for a non-programmer who expects a working example on first launch.

**Why it happens:**
Relative paths work during development because `python -m thermal_sim.app.gui` is run from the repo root. After packaging, bundled files live under `sys._MEIPASS` and the working directory is unpredictable.

**How to avoid:**
Create a `resources.py` module with a `get_resource_path(relative_path: str) -> Path` helper that returns `Path(sys._MEIPASS) / relative_path` when frozen, and `Path(__file__).parent.parent / relative_path` otherwise. Add all example files to the PyInstaller spec `datas`. Replace every hardcoded relative path in the codebase with this helper. Replace the bare `except Exception` on startup load with a specific `FileNotFoundError` / `json.JSONDecodeError` handler that logs a warning.

**Warning signs:**
- `open("examples/...")` or `Path("examples/...")` anywhere in application code
- No `sys.frozen` / `sys._MEIPASS` check in path resolution
- Bare `except Exception` on file load that silently discards the error
- PyInstaller spec with no `datas=` entries for example files

**Phase to address:** Packaging phase (Phase 4)

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| All logic in `MainWindow` | Fast prototype development | Untestable, can't add features without regression risk | Phase 1-3 prototype only — never beyond Phase 4 start |
| Bare `except Exception` in GUI | Prevents crashes on bad input | Hides real bugs; makes debugging production issues impossible | Never — replace with specific exception types |
| `assert` for control flow (`assert self.last_transient_result is not None`) | One-liner | Silently disabled with `python -O`; packaged apps should never use `-O` but it's an invisible footgun | Never — use `if x is None: raise RuntimeError(...)` |
| No `schema_version` in JSON | Simpler initial format | Any future field change requires guessing file age; migrations become impossible | Acceptable in Phase 1; must be added before Phase 4 adds new fields |
| `>=` version pins in `requirements.txt` | Always gets latest fixes | numpy 2.x or scipy breaking changes will silently corrupt a packaged build | Fine during active dev; pin upper bounds before packaging |
| Blocking solver call in button handler | Simpler code | GUI freezes; fatal for non-programmer users who will force-close the app | Never for parametric sweep; acceptable for sub-second single runs only |

---

## Integration Gotchas

Common mistakes when connecting the components added in Phase 4.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Matplotlib figure → PDF via ReportLab | Saving figure to disk as PNG then passing file path to ReportLab `Image()` | Render figure to `io.BytesIO` buffer (`fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')`), pass buffer directly to `reportlab.platypus.Image(buf)` — no temp files |
| QThread worker → MainWindow UI update | Calling `self.label.setText()` from inside the worker's `run()` method | Emit a `Signal(str)` from worker; connect to `label.setText` in `MainWindow` — all widget updates from main thread only |
| PyInstaller `--add-data` for JSON examples | Path separator: `--add-data "examples;examples"` on Windows (semicolon, not colon) | Use the spec file `datas=[("examples", "examples")]` to avoid shell quoting hell; verify with `os.listdir(sys._MEIPASS)` debug print |
| ReportLab + matplotlib colorbar | `tight_layout()` called before saving to buffer clips the colorbar | Call `fig.savefig(buf, bbox_inches='tight')` explicitly — `tight_layout()` alone is not sufficient when colorbars are present |
| Parametric sweep result display | Rebuilding the entire results table from scratch on every new result signal | Use `QAbstractTableModel` backed by the growing results list; `beginInsertRows()` / `endInsertRows()` for incremental updates |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full `TransientResult` stored per sweep run | Memory grows linearly with sweep size; app hangs or crashes | Extract summary stats immediately, release array | ~10 runs at default mesh, ~3 runs at 200×150 mesh |
| `canvas.draw()` called on every timestep result signal | Matplotlib redraws are expensive; GUI animation lags far behind computation | Throttle: only redraw if >250 ms since last draw, or redraw only on `finished` signal | Noticeable from first run; severe with 1000+ timestep transients |
| Rebuilding all QTableWidget rows on every model change | Table flickers; scroll position resets; slow for large probe/layer counts | Patch only changed rows; or use `QAbstractTableModel` for read-only result tables | Noticeable at ~50 rows; severe at ~200 |
| PDF generation blocking main thread | App freezes during report generation (reportlab with embedded figures is slow) | Run PDF generation in QThread worker same as solver | Large reports (many figures) take 2-5 seconds; worse with high-DPI figure export |
| Re-calling `build_thermal_network()` at every parametric step | Network rebuild is significant CPU even if only one parameter changes | Build network once per sweep run (correct), not once per timestep | Immediate: transient sweep runs become 10× slower |

---

## UX Pitfalls

Common user experience mistakes for non-programmer engineering tool users.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No progress indicator during long runs | Users cannot tell if app is frozen or running; they force-close it | Progress bar + cancel button for any computation over ~1 second; show current sweep iteration (e.g., "Run 3 of 20") |
| Error messages that expose Python tracebacks | "KeyError: 'material'" means nothing to a hardware engineer | Catch all solver/IO errors in `SimulationController`; present a one-sentence English message ("Layer 'Copper' references unknown material — check the Materials tab") |
| Parametric sweep results with no unit labels | Engineers cannot interpret a table of bare numbers | Every result column must include units in the header: "Peak T (°C)", "T_ambient delta (K)", "Time to 80°C (s)" |
| "Run" button stays active during sweep | User clicks Run again mid-sweep, launching a second worker thread that conflicts with the first | Disable Run button and all editing controls while worker is active; re-enable only in `finished` slot |
| PDF report that opens immediately in a modal dialog | Engineers want to generate a report and keep working | Save PDF to disk and show a non-modal notification with an "Open" link; do not block the UI |
| Unsaved-changes warning missing on exit | Engineers lose parameter edits when closing accidentally | Implement `closeEvent()` override that checks a dirty flag; prompt "Save before closing?" |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces for Phase 4.

- [ ] **Parametric sweep:** Runs all combinations, produces a result list — verify that memory is released between runs, cancel mid-sweep works cleanly, and results persist after the worker thread is destroyed
- [ ] **PDF report:** Generates a file — verify the file opens correctly on a machine other than the developer's, fonts render correctly, all figures are the right size, and generation works from the packaged exe (not just from source)
- [ ] **Power cycling:** Simulates duty-cycle power — verify that LU factorization is not being re-computed each step, that time-averaged temperatures are physically correct against a known analytical case, and that the GUI shows the time-varying power profile
- [ ] **GUI overhaul:** Looks polished in screenshots — verify it is usable at 1366×768 (smallest common corporate laptop resolution), that all editing actions are reachable without scrolling horizontally, and that tab order is logical for keyboard-only navigation
- [ ] **PyInstaller packaging:** `app.exe` launches — verify on a clean machine with no Python installed, with corporate AV active, from a path containing spaces, and from a network share (common corporate workflow)
- [ ] **JSON backward compat:** New fields load without errors — verify by running the full `examples/` test suite against the old project files after any `from_dict()` change
- [ ] **One-click launch:** Double-clicking the exe opens the GUI — verify there is no console window flash, the window icon appears in the taskbar (requires `SetCurrentProcessExplicitAppUserModelID`), and the startup example project loads

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| GUI freeze from blocking solver | MEDIUM | Extract `SimulationController` with `QThread`; requires refactoring `MainWindow` button handlers but not the solver core |
| JSON backward compat broken | HIGH | Write a migration script that reads old format, adds default values for missing fields, rewrites as new format; communicate to all users to migrate their files manually |
| PyInstaller AV quarantine | MEDIUM | Switch from `--onefile` to `--onedir`; rebuild and redistribute folder zip; update launch instructions |
| Font missing in PDF on target machine | LOW | Switch to ReportLab built-in fonts (Helvetica/Times); no architectural changes required |
| MainWindow god object too large to maintain | HIGH | Incremental extraction: start with `TableDataParser` (lowest risk), then `PlotManager`, then `SimulationController`; each extraction is a standalone refactor with its own test |
| Memory exhaustion in parametric sweep | MEDIUM | Add summary-only extraction immediately after each run; requires changing sweep accumulation loop but not the solver |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Blocking solver / GUI freeze | GUI overhaul + refactor (Phase 4, week 1) | Run a 10-second computation from GUI; confirm window remains responsive |
| JSON backward compat breaks | Every model-change task | Load all `examples/*.json` files in CI after any `from_dict()` change |
| PyInstaller AV / onefile | Packaging phase (Phase 4, last milestone) | Test `--onedir` build on a clean machine with Defender enabled |
| PDF font missing after packaging | PDF report phase (Phase 4) | Generate report from the exe build and open on a second machine |
| MainWindow god object growth | GUI overhaul (Phase 4, before adding features) | `main_window.py` must be under 400 lines after extraction; enforce with a line-count check |
| Parametric sweep memory bloat | Parametric sweep phase (Phase 4) | Profile memory with `tracemalloc` during a 20-run sweep; peak must stay under 500 MB |
| Power cycling LU invalidation | Power cycling phase (Phase 4) | Unit test: run a 2-layer model with duty-cycle power; compare final temperature to analytical steady-state average |
| Resource path breaks after packaging | Packaging phase (Phase 4) | Startup example project loads correctly from `dist/app/app.exe` on a clean machine |

---

## Sources

- PyInstaller official documentation — onefile vs onedir, data files, hidden imports: https://pyinstaller.org/en/stable/operating-mode.html and https://pyinstaller.org/en/stable/usage.html (HIGH confidence)
- PySide6 packaging tutorial (pythonguis.com): https://www.pythonguis.com/tutorials/packaging-pyside6-applications-windows-pyinstaller-installforge/ (MEDIUM confidence — verified against PyInstaller docs)
- Real Python QThread guide: https://realpython.com/python-pyqt-qthread/ (HIGH confidence — official patterns, confirmed by Qt docs)
- Qt official threading guidance: https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html (HIGH confidence)
- Matplotlib memory leak issues (GitHub): https://github.com/matplotlib/matplotlib/issues/23701 and https://github.com/matplotlib/matplotlib/issues/20300 (MEDIUM confidence — confirmed real, workarounds well-established)
- ReportLab user guide (official): https://docs.reportlab.com/ (HIGH confidence)
- PyInstaller PySide6 Qt forum threading issue (PySide-803): https://bugreports.qt.io/browse/PYSIDE-803 (MEDIUM confidence)
- JSON schema backward compatibility patterns: https://www.creekservice.org/articles/2024/01/08/json-schema-evolution-part-1.html (MEDIUM confidence)
- Codebase CONCERNS.md audit (internal, 2026-03-14): known issues in `main_window.py`, `project_io.py`, `transient.py` (HIGH confidence — direct inspection)

---

*Pitfalls research for: Desktop engineering simulation tool — Python/PySide6 Phase 4 upgrade*
*Researched: 2026-03-14*
