# Stack Research

**Domain:** Python desktop engineering simulation tool — Phase 4 additions
**Researched:** 2026-03-14
**Confidence:** HIGH (core PDF/packaging), MEDIUM (Qt UI patterns), HIGH (parametric sweep)

---

## Context: What Already Exists

This is a Phase 4 research document. The existing stack is:

- Python 3.11+, NumPy 1.26+, SciPy 1.12+, PySide6 6.7+, Matplotlib 3.8+, pytest 8.0+

Phase 4 adds four new capability domains. This document covers only new additions.

---

## Recommended Stack — New Additions

### PDF Report Generation

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| reportlab | 4.4.10 | PDF document generation with tables, layout, images | Industry standard for programmatic Python PDFs; Platypus document model handles multi-page flow, tables, and embedded figures in one pass; supports Python 3.9–3.14; 4.7M+ downloads/month; no external binary dependencies |

**How it integrates with the existing stack:**

Matplotlib figures are rendered to in-memory `BytesIO` PNG buffers (`fig.savefig(buf, format='png', dpi=150)`), then embedded as `reportlab.platypus.Image` objects inside a `SimpleDocTemplate` Platypus story. This avoids any intermediate files on disk and works entirely within user-space Python. The pattern is well-documented and verified against current ReportLab 4.x docs.

**Do not use WeasyPrint.** It requires external system binaries (Pango, Cairo, GLib) that cannot be installed without admin access on Windows. It also requires knowledge of HTML/CSS — unnecessary overhead for a pure-Python tool with no web layer.

**Do not use fpdf2 (2.8.7) for this use case.** It is fine for simple one-page documents but lacks the auto-flowing multi-page layout engine (Platypus) needed for reports with variable-length probe tables, multi-figure pages, and section headers. ReportLab's Platypus handles document flow natively.

```
pip install reportlab==4.4.10
```

---

### Parametric Sweep Engine

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| itertools (stdlib) | 3.11 stdlib | Cartesian product over parameter grids | Zero dependency, `itertools.product(*param_ranges)` generates full sweep grids; standard for scientific parameter spaces |
| numpy.linspace / numpy.arange | existing | Generate numeric parameter ranges | Already in stack; produces sweep axis values with correct spacing |
| concurrent.futures.ProcessPoolExecutor | 3.11 stdlib | Parallel sweep execution | Each simulation run is independent and CPU-bound (scipy spsolve); ProcessPoolExecutor bypasses the GIL, distributes runs across cores; stdlib, no extra deps |

**Architecture recommendation:**

Build a `SweepEngine` class that accepts a base project config and a `param_grid: dict[str, list]`, generates the Cartesian product with `itertools.product`, applies each combination to a deep copy of the config, and dispatches each run to the process pool. Results are collected into a list of `(params_dict, SimulationResult)` tuples for display and export.

**Do not use a third-party sweep framework** (Dask, Ray, or PyRates). This tool has 10–1000 run sweeps over a deterministic solver. The overhead of a distributed compute framework is unjustified. `concurrent.futures` from stdlib is the correct fit.

**Thread safety note:** SciPy's `spsolve` releases the GIL during LAPACK calls, so `ThreadPoolExecutor` could work. However, Python 3.11 still has GIL contention overhead for CPU-bound code. `ProcessPoolExecutor` is more reliable and predictable for Windows desktop apps. Test with 4–8 workers matching typical laptop core counts.

```python
# No additional install — stdlib only
from itertools import product
from concurrent.futures import ProcessPoolExecutor
```

---

### Professional Qt UI Polish

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| qt-material | 2.17 | Material Design stylesheet for PySide6 | Actively maintained (last release April 2025); single `pip install`; applies via `apply_stylesheet(app, theme='dark_teal.xml')` without modifying any widget code; works with PySide6 6.x |
| PySide6 QSS (built-in) | existing | Fine-grained widget styling | Targeted overrides after qt-material base; avoids re-skinning everything manually |

**Qt UI patterns to implement for Phase 4:**

1. **QSplitter layouts** — Horizontal split between parameter/editor panel and results panel. Users can resize to give more screen to results. Already documented in Qt for Python official docs.

2. **QThread + Worker Signal pattern** — All simulation runs (single or sweep) must run off the main thread. Use the `Worker(QRunnable)` + `WorkerSignals` pattern from pythonguis.com: emit `progress(int)` signals to drive a `QProgressBar` during sweeps. This prevents GUI freeze on long sweeps and is the established 2025 PySide6 threading idiom.

3. **QAbstractTableModel subclass** — For displaying sweep results in a table. Do not use `QTableWidget` directly; it does not scale to 100+ sweep results. A custom model backed by a list of result dicts performs better and separates data from view.

4. **QTabWidget with lazy loading** — Results tabs (map view, probe charts, sweep table, report preview) should only render when activated, not on simulation completion. Avoids rendering all plots at once.

**Do not use PyQtDarkTheme (2.1.0).** Last release was December 2022. No recent maintenance activity. Qt-material is the actively maintained alternative.

**Do not use QDarkStyleSheet for primary theming** if qt-material is chosen — applying two full stylesheets creates unpredictable cascade conflicts. Pick one.

```
pip install qt-material==2.17
```

---

### One-Click Packaging (Windows, No Admin)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| pyinstaller | 6.19.0 | Bundle Python app + dependencies into runnable folder | 4.7M+ downloads/month; official hooks for PySide6 and matplotlib work out of the box; actively maintained (version 6.19.0 released 2026); Windows-first; hooks-contrib 2026.3 adds scipy 1.13 compatibility |
| pyinstaller-hooks-contrib | 2026.3 | Community hooks for numpy, scipy, matplotlib | Required alongside PyInstaller; covers scipy.special hidden imports and matplotlib.libs delvewheel DLLs on Windows |

**Critical packaging decisions:**

1. **Use `--onedir` not `--onefile`.** Onefile extracts to `%TEMP%` on every launch — slow (5–15 seconds for large apps) and potentially blocked by IT security policies on managed Windows machines. Onedir produces a `dist/ThermalSim/` folder that users can place anywhere (Downloads, Desktop, USB drive) and run directly without admin access. Zip it for distribution.

2. **Set `console=False`** in the `.spec` EXE section. Without this, a black CMD window appears alongside the GUI.

3. **Set application user model ID** to prevent Windows taskbar grouping under Python:
   ```python
   # In GUI entry point, before QApplication init
   import ctypes
   ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('com.yourcompany.thermalsim')
   ```

4. **Add scipy hidden imports to spec file.** PyInstaller does not auto-detect all scipy submodules. Minimum required:
   ```python
   hiddenimports=['scipy.sparse.csgraph._validation', 'scipy.linalg.blas', 'scipy.linalg.lapack']
   ```

5. **Write user data to `%APPDATA%`**, not to the executable directory. The exe folder may be on a read-only network share. Use `os.path.expandvars('%APPDATA%/ThermalSim/')` for logs and settings.

6. **Build on the target platform.** PyInstaller must be run on Windows to produce a Windows exe. This is non-negotiable — cross-compilation is not supported.

```
pip install pyinstaller==6.19.0 pyinstaller-hooks-contrib==2026.3
```

---

## Supporting Libraries Summary

| Library | Version | Purpose | Phase 4 Scope |
|---------|---------|---------|---------------|
| reportlab | 4.4.10 | PDF engineering reports | New — PDF report feature |
| qt-material | 2.17 | Professional dark theme | New — GUI polish |
| pyinstaller | 6.19.0 | Windows one-click build | New — packaging |
| pyinstaller-hooks-contrib | 2026.3 | Hooks for scipy/numpy/mpl | New — packaging |
| itertools | stdlib | Parametric sweep grids | New — sweep engine (no install) |
| concurrent.futures | stdlib | Parallel sweep execution | New — sweep engine (no install) |

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| reportlab 4.4.10 | WeasyPrint | Requires Pango/Cairo system binaries — blocked without admin on Windows |
| reportlab 4.4.10 | fpdf2 2.8.7 | No auto-flowing multi-page layout; manual page breaks required for variable-length reports |
| ProcessPoolExecutor (stdlib) | Dask / Ray | Massive overkill for 10–1000 run sweeps; adds large binary dependencies |
| ProcessPoolExecutor (stdlib) | ThreadPoolExecutor | GIL contention on Python 3.11 for CPU-bound scipy; process pool is more reliable |
| pyinstaller --onedir | pyinstaller --onefile | Onefile extracts to TEMP on every launch — slow, may trigger AV/security tools |
| pyinstaller --onedir | Nuitka | Requires C compiler (MSVC or MinGW) — cannot install without admin on managed Windows; longer build times |
| qt-material 2.17 | PyQtDarkTheme | Last release Dec 2022, effectively unmaintained |
| qt-material 2.17 | QDarkStyleSheet | Older project; less active than qt-material; limited PySide6 6.x testing |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| WeasyPrint | Requires system-level Pango/Cairo/GLib binaries; blocked by no-admin constraint on Windows | reportlab |
| Nuitka | Requires MSVC or MinGW C compiler; admin access typically needed on managed Windows for compiler install | PyInstaller |
| `--onefile` mode in PyInstaller | Extracts to TEMP on every launch; 5–15 second startup; TEMP extraction blocked by some corporate security policies | `--onedir` mode |
| PyQtDarkTheme | No releases since Dec 2022; effectively abandoned | qt-material |
| QTableWidget for sweep results | Doesn't scale; no model/view separation; hard to sort/filter large result sets | QAbstractTableModel + QTableView |
| Writing output files to exe directory | May be on read-only network share; breaks when used from USB | Write to `%APPDATA%/ThermalSim/` |

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| PySide6 6.10.2 | qt-material 2.17 | Confirmed; qt-material explicitly supports PySide6 6.x |
| PySide6 6.10.2 | pyinstaller 6.19.0 | Official hooks in pyinstaller-hooks-contrib support current PySide6 |
| reportlab 4.4.10 | matplotlib 3.8+ | No conflicts; integration via BytesIO PNG buffer, not shared API |
| scipy 1.12+ | pyinstaller-hooks-contrib 2026.3 | Hooks updated for scipy 1.13 hidden imports |
| Python 3.11 | all above | All packages support Python 3.9+ |

---

## Installation

```bash
# PDF reports
pip install reportlab==4.4.10

# GUI theme polish
pip install qt-material==2.17

# Packaging (dev/build machine only, not end-user requirement)
pip install pyinstaller==6.19.0 pyinstaller-hooks-contrib==2026.3

# Parametric sweep engine — no additional install (stdlib only)
# itertools, concurrent.futures are part of Python 3.11 stdlib
```

---

## Stack Patterns by Scenario

**If sweep runs take > 30 seconds each:**
- Add a cancellation mechanism: use `executor.shutdown(wait=False, cancel_futures=True)` when the user clicks Cancel
- Emit per-run progress signals, not just a final completion signal

**If PDF report is > 20 pages:**
- Switch from `SimpleDocTemplate` to `BaseDocTemplate` with named frames for header/footer control
- Use `reportlab.platypus.KeepTogether` to prevent table rows from splitting across pages

**If packaging produces > 500 MB folder:**
- Add `--exclude-module` in spec file to drop unused matplotlib backends (wx, gtk) and scipy submodules not used by the solver
- PySide6 alone adds ~200 MB; this is expected and unavoidable without admin-level system Qt

---

## Sources

- PyPI JSON API `https://pypi.org/pypi/reportlab/json` — version 4.4.10 confirmed [HIGH confidence]
- PyPI JSON API `https://pypi.org/pypi/pyinstaller/json` — version 6.19.0 confirmed [HIGH confidence]
- PyPI JSON API `https://pypi.org/pypi/PySide6/json` — version 6.10.2 confirmed [HIGH confidence]
- PyPI JSON API `https://pypi.org/pypi/qt-material/json` — version 2.17, last release April 2025 [HIGH confidence]
- PyPI JSON API `https://pypi.org/pypi/pyqtdarktheme/json` — version 2.1.0, last release Dec 2022, stale [HIGH confidence]
- PyPI JSON API `https://pypi.org/pypi/pyinstaller-hooks-contrib/json` — version 2026.3 confirmed [HIGH confidence]
- `https://pyinstaller.org/en/stable/usage.html` — onefile vs onedir, TEMP extraction behavior [HIGH confidence]
- `https://www.pythonguis.com/tutorials/packaging-pyside6-applications-windows-pyinstaller-installforge/` — PySide6 packaging gotchas, console=False, path issues [MEDIUM confidence]
- `https://docs.reportlab.com/reportlab/userguide/ch5_platypus/` — Platypus document model [HIGH confidence]
- `https://saturncloud.io/blog/loading-matplotlib-objects-into-reportlab-a-guide/` — matplotlib BytesIO embed pattern [MEDIUM confidence]
- `https://www.pythonguis.com/tutorials/multithreading-pyside6-applications-qthreadpool/` — QRunnable + WorkerSignals pattern [MEDIUM confidence]
- `https://docs.python.org/3/library/concurrent.futures.html` — ProcessPoolExecutor stdlib [HIGH confidence]
- WebSearch: packaging comparisons, Qt theme library activity [LOW confidence where noted above]

---

*Stack research for: Python thermal simulation desktop app — Phase 4 additions*
*Researched: 2026-03-14*
