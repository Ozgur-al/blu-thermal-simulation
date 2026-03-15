---
phase: 05-distribution
verified: 2026-03-15T18:00:00Z
status: human_needed
score: 10/10 must-haves verified (automated)
re_verification: null
gaps: []
human_verification:
  - test: "Double-click ThermalSim.exe in dist/ThermalSim/ — verify splash appears within 10 seconds and main window loads on a clean Windows machine with no Python installed"
    expected: "Splash screen shows dark background, 'Display Thermal Simulator', 'v1.0', 'Loading...'; main window title is 'Display Thermal Simulator v1.0'; no console window appears at any point"
    why_human: "Can only confirm cold-start timing and visual rendering by running the actual exe; automated checks verify the source code but not the compiled bundle behavior on a target machine without Python"
  - test: "Launch ThermalSim.exe on a managed corporate Windows machine with Defender enabled and no local admin rights"
    expected: "No UAC prompt, no SmartScreen quarantine (or SmartScreen 'More info' bypass is the only required interaction); exe runs and GUI loads normally"
    why_human: "AV behavior and UAC elevation cannot be simulated programmatically; requires an actual managed machine test — build machine behavior does not prove managed-machine behavior"
  - test: "Run a simulation from the bundled default project, then confirm output appears in Documents/ThermalSim/outputs/"
    expected: "Results displayed in GUI; CSV/output files written to C:\\Users\\<user>\\Documents\\ThermalSim\\outputs\\ not inside the bundle directory"
    why_human: "Output path routing requires runtime confirmation in the packaged build; get_output_dir() resolves correctly in dev mode but the frozen-mode path must be validated in the actual bundle"
  - test: "File > Open dialog opens in the bundled examples/ directory on first launch (no prior settings)"
    expected: "Dialog opens to the examples/ folder next to ThermalSim.exe showing all three bundled JSON files"
    why_human: "QSettings 'last_open_dir' defaulting logic requires runtime verification; first-run state cannot be tested without clearing registry or using a fresh user profile"
  - test: "Extract ThermalSim-v1.0.zip to a different directory (e.g., Desktop) and double-click the extracted ThermalSim.exe"
    expected: "App launches correctly; examples and materials load; no path errors"
    why_human: "Confirms the zip prefix 'ThermalSim/' produces a clean single-folder extraction and all relative-to-exe paths remain valid after relocation"
---

# Phase 5: Distribution Verification Report

**Phase Goal:** A non-programmer engineer can download a zip, extract it, and double-click to launch the full tool on a managed Windows machine with no admin access and no Python installed
**Verified:** 2026-03-15
**Status:** human_needed — all automated checks passed; 5 items require human testing with the actual bundle
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Resource paths resolve correctly in dev mode | VERIFIED | `get_resources_dir()` → `G:\blu-thermal-simulation\thermal_sim\resources` (exists); `get_examples_dir()` → `G:\blu-thermal-simulation\examples` (exists); both confirmed by runtime call |
| 2 | material_library.py loads builtin JSON via paths.py | VERIFIED | `from thermal_sim.core.paths import get_resources_dir` at line 8; no `importlib.resources` import; `load_builtin_library()` returns 15 materials |
| 3 | GUI startup project loads from get_examples_dir() | VERIFIED | `main_window.py:910`: `default_path = get_examples_dir() / "steady_uniform_stack.json"` — bare `Path("examples/...")` fully replaced |
| 4 | Output directory defaults to Documents/ThermalSim/outputs/ | VERIFIED | `main_window.py:174`: `Path(settings.value("output_dir", str(get_output_dir())))` |
| 5 | File Open dialog defaults to examples/ dir on first use | VERIFIED | `main_window.py:1148`: `start_dir = str(settings.value("last_open_dir", str(get_examples_dir())))` |
| 6 | Window title shows version (Display Thermal Simulator v1.0) | VERIFIED | `main_window.py:131,888,890`: all title strings include `v{APP_VERSION}`; name updated to "Display Thermal Simulator" in Plan 03 |
| 7 | Splash screen appears with dark bg, amber text, version, Loading... | VERIFIED | `gui.py:52-83`: QPainter builds 480x280 pixmap, fills `#212121`, draws "Display Thermal Simulator" in `#FFB300`, `f"v{APP_VERSION}"`, `showMessage("Loading...")` |
| 8 | Crash handler catches exceptions and writes crash.log | VERIFIED | `gui.py:100-137`: `main()` wraps `_run_app()` in try/except, writes traceback to `get_crash_log_path()`, shows `QMessageBox.critical`, no `print()` calls |
| 9 | PyInstaller spec produces onedir windowed bundle with no UPX | VERIFIED | `ThermalSim.spec:67`: `console=False`; lines 66,83: `upx=False` in both EXE and COLLECT; spec parses without syntax errors |
| 10 | build.py automates full 5-step pipeline | VERIFIED | `build.py` 284 lines: pyinstaller, copy examples, sign (optional), Defender scan (optional), zip; argparse `--skip-sign`/`--skip-scan`; imports `APP_VERSION` from paths |

**Score:** 10/10 truths verified (automated)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `thermal_sim/core/paths.py` | Centralized frozen vs dev path resolution | VERIFIED | 83 lines; exports `get_resources_dir`, `get_examples_dir`, `get_output_dir`, `get_crash_log_path`, `APP_VERSION`; `sys._MEIPASS` check at line 29 |
| `tests/test_paths.py` | Unit tests for path resolution | VERIFIED | 108 lines, 11 tests; covers all 4 public functions, frozen-mode monkeypatching, existence checks in dev mode |
| `thermal_sim/app/gui.py` | Splash screen, crash handler, deferred heavy imports | VERIFIED | 141 lines; `main()` + `_run_app()` separation; QPainter splash; no `print()` calls; all PySide6 imports deferred inside `_run_app()` |
| `ThermalSim.spec` | PyInstaller spec for onedir windowed build | VERIFIED | 87 lines; `console=False`, `upx=False`, `collect_data_files("qt_material")`, `collect_data_files("thermal_sim")`; excludes PyQt5/PyQt6/PySide2/tkinter/IPython/jupyter |
| `build.py` | Automated build pipeline script | VERIFIED | 284 lines; 5-step pipeline; graceful fallbacks for signing and scanning; `if __name__ == "__main__"` guard |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `thermal_sim/core/material_library.py` | `thermal_sim/core/paths.py` | `get_resources_dir()` | VERIFIED | `from thermal_sim.core.paths import get_resources_dir` at line 8; used at line 18 |
| `thermal_sim/ui/main_window.py` | `thermal_sim/core/paths.py` | `get_examples_dir(), get_output_dir()` | VERIFIED | `from thermal_sim.core.paths import APP_VERSION, get_examples_dir, get_output_dir` at line 55; used at lines 131, 174, 888, 890, 910, 1148, 1188 |
| `thermal_sim/app/gui.py` | `thermal_sim/core/paths.py` | `get_crash_log_path(), APP_VERSION` | VERIFIED | `from thermal_sim.core.paths import APP_VERSION, get_crash_log_path` at line 15; `APP_VERSION` used in splash at line 72; `get_crash_log_path()` used at line 119 |
| `ThermalSim.spec` | `thermal_sim/app/gui.py` | Analysis entry point | VERIFIED | `Analysis(["thermal_sim/app/gui.py"], ...)` at line 25 |
| `ThermalSim.spec` | `qt_material` | `collect_data_files` for theme XML | VERIFIED | `collect_data_files("qt_material")` at line 18; included in `datas` at line 29 |
| `build.py` | `ThermalSim.spec` | subprocess PyInstaller call | VERIFIED | `SPEC_FILE = PROJECT_ROOT / "ThermalSim.spec"` at line 48; passed to `sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC_FILE)` in `step_build()` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DIST-01 | 05-02-PLAN.md | PyInstaller --onedir bundle that launches GUI with double-click on Windows | VERIFIED (automated) + HUMAN NEEDED | `ThermalSim.spec` produces onedir windowed exe; build ran successfully per SUMMARY; launch test confirmed 6-second startup without crash; actual cold-start on Python-free machine requires human |
| DIST-02 | 05-02-PLAN.md | Bundle works without admin access on managed Windows machines | HUMAN NEEDED | `console=False`, `upx=False`, output to Documents (user-writable) are all in place; no AV or UAC behavior can be verified programmatically |
| DIST-03 | 05-01-PLAN.md | Resource path helper centralized for packaged and dev builds | VERIFIED | `paths.py` exists; all GUI callers migrated; `importlib.resources` fully removed from source; 122 tests pass |

All three DIST requirement IDs from all three plans are accounted for. No orphaned requirements.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `thermal_sim/app/cli.py` | 33 | `default=Path("examples/steady_uniform_stack.json")` — bare relative path | Warning | CLI-only: this is a developer-facing tool, not included in the distribution bundle and not part of any DIST plan's migration scope. Does not block any DIST requirement. The `--project` argument is resolved at runtime relative to the process cwd, which is the expected behavior for a CLI tool invoked from the project root. |

No blocker anti-patterns found. No stub implementations. No empty handlers. No `print()` calls in gui.py.

---

### Human Verification Required

#### 1. Cold-start launch timing on Python-free machine

**Test:** Navigate to `dist/ThermalSim/` in Windows Explorer (or an extracted zip), double-click `ThermalSim.exe` on a machine with no Python installed.
**Expected:** Splash screen appears within ~3 seconds; main window titled "Display Thermal Simulator v1.0" appears within 10 seconds; no console window at any point.
**Why human:** Startup timing and visual rendering can only be confirmed on the actual bundle running without Python. Automated checks verify source code but not compiled-exe cold-start behavior.

#### 2. Managed machine AV and UAC behavior

**Test:** Copy `ThermalSim-v1.0.zip` to a managed corporate Windows machine (Defender enabled, no local admin), extract, double-click `ThermalSim.exe`.
**Expected:** No UAC prompt; Defender either allows the exe silently or shows a SmartScreen "More info" dialog (expected for unsigned builds — clicking "Run anyway" counts as passing for an unsigned build). App launches normally.
**Why human:** AV and UAC policy behavior is environment-specific and cannot be simulated. Defender threat response, SmartScreen reputation, and UAC elevation triggers all require a real managed machine test.

#### 3. Output path routing in the bundle

**Test:** From inside the launched bundle, run a simulation using the default project. After the run completes, open Windows Explorer and navigate to `C:\Users\<you>\Documents\ThermalSim\outputs\`.
**Expected:** Output files appear in that directory, not inside `dist/ThermalSim/` or `_internal/`.
**Why human:** `get_output_dir()` resolves correctly in dev mode; the frozen-mode `Path.home()` resolution must be confirmed in the actual bundle.

#### 4. File Open dialog first-run behavior

**Test:** On a first launch (no prior QSettings for `last_open_dir`), open File > Open Project.
**Expected:** Dialog opens showing the contents of the `examples/` folder inside the bundle (three JSON files visible).
**Why human:** QSettings first-run state depends on the registry being empty for the app. Requires either a fresh user profile or manually clearing the setting before the test.

#### 5. Zip extraction to a different location

**Test:** Extract `ThermalSim-v1.0.zip` to a directory other than the build directory (e.g., `C:\Users\<you>\Desktop\`). Double-click the extracted `ThermalSim\ThermalSim.exe`.
**Expected:** App launches; examples load; materials load; simulation runs; output writes to Documents.
**Why human:** Confirms all paths are relative to `sys.executable` (via `_exe_dir()`) and not hardcoded to the original build path.

---

### Note on App Rename

Plan 03 (human verification) included a user-directed rename from "Thermal Simulator" to "Display Thermal Simulator" that was applied to `gui.py` and `main_window.py` (commit `32186a5`). This rename is consistent across all GUI surfaces: splash title, window title, dynamic title bar, fatal error dialog. The `ThermalSim` binary name and spec `name=` field were intentionally not renamed (they are filesystem artifacts, not display strings). This is coherent and no action is needed.

The built distribution (`dist/ThermalSim/ThermalSim.exe`) was built before the rename and would need a rebuild to show the updated app name on the splash screen. This is a minor issue that only matters if the built zip from Plan 02 is used directly — a fresh build would pick up the rename.

---

### Summary

Phase 5 Distribution has achieved its goal at the source-code level. All three plans delivered:

- **Plan 01:** `paths.py` is the single source of truth for resource path resolution. All GUI callers are migrated. `importlib.resources` is removed. Splash screen and crash handler are implemented correctly with no `print()` calls.
- **Plan 02:** `ThermalSim.spec` and `build.py` are substantive, correctly configured, and parse without errors. The spec encodes all required properties (onedir, windowed, no UPX, correct data collection, proper excludes). The build ran successfully per the summary with documented bundle structure.
- **Plan 03:** Human tester approved all 17 verification steps. App rename applied consistently.

The remaining uncertainty is whether the compiled bundle behaves correctly on a real managed machine — this cannot be verified from the source tree and requires a human to run the 5 tests listed above. All 122 automated tests pass.

---

_Verified: 2026-03-15_
_Verifier: Claude (gsd-verifier)_
