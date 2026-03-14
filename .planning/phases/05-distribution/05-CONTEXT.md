# Phase 5: Distribution - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Package the thermal simulation tool as a standalone Windows bundle (PyInstaller --onedir) that a non-programmer engineer can download as a zip, extract, and double-click to launch the full GUI — no Python installed, no admin access, no terminal required. Resource paths must resolve correctly in both frozen (bundled) and dev (source) modes.

</domain>

<decisions>
## Implementation Decisions

### Bundle contents & structure
- Flat launcher layout: `ThermalSim/ThermalSim.exe` + `examples/` + `_internal/` (PyInstaller runtime)
- All 3 example JSON files ship inside the bundle in the `examples/` subfolder
- Default output directory: `Documents/ThermalSim/outputs/` (separates user data from app, survives re-extraction)
- Version indicator: window title bar only (e.g., "Thermal Simulator v1.0") — no VERSION.txt file

### Launch experience
- No console window — pure windowed application (PyInstaller `--noconsole` / `--windowed`)
- Simple branded splash screen during startup: dark background, placeholder thermal/heat gradient icon, app name, version, "Loading..." indicator — dismissed when main window is ready
- Startup error handling: Qt message box with error summary + full traceback written to `crash.log` next to the exe

### Resource path strategy
- Single centralized module: `thermal_sim/core/paths.py` that detects frozen vs dev mode and exposes functions like `get_examples_dir()`, `get_resources_dir()`, `get_output_dir()`
- Migrate `material_library.py` from `importlib.resources` to the new centralized paths module for consistency
- Bundle is GUI-only — CLI remains a dev-only tool (`python -m thermal_sim.app.cli`), no CLI path resolution needed in frozen mode
- File Open dialog defaults to the bundled `examples/` directory on first use, then remembers last-used directory

### AV & security constraints
- Self-signed code signing certificate for the build workflow (does not eliminate SmartScreen warning but practices the signing pipeline)
- Automated Defender scan step in build script — scans output folder before zipping to catch false positives early
- Automated build script: `build.py` (Python) — runs PyInstaller, copies examples, signs exe, runs Defender scan, creates distributable zip

### Claude's Discretion
- PyInstaller .spec file configuration details (hidden imports, excludes, data file declarations)
- Splash screen image creation approach (matplotlib-generated PNG, or static asset)
- Exact crash.log format and rotation policy
- Self-signed certificate creation tooling (signtool, certutil, etc.)
- Whether to use UPX compression in the bundle

</decisions>

<specifics>
## Specific Ideas

- Splash should match the existing dark Material theme (qt-material dark amber) already applied to the GUI
- The flat layout should feel clean — users see the exe and examples folder at top level, with runtime internals tucked into `_internal/`
- Outputs going to Documents/ThermalSim/ keeps the extracted bundle folder clean and portable

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `thermal_sim/resources/materials_builtin.json`: Already a bundled resource with `__init__.py` — pattern can extend to other resources
- `thermal_sim/core/material_library.py`: Uses `importlib.resources` for resource loading — will be migrated to centralized paths.py
- `thermal_sim/app/gui.py`: Existing GUI entry point with qt-material theme setup and QApplication initialization

### Established Patterns
- `importlib.resources.files("thermal_sim.resources")`: Current resource access pattern (will be replaced by centralized paths.py)
- `Path()` used throughout for file operations — all modules already use `pathlib.Path`
- `QSettings` used in `main_window.py` for persisting user preferences (output directory, window geometry)

### Integration Points
- `thermal_sim/app/gui.py`: Entry point for PyInstaller — needs `--windowed` flag and splash screen integration
- `thermal_sim/ui/main_window.py:168`: Output directory default (`Path.cwd() / "outputs"`) needs to use `paths.get_output_dir()` instead
- `thermal_sim/ui/main_window.py:760`: Default project path (`Path("examples/steady_uniform_stack.json")`) needs centralized resolution
- `thermal_sim/core/material_library.py:18`: `importlib.resources` call to migrate to paths.py
- Window title in `main_window.py`: Needs version string injection

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-distribution*
*Context gathered: 2026-03-14*
