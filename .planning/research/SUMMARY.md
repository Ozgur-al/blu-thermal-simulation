# Project Research Summary

**Project:** blu-thermal-simulation
**Domain:** Python desktop engineering simulation tool — Phase 4 (prototype-to-professional upgrade)
**Researched:** 2026-03-14
**Confidence:** HIGH (stack, architecture), MEDIUM (features, pitfalls)

## Executive Summary

This is a Phase 4 upgrade of an existing Python/PySide6 thermal simulation tool that already solves RC-network steady-state and transient problems with a working GUI. The goal is transforming a functioning prototype into a professional internal tool that thermal engineers reach for by default — comparable in feel (if not scope) to Ansys Icepak or COMSOL. Research across all four domains converges on the same conclusion: the biggest risk is not picking the wrong libraries, it is adding Phase 4 features on top of structural debt. The existing `MainWindow` class at 939 lines is already past the point where new features can be added safely. Refactoring must come before feature work, not after.

The recommended approach sequences work in three distinct milestones: first, backend engine work that can be tested through the CLI without touching the GUI (parametric sweep engine, power-profile model, PDF report generator); second, wiring those backends into the GUI while maintaining separation via dedicated dialog and panel classes; third, visual polish and packaging. The stack additions are minimal and deliberate — only four new dependencies are required (reportlab, qt-material, pyinstaller, pyinstaller-hooks-contrib), and two of the most critical capabilities (parametric sweep via itertools + ProcessPoolExecutor) use nothing but the stdlib. All recommended libraries are current, well-maintained, and verified against PyPI.

The critical risk profile is well-defined. GUI thread blocking during long sweeps will cause visible freezes on a non-programmer user's machine. JSON backward compatibility breaks will destroy months of saved project files. PyInstaller onefile mode will trigger antivirus on corporate Windows machines. All three risks have known, documented prevention strategies. The architecture research identifies exactly where each risk surfaces and how to neutralize it before it becomes a production problem.

---

## Key Findings

### Recommended Stack

Phase 4 adds four new capability domains to an existing Python 3.11 / NumPy / SciPy / PySide6 / Matplotlib stack. The additions are surgical — no changes to the existing solver pipeline or core dependencies are required.

**Core technologies (new additions only):**
- **reportlab 4.4.10** — PDF report generation via Platypus layout engine; industry standard, 4.7M+ downloads/month, embeds matplotlib figures via in-memory BytesIO, no external binaries required on Windows
- **qt-material 2.17** — Material Design stylesheet for PySide6; actively maintained (April 2025 release); single-line application via `apply_stylesheet(app, 'dark_teal.xml')`; replaces the unmaintained PyQtDarkTheme
- **pyinstaller 6.19.0 + pyinstaller-hooks-contrib 2026.3** — Windows one-folder bundling; no admin access required; the hooks-contrib package is mandatory for correct scipy/numpy/matplotlib bundling
- **itertools + concurrent.futures (stdlib)** — parametric sweep engine; zero additional dependencies; ProcessPoolExecutor bypasses GIL for CPU-bound scipy solver calls

Key exclusions to enforce: WeasyPrint (requires Pango/Cairo system binaries), `--onefile` PyInstaller mode (AV quarantine, slow startup), Nuitka (requires C compiler, needs admin), Dask/Ray (overkill for 10–1000 run sweeps).

See `STACK.md` for full version compatibility matrix and installation commands.

### Expected Features

Phase 4 is not a greenfield MVP — it is the upgrade that makes an existing prototype feel like a product. The feature research benchmarks against Ansys Icepak, COMSOL, and Zemax OpticStudio to establish what professional thermal engineers expect.

**Must have (table stakes — missing these makes the tool feel like a script):**
- Undo/Redo via QUndoStack — every engineering tool has this; engineers who fear editing don't use the tool
- Run/Cancel simulation with progress indicator — transient sweeps can run for minutes without feedback
- Status bar with file state and last run time — Icepak and COMSOL both show this
- All CLI capabilities exposed in GUI — CSV export, output directory, solver mode
- Structured results summary table — T_max/T_avg/T_min per layer, hotspot rank; first thing engineers look at
- PDF engineering report export — required for design review handoffs
- Parametric sweep engine with results comparison — core differentiator; most requested feature class in thermal tools
- One-click packaged launcher — non-programmer colleagues need a double-click exe

**Should have (differentiators, Phase 4 bonus):**
- Time-varying heat sources (power cycling) — real-world duty cycles; high value but high complexity
- Material library import/export (JSON) — team-shared material databases
- Hotspot annotation on temperature maps — low complexity, high visual impact
- Expanded validation with GUI comparison plots — builds engineer trust

**Defer to future phase:**
- Project templates / New From Template dialog — example files exist; GUI discovery is low urgency
- Comprehensive keyboard shortcut map — partial shortcuts first
- Temperature-dependent material properties — breaks linear solver, 10x complexity for marginal accuracy in 25-120°C range
- 3D visualization / CAD import — fundamentally incompatible with 2.5D RC model approach

**Critical dependency note:** Packaging must be the final step. Undo/Redo must be implemented before other GUI features (retrofitting QUndoCommand is painful). Parametric sweep and results comparison must ship together — sweep output is meaningless without comparison view.

See `FEATURES.md` for full prioritization matrix and competitor analysis.

### Architecture Approach

Phase 4 extends the existing layered architecture at well-defined seams without requiring solver surgery. The key architectural insight is that all four Phase 4 features are consumers of `DisplayProject` and emitters of result data — they never reach into solver internals. The solver pipeline remains completely unchanged.

New components slot in as: a `sweeps/` package (SweepSpec, SweepRunner, ProjectMutator) parallel to the existing `solvers/`; a `PowerProfile` dataclass in `models/`; a `report_gen.py` module in `io/` alongside the existing `csv_export.py`; and three new UI dialogs/panels in `ui/` that keep sweep logic out of the already-oversized `MainWindow`.

**Major components (new):**
1. **SweepRunner (QRunnable)** — executes N solver calls in background thread; emits per-step progress signals; uses `ProjectMutator.apply()` to deep-copy project for each step without mutating the live project
2. **ReportGenerator** — assembles ReportLab Platypus PDF; renders matplotlib figures to in-memory BytesIO (no temp files); consumes existing postprocess and visualization functions unchanged
3. **PowerProfile** — piecewise-linear callable; injected into TransientSolver as optional kwarg; updates only the RHS b_vector per step, never the LHS matrix (LU factorization stays valid for entire simulation)
4. **SweepDialog + SweepResultsPanel** — dedicated UI classes; MainWindow gets only a "Run Sweep" button and results tab slot; all sweep logic lives in these classes

**Recommended build order:** Backend first (PowerProfile → TransientSolver integration → SweepSpec/ProjectMutator → SweepRunner → ReportGenerator), then GUI wiring, then QDockWidget polish and packaging last.

See `ARCHITECTURE.md` for full data flow diagrams, pattern examples, and anti-pattern catalogue.

### Critical Pitfalls

Eight pitfalls identified; the top five require explicit phase-level prevention strategies:

1. **Blocking solver on main Qt thread** — sweeps running in button handlers will freeze the GUI for minutes on Windows. Prevention: QRunnable + QThreadPool + signal-only communication between worker and main thread. Must be addressed as the first task of GUI work, before adding any new feature.

2. **JSON backward compatibility breaks** — new fields in `from_dict()` using bracket access (`data["new_field"]`) instead of `.get("new_field", default)` will corrupt every existing project file. Prevention: all new fields use `.get()` with sensible defaults; add `schema_version` integer to JSON root; load all `examples/` files in CI after any model change.

3. **PyInstaller onefile mode triggers antivirus** — temp-directory extraction pattern matches malware heuristics; corporate Windows AV will quarantine the exe. Prevention: use `--onedir` exclusively, distribute as a zip, never use UPX compression.

4. **MainWindow god object collapses under Phase 4 feature weight** — at 939 lines it is already at the limit; adding sweep UI, power profile editors, and report dialogs inline will push it past 1500 lines and make it untestable. Prevention: extract `TableDataParser`, `SimulationController`, and `PlotManager` from `MainWindow` before adding any Phase 4 features.

5. **Parametric sweep accumulating full TransientResult arrays** — at default mesh, 10 sweep runs storing full 4D temperature arrays exhaust available RAM. Prevention: SweepRunner must extract summary stats immediately after each run and release the full array; sweep result stores only `{params: dict, summary: dict}` tuples.

Additional pitfalls: PDF font missing after packaging (use ReportLab built-in Type1 fonts — Helvetica/Times); power cycling LU factorization invalidation (separate matrix build from RHS build; never call `build_thermal_network()` inside the time loop); resource path breaks after packaging (create a `resources.py` helper that checks `sys._MEIPASS` before returning paths).

See `PITFALLS.md` for full recovery strategies and the "Looks Done But Isn't" verification checklist.

---

## Implications for Roadmap

Based on combined research, the work naturally partitions into five phases. The sequencing is driven by three constraints: (1) backend components must be testable via CLI before GUI wiring begins; (2) MainWindow must be refactored before new UI features are added; (3) packaging must be last because it validates everything.

### Phase 1: Foundation — MainWindow Refactor + Threading Infrastructure

**Rationale:** The MainWindow god object at 939 lines is the single largest risk to Phase 4 success. Every subsequent feature will be added to this class unless it is decomposed first. Retrofitting QUndoStack and QThread patterns into a monolith is 3-5x harder than building on clean collaborators. This phase unblocks all subsequent GUI work.

**Delivers:** A MainWindow under 400 lines; extracted SimulationController (owns QThread/QRunnable pattern), TableDataParser (owns table widget ↔ model conversion), PlotManager (owns matplotlib canvases); QUndoStack wired to all existing edit operations; existing single-run simulations running off the main thread with progress bar and cancel button.

**Addresses:** Undo/Redo (table stakes), Run/Cancel with progress (table stakes), Status bar (table stakes)

**Avoids:** MainWindow god object pitfall (Pitfall 4), Blocking solver pitfall (Pitfall 1)

**Research flag:** Standard Qt patterns — skip research phase. QUndoStack and QThread patterns are thoroughly documented and verified.

### Phase 2: Backend Engines — Sweep + Power Profile + Report Generator

**Rationale:** Building backend components that work via CLI first means they can be tested against known analytical solutions before any GUI is built. This catches physics bugs before UI concerns complicate debugging. The three backend components (SweepEngine, PowerProfile, ReportGenerator) are independent of each other and can be developed in parallel or in sequence.

**Delivers:** `sweeps/` package with SweepSpec, SweepRunner, ProjectMutator; PowerProfile callable injected into TransientSolver; ReportGenerator producing PDF from steady-state, transient, or sweep results; CLI commands for sweep execution and report generation; backward-compatible JSON for power profiles.

**Addresses:** Parametric sweep engine (P1), Time-varying heat sources (P2), PDF report export (P1)

**Avoids:** JSON backward compat pitfall (Pitfall 2) — schema_version field and `.get()` discipline required here; Sweep memory bloat (Pitfall 6) — summary-only extraction from TransientResult; Power cycling LU invalidation (Pitfall 7); PDF font pitfall (Pitfall 5) — use Type1 built-ins only

**Research flag:** Standard patterns for all three. SweepRunner uses documented QRunnable pattern. ReportLab Platypus + BytesIO pattern is verified against official docs. No research phase needed.

### Phase 3: GUI Wiring — Sweep Dialog, Results Comparison, Report Trigger

**Rationale:** With backend engines working and MainWindow decomposed, GUI wiring is lower risk. Each backend gets a dedicated UI class (SweepDialog, SweepResultsPanel) that MainWindow instantiates but does not own logic for. Results comparison view must ship in the same phase as sweep UI — sweep output is meaningless without it.

**Delivers:** SweepDialog (QDialog for sweep configuration + live progress bar showing "Run 3 of 20"); SweepResultsPanel (QAbstractTableModel-backed comparison table + overlay probe plots); Report generation button integrated into results area; all CLI capabilities accessible from GUI; structured results summary table exposed as dedicated Results Summary panel.

**Addresses:** Parametric sweep + results comparison (P1), All CLI in GUI (P1), Structured results summary (P1), PDF report from GUI (P1)

**Avoids:** Anti-pattern of adding sweep UI to MainWindow directly (use dedicated dialog classes); QTableWidget for large result sets (use QAbstractTableModel + beginInsertRows); canvas.draw() on every signal (throttle redraws to >250ms interval)

**Research flag:** Standard PySide6 patterns. QAbstractTableModel and QRunnable signal patterns are well-documented. Skip research phase.

### Phase 4: Polish — Qt Material Theme, QDockWidget Layout, Hotspot Annotation

**Rationale:** Visual refactoring of the GUI shell is purely presentational and carries no physics risk. Doing it after feature backends are wired means the refactor doesn't need to simultaneously support new components being built. This is also where low-complexity, high-impact polish items ship.

**Delivers:** qt-material dark theme applied; QDockWidget-based panel layout replacing fixed QSplitter; hotspot annotation on temperature maps (top-N labels at hotspot cells); material library import/export (JSON user library); expanded validation GUI report; consistent keyboard shortcuts (Ctrl+S, Ctrl+Z/Y, F5, Escape).

**Addresses:** Professional UI polish, hotspot annotation (P2), material library I/O (P2), expanded validation (P2)

**Avoids:** Applying two conflicting full stylesheets (pick qt-material only, no QDarkStyleSheet); regression to existing features during QDockWidget restructure (purely visual refactor, no logic changes)

**Research flag:** Standard patterns. qt-material 2.17 PySide6 compatibility is confirmed. QDockWidget is core Qt. Skip research phase.

### Phase 5: Packaging — PyInstaller One-Folder Bundle, Resources, Final Verification

**Rationale:** Packaging must be last because it validates that every feature works correctly from a frozen build with no Python installed. It also carries the highest external risk (AV, corporate machines, path resolution) and requires the GUI to be feature-complete before packaging an incomplete tool is worthwhile.

**Delivers:** PyInstaller onedir build with no console window; resources.py `get_resource_path()` helper using sys._MEIPASS; all example JSON files in spec datas; scipy hidden imports in spec; SetCurrentProcessExplicitAppUserModelID for proper taskbar grouping; user data written to %APPDATA%/ThermalSim/; verified on clean Windows machine with Defender enabled; verified from path with spaces and from network share; `launch.bat` fallback for in-repo use.

**Addresses:** One-click packaged launcher (P1 — required for non-programmer adoption)

**Avoids:** Onefile mode AV quarantine (use --onedir), resource path breaks (resources.py helper), PDF font missing (Type1 built-ins confirmed safe), UPX compression (triggers additional AV false positives)

**Research flag:** May benefit from a targeted research pass on scipy 1.12+ hidden import list for pyinstaller-hooks-contrib 2026.3 — the exact set of required hidden imports can change between scipy minor versions. Verify against packaging docs before building.

### Phase Ordering Rationale

- Phase 1 before all GUI phases: structural debt must be cleared first or every subsequent feature lands in the wrong place
- Phase 2 before Phase 3: backend-first enables CLI testing independent of GUI; catches physics bugs in isolation
- Phase 3 after Phase 2 and Phase 1: requires both clean GUI structure (Phase 1) and working backends (Phase 2)
- Phase 4 after Phase 3: visual refactoring after feature wiring avoids simultaneous backend + presentation churn
- Phase 5 always last: packaging is a validation gate, not a feature; packaging an incomplete tool ships a permanent incomplete impression

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All library versions confirmed via PyPI JSON API; compatibility matrix verified; alternatives documented with specific rejection rationale |
| Features | MEDIUM | Benchmarked against Icepak, COMSOL, Zemax — strong professional consensus; specific implementation complexity estimates are research-based inference, not measured |
| Architecture | HIGH | Based on direct codebase inspection (Phase 3 source) + official Qt docs; all patterns verified against PySide6 6.x documentation; data flows are concrete, not speculative |
| Pitfalls | MEDIUM-HIGH | Most pitfalls confirmed by official docs and community post-mortems; memory exhaustion numbers (Pitfall 6) are estimates based on array size calculations, not profiled measurements |

**Overall confidence:** HIGH for technology and architecture decisions. MEDIUM for feature complexity estimates and performance thresholds (these will require validation during implementation).

### Gaps to Address

- **Sweep memory thresholds:** Pitfalls research estimates ~350 MB for a 10-run transient sweep at default mesh. This should be profiled with tracemalloc early in Phase 2 to validate the summary-only extraction requirement before it becomes an emergency.

- **Report generation performance:** The research notes PDF generation "may" block the main thread for 2-5 seconds on large reports. Whether this requires a QRunnable or runs acceptably on the main thread needs measurement on a real machine during Phase 3.

- **PyInstaller hidden imports for scipy 1.12+:** The spec file hidden import list (`scipy.sparse.csgraph._validation`, `scipy.linalg.blas`, `scipy.linalg.lapack`) was verified against pyinstaller-hooks-contrib 2026.3 documentation, but scipy's internal structure changes between minor versions. Validate the complete import list against an actual build during Phase 5.

- **Corporate AV testing:** The `--onedir` recommendation is well-supported, but actual behavior on managed Windows endpoints with CrowdStrike or Cylance (not just Defender) was not verified. This needs a real test on a target machine during Phase 5.

- **Qt Material + PySide6 6.10.2 layout regressions:** qt-material applies CSS-level style overrides and can alter widget geometry. The exact visual impact on existing complex layouts (splitters, tabs, matplotlib canvas) needs an integration test during Phase 4.

---

## Sources

### Primary (HIGH confidence)
- PyPI JSON API (reportlab, pyinstaller, PySide6, qt-material, pyinstaller-hooks-contrib) — version confirmation
- PyInstaller official docs (pyinstaller.org) — onedir/onefile operating mode, data files, hidden imports
- ReportLab official docs (docs.reportlab.com) — Platypus document model, font handling
- Qt for Python official docs (doc.qt.io/qtforpython-6) — QThread, QRunnable, QDockWidget, QUndoStack
- Python 3.11 stdlib docs (docs.python.org) — concurrent.futures, itertools
- Existing codebase direct inspection — MainWindow line count, Phase 3 architecture, CONCERNS.md audit

### Secondary (MEDIUM confidence)
- pythonguis.com QThreadPool multithreading tutorial (2025) — QRunnable + WorkerSignals pattern
- pythonguis.com PySide6 PyInstaller packaging tutorial (2025) — packaging gotchas, console=False
- pythonguis.com PDF report generator example (Dec 2025) — ReportLab + matplotlib BytesIO pattern
- Ansys Icepak 2025 R2 release notes — competitor feature baseline
- COMSOL 6.3 parametric sweep docs — sweep feature benchmark
- Electronics Cooling thermal methodology (2024) — engineering tool UX expectations
- Real Python QThread guide — threading patterns
- JSON schema evolution patterns (creekservice.org) — backward compat strategies

### Tertiary (LOW confidence)
- WebSearch: PyInstaller AV quarantine behavior on corporate endpoints with non-Defender tools — needs real-world validation
- WebSearch: qt-material layout regression behavior on complex PySide6 UIs — needs integration test

---

*Research completed: 2026-03-14*
*Ready for roadmap: yes*
