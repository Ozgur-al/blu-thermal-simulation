# Phase 5: Distribution - Research

**Researched:** 2026-03-15
**Domain:** PyInstaller Windows packaging, resource path resolution, Qt splash screen, code signing
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Bundle contents & structure**
- Flat launcher layout: `ThermalSim/ThermalSim.exe` + `examples/` + `_internal/` (PyInstaller runtime)
- All 3 example JSON files ship inside the bundle in the `examples/` subfolder
- Default output directory: `Documents/ThermalSim/outputs/` (separates user data from app, survives re-extraction)
- Version indicator: window title bar only (e.g., "Thermal Simulator v1.0") — no VERSION.txt file

**Launch experience**
- No console window — pure windowed application (PyInstaller `--noconsole` / `--windowed`)
- Simple branded splash screen during startup: dark background, placeholder thermal/heat gradient icon, app name, version, "Loading..." indicator — dismissed when main window is ready
- Startup error handling: Qt message box with error summary + full traceback written to `crash.log` next to the exe

**Resource path strategy**
- Single centralized module: `thermal_sim/core/paths.py` that detects frozen vs dev mode and exposes functions like `get_examples_dir()`, `get_resources_dir()`, `get_output_dir()`
- Migrate `material_library.py` from `importlib.resources` to the new centralized paths module for consistency
- Bundle is GUI-only — CLI remains a dev-only tool (`python -m thermal_sim.app.cli`), no CLI path resolution needed in frozen mode
- File Open dialog defaults to the bundled `examples/` directory on first use, then remembers last-used directory

**AV & security constraints**
- Self-signed code signing certificate for the build workflow (does not eliminate SmartScreen warning but practices the signing pipeline)
- Automated Defender scan step in build script — scans output folder before zipping to catch false positives early
- Automated build script: `build.py` (Python) — runs PyInstaller, copies examples, signs exe, runs Defender scan, creates distributable zip

### Claude's Discretion
- PyInstaller .spec file configuration details (hidden imports, excludes, data file declarations)
- Splash screen image creation approach (matplotlib-generated PNG, or static asset)
- Exact crash.log format and rotation policy
- Self-signed certificate creation tooling (signtool, certutil, etc.)
- Whether to use UPX compression in the bundle

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DIST-01 | PyInstaller --onedir bundle that launches GUI with double-click on Windows | PyInstaller 6.19.0 onedir spec file pattern; EXE+COLLECT structure; windowed mode flag |
| DIST-02 | Bundle works without admin access on managed Windows machines | onedir avoids temp-dir extraction; --noupx eliminates UPX-related AV flags; output to Documents dir needs no elevation; self-signed cert satisfies UAC requirement |
| DIST-03 | Resource path helper centralized for packaged and dev builds | sys.frozen + sys._MEIPASS detection pattern; paths.py module design; importlib.resources migration path |
</phase_requirements>

---

## Summary

PyInstaller 6.x (current 6.19.0) is the standard tool for bundling Python GUI applications as standalone Windows executables. The `--onedir` mode is strongly preferred over `--onefile` for managed Windows environments because it avoids writing to a temporary directory at startup (which requires elevated permissions or triggers Defender), and because file extraction patterns in onefile mode are a primary cause of AV false positives. For this project the decision to use onedir is already locked.

The critical challenge is resource path resolution. When PyInstaller freezes an application, `sys._MEIPASS` points to the `_internal/` subfolder inside the bundle directory — not to the directory containing the executable. All resource lookups must detect whether they are running frozen (`getattr(sys, 'frozen', False)`) and use `sys._MEIPASS` as the base, or fall back to `Path(__file__).parent` chains for dev mode. The proposed `thermal_sim/core/paths.py` module is the correct pattern: one centralized place that any module can import for safe path resolution.

The qt-material library loads theme XML files dynamically at runtime — PyInstaller's static analysis cannot discover them. The entire `qt_material` package directory (including `themes/*.xml` and `base/*.qss`) must be explicitly included in the spec file's `datas` list. Similarly, `thermal_sim/resources/materials_builtin.json` must be declared as a data file because JSON is not Python and is not auto-bundled. scipy, numpy, matplotlib, and PySide6 all have maintained hooks in `pyinstaller-hooks-contrib` and bundle correctly without extra hidden imports for the usage patterns in this project.

**Primary recommendation:** Build the spec file manually (not from CLI flags alone) so data file declarations are explicit, version-controlled, and reproducible. Use `--noupx` to minimize AV false positives on managed machines.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pyinstaller | >=6.11 (current 6.19.0) | Converts Python app to standalone exe | De-facto standard; maintains hooks for all project dependencies; active maintenance |
| pyinstaller-hooks-contrib | auto-installed with pyinstaller | Community hooks for PySide6, scipy, matplotlib, numpy | Provides correct hidden imports without manual spec work |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| signtool.exe | ships with Windows SDK / VS Build Tools | Signs the exe with a certificate | Self-signed cert creation + signing step in build.py |
| MpCmdRun.exe | built into Windows | Defender scan of output directory | Automated scan before zip step in build.py |
| zipfile (stdlib) | stdlib | Create distributable zip | Final packaging step — no extra dep needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyInstaller onedir | Nuitka | Nuitka compiles to C (lower AV risk) but requires C compiler, is slower to build, and adds toolchain complexity — overkill for this internal tool |
| PyInstaller onedir | cx_Freeze | Less maintained, fewer hooks for PySide6, more manual configuration |
| PyInstaller onedir | --onefile | onefile extracts to TEMP at startup — triggers AV and requires temp write access; explicitly rejected |
| QSplashScreen (Qt-native) | PyInstaller bootloader splash | Bootloader splash only supports static images without Qt theming; QSplashScreen integrates with the dark_amber theme |

**Installation (add to requirements.txt / build environment only):**
```bash
pip install pyinstaller pyinstaller-hooks-contrib
```
These are build-time dependencies only — they do not ship in the bundle.

---

## Architecture Patterns

### Recommended Project Structure After This Phase
```
G:/blu-thermal-simulation/
├── thermal_sim/
│   ├── core/
│   │   └── paths.py          # NEW: centralized path resolution
│   └── app/
│       └── gui.py            # MODIFIED: add splash + crash handler
├── build.py                  # NEW: automated build script
├── ThermalSim.spec           # NEW: PyInstaller spec file
├── dist/
│   └── ThermalSim/           # build output
│       ├── ThermalSim.exe
│       ├── examples/         # 3 JSON files copied here
│       └── _internal/        # PyInstaller runtime
└── ThermalSim-v1.0.zip       # distributable artifact
```

### Pattern 1: Frozen vs Dev Path Detection (paths.py)

**What:** A single module that every other module imports for safe path resolution.
**When to use:** Any code that needs to locate a resource file (JSON, icon, example project).

```python
# thermal_sim/core/paths.py
# Source: PyInstaller runtime docs https://pyinstaller.org/en/stable/runtime-information.html
from __future__ import annotations
import sys
from pathlib import Path


def _bundle_root() -> Path:
    """Root of the PyInstaller bundle (_internal dir), or package root in dev."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    # Dev mode: root is three levels up from this file (thermal_sim/core/paths.py)
    return Path(__file__).resolve().parent.parent.parent


def _exe_dir() -> Path:
    """Directory containing ThermalSim.exe (one level above _internal), or project root."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def get_resources_dir() -> Path:
    """Path to thermal_sim/resources/ — always inside _internal in bundle."""
    return _bundle_root() / "thermal_sim" / "resources"


def get_examples_dir() -> Path:
    """Path to examples/ — sits next to ThermalSim.exe in the bundle."""
    return _exe_dir() / "examples"


def get_output_dir() -> Path:
    """Default output directory: ~/Documents/ThermalSim/outputs/."""
    return Path.home() / "Documents" / "ThermalSim" / "outputs"


def get_crash_log_path() -> Path:
    """Path for crash.log — sits next to ThermalSim.exe."""
    return _exe_dir() / "crash.log"
```

**Key insight on `_MEIPASS` vs `exe_dir`:**
In a onedir build, `sys._MEIPASS` = `<bundle>/_internal/` (the runtime files), while
`Path(sys.executable).parent` = `<bundle>/` (where the .exe lives). Examples go next to
the .exe, not inside _internal. Resources that are bundled Python package data go inside
_internal alongside the .pyc files.

### Pattern 2: PyInstaller Spec File (onedir, windowed)

**What:** The .spec file declares exactly what goes into the bundle.
**When to use:** Once at build time; version-control this file.

```python
# ThermalSim.spec
# Source: https://pyinstaller.org/en/stable/spec-files.html
import os
from PyInstaller.utils.hooks import collect_data_files, collect_all

# Collect qt_material themes and base stylesheets (not auto-detected)
qt_material_datas = collect_data_files("qt_material")

# Collect thermal_sim package data (resources/*.json)
thermal_sim_datas = collect_data_files("thermal_sim")

a = Analysis(
    ["thermal_sim/app/gui.py"],
    pathex=[],
    binaries=[],
    datas=[
        *qt_material_datas,       # dark_amber.xml and all theme files
        *thermal_sim_datas,       # materials_builtin.json
    ],
    hiddenimports=[
        "thermal_sim.ui.main_window",
        "thermal_sim.core.paths",
    ],
    hookspath=[],
    hooksconfig={},
    excludes=[
        "PyQt5", "PyQt6", "PySide2",   # remove other Qt bindings (saves ~100 MB)
        "tkinter",
        "IPython",
        "jupyter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,    # onedir: binaries go in COLLECT, not EXE
    name="ThermalSim",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                # IMPORTANT: disable UPX — reduces AV false positives
    console=False,            # --windowed / --noconsole
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                # add .ico path here when asset exists
    version=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ThermalSim",
)
```

### Pattern 3: QSplashScreen (Qt-native, themed)

**What:** A Qt splash screen created before MainWindow, dismissed when MainWindow is ready.
**When to use:** The app's cold-start is dominated by scipy/numpy/PySide6 import time.

```python
# In thermal_sim/app/gui.py, inside main()
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSplashScreen.html
from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
apply_stylesheet(app, theme="dark_amber.xml")

# Build splash pixmap (no external asset required — drawn with QPainter)
pixmap = QPixmap(480, 280)
pixmap.fill(QColor("#212121"))
painter = QPainter(pixmap)
painter.setPen(QColor("#FFB300"))   # dark_amber accent
font = QFont("Segoe UI", 22, QFont.Bold)
painter.setFont(font)
painter.drawText(pixmap.rect(), Qt.AlignCenter, "Thermal Simulator\nv1.0")
painter.end()

splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
splash.show()
splash.showMessage("Loading...", Qt.AlignBottom | Qt.AlignHCenter, QColor("#e0e0e0"))
app.processEvents()

# ... import heavy modules, construct MainWindow ...
window = MainWindow()
window.show()
splash.finish(window)          # closes splash when main window is visible
```

### Pattern 4: Crash Handler in gui.py

**What:** Wraps the entire `main()` body to catch unexpected exceptions, show a Qt dialog, and write crash.log.
**When to use:** Frozen mode only — in dev mode, let exceptions propagate normally for debugging.

```python
# In thermal_sim/app/gui.py
import traceback
from thermal_sim.core.paths import get_crash_log_path

def main() -> None:
    try:
        _run_app()
    except Exception:
        tb = traceback.format_exc()
        try:
            log_path = get_crash_log_path()
            log_path.write_text(tb, encoding="utf-8")
        except Exception:
            pass
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            _app = QApplication.instance() or QApplication([])
            QMessageBox.critical(None, "Thermal Simulator — Fatal Error",
                                 f"An unexpected error occurred.\n\n{tb[:800]}\n\nSee crash.log for full details.")
        except Exception:
            pass
        raise SystemExit(1)
```

### Pattern 5: Automated build.py Script

**What:** Single Python script that orchestrates the full build pipeline.
**When to use:** Every release build.

```python
# build.py (simplified structure)
import subprocess, shutil, zipfile
from pathlib import Path

DIST_DIR = Path("dist/ThermalSim")
OUTPUT_ZIP = Path("ThermalSim-v1.0.zip")

# Step 1: Run PyInstaller
subprocess.run(["pyinstaller", "--clean", "ThermalSim.spec"], check=True)

# Step 2: Copy examples next to exe
examples_dest = DIST_DIR / "examples"
examples_dest.mkdir(exist_ok=True)
for f in Path("examples").glob("*.json"):
    shutil.copy2(f, examples_dest / f.name)

# Step 3: Sign exe (signtool must be on PATH)
# subprocess.run(["signtool", "sign", "/f", "cert.pfx", "/p", "...", str(DIST_DIR / "ThermalSim.exe")], check=True)

# Step 4: Defender scan
subprocess.run([
    r"C:\Program Files\Windows Defender\MpCmdRun.exe",
    "-Scan", "-ScanType", "3", "-File", str(DIST_DIR)
], check=False)   # non-zero exit = quarantine: fail the build

# Step 5: Create zip
with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    for f in DIST_DIR.rglob("*"):
        if f.is_file():
            zf.write(f, Path("ThermalSim") / f.relative_to(DIST_DIR))
print(f"Built: {OUTPUT_ZIP}")
```

### Anti-Patterns to Avoid

- **Using `--onefile`:** Extracts to `%TEMP%` at startup — triggers Defender, requires temp write, causes multi-second cold start. The decision is locked to onedir.
- **Using `Path.cwd()` for resource lookups in frozen mode:** `cwd()` is whatever directory the user launched from — not the bundle directory. Always use `sys._MEIPASS` or `Path(sys.executable).parent`.
- **Relying on PyInstaller to auto-detect data files:** JSON, XML, QSS files are invisible to static analysis. Declare them explicitly in the spec's `datas`.
- **Leaving UPX enabled:** UPX-compressed DLLs fail Control Flow Guard (CFG) checks on modern Windows and are a known AV trigger on managed machines. Use `upx=False` in both EXE and COLLECT.
- **Importing qt_material before QApplication exists:** `apply_stylesheet` requires a live QApplication. Ensure app is created first.
- **Writing output to the bundle directory:** The extracted bundle in a managed environment is often read-only. All user output must go to `Documents/ThermalSim/outputs/` (writable, no admin needed).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Detecting frozen vs dev mode | Custom environment variable | `getattr(sys, 'frozen', False) + sys._MEIPASS` | Official PyInstaller contract — documented API |
| Collecting qt_material theme files | Manual directory enumeration | `collect_data_files("qt_material")` in spec | Handles package relocation correctly across venvs |
| Splash image as an external PNG file | Ship a PNG asset | Draw with QPainter at runtime | Eliminates one bundled asset; can't be accidentally deleted; matches theme at runtime |
| Creating zip archive | Custom tar/zlib code | `zipfile.ZipFile` (stdlib) | Standard, no extra dep |
| AV scanning in build script | Parse Defender logs | Check MpCmdRun exit code | Non-zero exit = threat detected; simplest reliable signal |

**Key insight:** PyInstaller's hook system and `pyinstaller-hooks-contrib` already solve 90% of the bundling complexity for the dependencies in this project. The only package requiring explicit manual data collection is `qt_material` (its theme XML files are not Python modules).

---

## Common Pitfalls

### Pitfall 1: qt_material Themes Not Bundled
**What goes wrong:** The app launches but appears unstyled (grey default Qt theme) because `dark_amber.xml` is not found.
**Why it happens:** `apply_stylesheet(app, theme="dark_amber.xml")` loads the theme file from disk at runtime. PyInstaller does not follow `open()` calls or string-based file references.
**How to avoid:** Add `collect_data_files("qt_material")` to spec's `datas`. Verify with: `import qt_material; print(qt_material.__file__)` — then check that the themes/ subdirectory is in `dist/ThermalSim/_internal/qt_material/`.
**Warning signs:** App launches but all widgets render in default grey OS theme.

### Pitfall 2: materials_builtin.json Not Found
**What goes wrong:** `load_builtin_library()` raises `FileNotFoundError` on first run after bundling.
**Why it happens:** `importlib.resources.files("thermal_sim.resources")` works in dev mode because the package is on disk. In frozen mode it also works — IF PyInstaller collected the `.json` file alongside the `.pyc` files in `_internal`. PyInstaller won't auto-collect non-`.py` files unless told to.
**How to avoid:** `collect_data_files("thermal_sim")` in spec collects all non-Python files under the package, including `resources/materials_builtin.json`.
**Warning signs:** First launch crashes with `FileNotFoundError: thermal_sim/resources/materials_builtin.json`.

### Pitfall 3: examples/ Path Wrong in Frozen Mode
**What goes wrong:** The default project load (`Path("examples/steady_uniform_stack.json")`) resolves relative to `cwd()`, which is typically `C:\Users\<user>` when double-clicking — not the bundle directory.
**Why it happens:** `main_window.py:909` uses a bare relative path. In dev, `cwd` is the project root. In frozen, `cwd` is user's launch location.
**How to avoid:** Replace bare relative path with `paths.get_examples_dir() / "steady_uniform_stack.json"`. This is one of the explicit integration points listed in CONTEXT.md.
**Warning signs:** Default project fails to load; GUI opens empty with error in logs.

### Pitfall 4: Output Directory Permission Error
**What goes wrong:** Simulation results fail to save — `PermissionError` writing to the bundle directory.
**Why it happens:** On managed machines the extracted bundle folder may be on a read-only network share or a user-writable but location-restricted path.
**How to avoid:** `get_output_dir()` returns `Path.home() / "Documents" / "ThermalSim" / "outputs"`, which is always writable without admin. The `main_window.py:173` default must be changed from `Path.cwd() / "outputs"` to `paths.get_output_dir()`.
**Warning signs:** Default save fails silently; user finds no output files.

### Pitfall 5: Multiple Qt Bindings in Build Venv
**What goes wrong:** PyInstaller aborts with: "Trying to collect multiple Qt bindings packages".
**Why it happens:** If the build venv has PyQt5, PyQt6, or PySide2 installed alongside PySide6 (e.g., installed by unrelated dev tools), pyinstaller-hooks-contrib raises a hard error.
**How to avoid:** Build from a clean venv with only the packages in `requirements.txt`. Add `excludes=["PyQt5", "PyQt6", "PySide2"]` to the Analysis block as a safety net.
**Warning signs:** PyInstaller terminates mid-analysis with a multiple-Qt-bindings error.

### Pitfall 6: UPX Corrupts Qt DLLs
**What goes wrong:** Bundle crashes immediately on launch with a DLL load error on managed Windows machines with Control Flow Guard enabled.
**Why it happens:** UPX is enabled by default in PyInstaller if UPX.exe is found on PATH. Qt DLLs with CFG enabled are corrupted by UPX compression.
**How to avoid:** Always set `upx=False` in both EXE and COLLECT sections of the spec. Confirm with `--noupx` flag if running PyInstaller from CLI.
**Warning signs:** App launches in dev but crashes immediately from the dist folder.

### Pitfall 7: Defender MpCmdRun Path Varies
**What goes wrong:** `build.py` fails to run the Defender scan because `MpCmdRun.exe` is not at the hardcoded path.
**Why it happens:** The platform path changed between Windows versions. In Windows 11 the path may be `C:\ProgramData\Microsoft\Windows Defender\Platform\<version>\MpCmdRun.exe`.
**How to avoid:** Search for MpCmdRun.exe before invoking:
```python
import glob
candidates = glob.glob(r"C:\ProgramData\Microsoft\Windows Defender\Platform\*\MpCmdRun.exe")
mpcmdrun = candidates[-1] if candidates else r"C:\Program Files\Windows Defender\MpCmdRun.exe"
```
Make the scan step non-fatal if MpCmdRun is not found (warn but continue).

### Pitfall 8: sys.stdout/sys.stderr is None in Windowed Mode
**What goes wrong:** Any code that calls `print()` or logs to stderr crashes with `AttributeError: 'NoneType' object has no attribute 'write'`.
**Why it happens:** PyInstaller sets stdout/stderr to None in `--noconsole` / `--windowed` builds on Windows.
**How to avoid:** The crash handler in `gui.py` must not use `print()`. Use the crash.log file path exclusively. Avoid `logging.StreamHandler(sys.stderr)` without a None check.

---

## Code Examples

### Centralized paths.py — Full Implementation
```python
# thermal_sim/core/paths.py
# Source: PyInstaller runtime-information docs (https://pyinstaller.org/en/stable/runtime-information.html)
from __future__ import annotations
import sys
from pathlib import Path


def _bundle_root() -> Path:
    """_internal/ in frozen bundle; project root in dev mode."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


def _exe_dir() -> Path:
    """Directory of ThermalSim.exe; project root in dev mode."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def get_resources_dir() -> Path:
    return _bundle_root() / "thermal_sim" / "resources"


def get_examples_dir() -> Path:
    return _exe_dir() / "examples"


def get_output_dir() -> Path:
    return Path.home() / "Documents" / "ThermalSim" / "outputs"


def get_crash_log_path() -> Path:
    return _exe_dir() / "crash.log"
```

### Migrating material_library.py from importlib.resources
```python
# BEFORE (importlib.resources — still works in frozen but couples to package structure)
from importlib.resources import files
resource = files("thermal_sim.resources").joinpath("materials_builtin.json")
text = resource.read_text(encoding="utf-8")

# AFTER (centralized paths — works in both frozen and dev)
from thermal_sim.core.paths import get_resources_dir
resource = get_resources_dir() / "materials_builtin.json"
text = resource.read_text(encoding="utf-8")
```

### Self-Signed Certificate (PowerShell — one-time setup)
```powershell
# Source: https://learn.microsoft.com/en-us/powershell/module/pki/new-selfsignedcertificate
$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject "CN=ThermalSim Internal Build" `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -KeyExportPolicy Exportable
$pwd = ConvertTo-SecureString -String "changeme" -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath "build_cert.pfx" -Password $pwd
```

### Signing the Exe (signtool)
```bash
# signtool is in Windows SDK / VS Build Tools; find it with:
# where signtool  OR  find "C:\Program Files (x86)\Windows Kits" -name signtool.exe
signtool sign /f build_cert.pfx /p changeme /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 dist\ThermalSim\ThermalSim.exe
```

### Defender Scan in build.py
```python
# Source: https://learn.microsoft.com/en-us/defender-endpoint/command-line-arguments-microsoft-defender-antivirus
import glob, subprocess
from pathlib import Path

def run_defender_scan(target_dir: Path) -> bool:
    candidates = sorted(glob.glob(
        r"C:\ProgramData\Microsoft\Windows Defender\Platform\*\MpCmdRun.exe"
    ))
    mpcmdrun = candidates[-1] if candidates else r"C:\Program Files\Windows Defender\MpCmdRun.exe"
    result = subprocess.run(
        [mpcmdrun, "-Scan", "-ScanType", "3", "-File", str(target_dir)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[WARNING] Defender scan flagged files:\n{result.stdout}")
        return False
    print("[OK] Defender scan: no threats found")
    return True
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `os.path.dirname(sys.executable) == sys._MEIPASS` | These are different paths in onedir (exe_dir vs _internal/) | PyInstaller 6.0 | Resource lookups using `sys.executable` path break; must use `sys._MEIPASS` for bundled data |
| `--onefile` as default | `--onedir` strongly preferred for AV/managed environments | PyInstaller 5.x+ community consensus | onefile is a known AV trigger and incompatible with no-admin temp write |
| `importlib.resources` for package data in frozen apps | Still works via `PyiFrozenResourceReader`, but requires JSON files be declared in spec `datas` | PyInstaller 5.8+ | importlib.resources API works in frozen, but data files must still be explicitly bundled |
| UPX enabled by default | Disable with `upx=False` for Qt apps | PyInstaller 6.x | UPX corrupts Qt DLLs with CFG enabled on Windows 11 |
| Bootloader splash screen | QSplashScreen (Qt-native) | Bootloader splash added in PyInstaller 5.x | QSplashScreen preferred when app has Qt theming; bootloader splash has no theme awareness |

**Deprecated/outdated:**
- PyInstaller `--noconsole` flag: Still works, but `console=False` in the spec EXE block is the canonical form for a spec-driven build.

---

## Open Questions

1. **qt_material import paths on build machine vs target machine**
   - What we know: `collect_data_files("qt_material")` collects all non-Python files from the installed qt_material package.
   - What's unclear: If the build machine has qt_material installed in a non-standard location (e.g., conda prefix), the collected paths may embed absolute paths in the spec that break on other machines.
   - Recommendation: Always build from a clean venv with `pip install -r requirements.txt`. Verify the spec does not hardcode absolute source paths before committing.

2. **CrowdStrike / Cylance behavior (per STATE.md blocker)**
   - What we know: Windows Defender scan passes. The STATE.md explicitly calls out that corporate AV beyond Defender has not been verified.
   - What's unclear: CrowdStrike and Cylance use behavioral heuristics, not just signature matching. A PyInstaller onedir bundle could still be flagged.
   - Recommendation: The self-signed certificate and Defender scan in `build.py` are the extent of what can be automated. Testing on an actual managed machine is a manual step that must happen before the phase is considered done. Document this as a known limitation in the README.

3. **signtool availability without Visual Studio**
   - What we know: signtool ships with the Windows SDK (via Visual Studio or Build Tools download).
   - What's unclear: The developer's machine may not have signtool on PATH.
   - Recommendation: build.py should check for signtool with `shutil.which("signtool")` and skip signing with a clear warning if not found — the build should still succeed, just unsigned.

---

## Sources

### Primary (HIGH confidence)
- https://pyinstaller.org/en/stable/runtime-information.html — sys.frozen, sys._MEIPASS, onedir vs onefile path differences
- https://pyinstaller.org/en/stable/spec-files.html — Analysis/PYZ/EXE/COLLECT structure, datas parameter
- https://pyinstaller.org/en/stable/usage.html — PyInstaller 6.19.0 current version, --windowed, --noupx flags
- https://pyinstaller.org/en/stable/hooks.html — collect_data_files(), collect_all(), copy_metadata() API
- https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSplashScreen.html — QSplashScreen API, finish(), showMessage()
- https://learn.microsoft.com/en-us/defender-endpoint/command-line-arguments-microsoft-defender-antivirus — MpCmdRun.exe -Scan syntax

### Secondary (MEDIUM confidence)
- https://www.pythonguis.com/tutorials/packaging-pyside6-applications-windows-pyinstaller-installforge/ — PySide6+PyInstaller practical guide; data files and spec structure verified against official docs
- https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html — sys.stdout=None in windowed mode, multiprocessing freeze_support
- https://github.com/orgs/pyinstaller/discussions/8207 — PyInstaller 6.3.0 Defender false positive confirmed; onefile > onedir for AV risk
- https://github.com/upx/upx/issues/711 — UPX causes AV false positives; corroborated by PyInstaller issue #4178 (UPX corrupts CFG DLLs)

### Tertiary (LOW confidence)
- https://github.com/UN-GCPDS/qt-material — qt_material themes directory structure; confirmed datas fix needed; package README lacks explicit PyInstaller guidance

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PyInstaller 6.19.0 version verified from official docs; hooks-contrib auto-installed confirmed
- Architecture: HIGH — paths.py pattern directly derived from official PyInstaller runtime-information docs; spec file structure from official spec-files docs
- Pitfalls: HIGH for UPX/onefile/stdout/qt_material issues (multiple sources, official confirmation); MEDIUM for CrowdStrike behavior (verified as unknown in project STATE.md)

**Research date:** 2026-03-15
**Valid until:** 2026-06-15 (PyInstaller releases frequently but core onedir/spec patterns are stable; qt_material bundling pattern stable)
