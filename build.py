"""Automated build script for ThermalSim Windows distribution.

Pipeline:
    1. Clean PyInstaller build from ThermalSim.spec
    2. Copy examples/ folder next to ThermalSim.exe
    3. Sign exe with signtool (optional — skipped if cert or signtool not found)
    4. Windows Defender custom scan of dist/ThermalSim/ (optional — skipped if MpCmdRun not found)
    5. Create ThermalSim-v<VERSION>.zip distributable

Usage:
    python build.py                 # full pipeline (sign + scan if available)
    python build.py --skip-sign     # skip code signing (no cert on machine)
    python build.py --skip-scan     # skip Defender scan
    python build.py --skip-sign --skip-scan   # CI / quick dev build

Outputs:
    dist/ThermalSim/        -- onedir bundle (exe + examples + _internal)
    ThermalSim-v1.0.zip     -- distributable archive
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Version comes from the single source of truth in the app package.
# Import here so build.py always reflects the same version as the running app.
try:
    # Must be importable from the dev venv — this script is dev-only.
    sys.path.insert(0, str(Path(__file__).parent))
    from thermal_sim.core.paths import APP_VERSION
except Exception as exc:  # noqa: BLE001
    print(f"[WARNING] Could not import APP_VERSION from thermal_sim.core.paths: {exc}")
    print("[WARNING] Falling back to version string '1.0'")
    APP_VERSION = "1.0"

PROJECT_ROOT = Path(__file__).parent.resolve()
SPEC_FILE = PROJECT_ROOT / "ThermalSim.spec"
DIST_DIR = PROJECT_ROOT / "dist" / "ThermalSim"
EXAMPLES_SRC = PROJECT_ROOT / "examples"
EXAMPLES_DEST = DIST_DIR / "examples"
OUTPUT_ZIP = PROJECT_ROOT / f"ThermalSim-v{APP_VERSION}.zip"

CERT_FILE = PROJECT_ROOT / "build_cert.pfx"
# Timestamp server for RFC 3161 counter-signatures — free and reliable.
TIMESTAMP_URL = "http://timestamp.digicert.com"

# ---------------------------------------------------------------------------
# Step helpers
# ---------------------------------------------------------------------------


def _header(text: str) -> None:
    """Print a prominent step header."""
    print()
    print("=" * 60)
    print(f"  {text}")
    print("=" * 60)


def step_build() -> None:
    """Step 1: Run PyInstaller to produce the onedir bundle."""
    _header("Step 1: PyInstaller build")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        str(SPEC_FILE),
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print("[OK] PyInstaller build complete")


def step_copy_examples() -> None:
    """Step 2: Copy all JSON examples next to ThermalSim.exe."""
    _header("Step 2: Copy examples")
    EXAMPLES_DEST.mkdir(parents=True, exist_ok=True)
    json_files = list(EXAMPLES_SRC.glob("*.json"))
    if not json_files:
        print(f"[WARNING] No JSON files found in {EXAMPLES_SRC}")
    for src in json_files:
        dest = EXAMPLES_DEST / src.name
        shutil.copy2(src, dest)
        print(f"  Copied: {src.name}")
    print(f"[OK] {len(json_files)} example(s) copied to {EXAMPLES_DEST}")


def step_sign(skip: bool) -> bool:
    """Step 3: Sign ThermalSim.exe with signtool (optional).

    Returns True if signing succeeded or was intentionally skipped,
    False if signing was attempted and failed.
    """
    _header("Step 3: Code signing")

    if skip:
        print("[SKIP] --skip-sign flag set; skipping code signing")
        return True

    signtool = shutil.which("signtool")
    if not signtool:
        print("[WARNING] signtool not found on PATH — skipping code signing")
        print("          Install Windows SDK or VS Build Tools to enable signing")
        return True  # Non-fatal: build continues unsigned

    if not CERT_FILE.exists():
        print(f"[WARNING] Certificate not found: {CERT_FILE}")
        print("          Generate with: New-SelfSignedCertificate (see RESEARCH.md)")
        print("          Skipping code signing — bundle will be unsigned")
        return True  # Non-fatal: build continues unsigned

    exe_path = DIST_DIR / "ThermalSim.exe"
    cmd = [
        signtool, "sign",
        "/f", str(CERT_FILE),
        "/p", os.environ.get("BUILD_CERT_PASSWORD", ""),
        "/fd", "SHA256",
        "/tr", TIMESTAMP_URL,
        "/td", "SHA256",
        str(exe_path),
    ]
    print(f"Signing: {exe_path.name}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] signtool failed:\n{result.stderr}")
        return False
    print("[OK] Code signing complete")
    return True


def step_defender_scan(skip: bool) -> bool:
    """Step 4: Run Windows Defender custom scan on dist/ThermalSim/.

    Returns True if scan found no threats or was skipped,
    False if Defender flagged files (warning only — build does not fail).
    """
    _header("Step 4: Windows Defender scan")

    if skip:
        print("[SKIP] --skip-scan flag set; skipping Defender scan")
        return True

    # Locate MpCmdRun.exe — path varies by Windows version and Defender update.
    # Windows 11: C:\ProgramData\Microsoft\Windows Defender\Platform\<version>\MpCmdRun.exe
    # Older:      C:\Program Files\Windows Defender\MpCmdRun.exe
    candidates = sorted(
        glob.glob(
            r"C:\ProgramData\Microsoft\Windows Defender\Platform\*\MpCmdRun.exe"
        )
    )
    fallback = r"C:\Program Files\Windows Defender\MpCmdRun.exe"
    mpcmdrun = candidates[-1] if candidates else fallback

    if not Path(mpcmdrun).exists():
        print(f"[WARNING] MpCmdRun.exe not found at: {mpcmdrun}")
        print("          Skipping Defender scan — run manually before distributing")
        return True  # Non-fatal: skip scan

    print(f"Using: {mpcmdrun}")
    print(f"Scanning: {DIST_DIR}")
    result = subprocess.run(
        [mpcmdrun, "-Scan", "-ScanType", "3", "-File", str(DIST_DIR)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # Non-zero = threat detected or scan error.  Warn but don't abort —
        # different environments may have different Defender configs and false
        # positive rates vary.  The human releasing the build should investigate.
        print(f"[WARNING] Defender scan returned non-zero exit ({result.returncode})")
        if result.stdout:
            print(result.stdout[:500])
        print("          Investigate before distributing — may be a false positive")
        return False

    print("[OK] Defender scan: no threats found")
    return True


def step_zip() -> Path:
    """Step 5: Create ThermalSim-v<VERSION>.zip.

    All files archived under ThermalSim/ prefix so that extraction creates a
    single folder (ThermalSim/) rather than dumping files into the current dir.

    Returns the path to the created zip file.
    """
    _header("Step 5: Create distributable zip")

    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()
        print(f"  Removed existing: {OUTPUT_ZIP.name}")

    file_count = 0
    with zipfile.ZipFile(OUTPUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src in DIST_DIR.rglob("*"):
            if src.is_file():
                # Archive path: ThermalSim/<relative path inside dist/ThermalSim/>
                arcname = Path("ThermalSim") / src.relative_to(DIST_DIR)
                zf.write(src, arcname)
                file_count += 1

    size_mb = OUTPUT_ZIP.stat().st_size / (1024 * 1024)
    print(f"[OK] Created: {OUTPUT_ZIP.name}")
    print(f"     Files:   {file_count}")
    print(f"     Size:    {size_mb:.1f} MB")
    return OUTPUT_ZIP


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the ThermalSim Windows distribution bundle."
    )
    parser.add_argument(
        "--skip-sign",
        action="store_true",
        help="Skip code signing with signtool (build continues unsigned)",
    )
    parser.add_argument(
        "--skip-scan",
        action="store_true",
        help="Skip the Windows Defender scan of the output directory",
    )
    args = parser.parse_args()

    warnings: list[str] = []

    # Step 1: Build
    step_build()

    # Step 2: Copy examples
    step_copy_examples()

    # Step 3: Sign
    sign_ok = step_sign(skip=args.skip_sign)
    if not sign_ok:
        warnings.append("Code signing failed — bundle is unsigned")

    # Step 4: Defender scan
    scan_ok = step_defender_scan(skip=args.skip_scan)
    if not scan_ok:
        warnings.append("Defender scan flagged files — investigate before distributing")

    # Step 5: Zip
    zip_path = step_zip()

    # Final summary
    _header("Build Summary")
    print(f"  Bundle:   {DIST_DIR}")
    print(f"  Zip:      {zip_path}")
    print(f"  Version:  v{APP_VERSION}")
    print(f"  Zip size: {zip_path.stat().st_size / (1024 * 1024):.1f} MB")

    if warnings:
        print()
        print("Warnings:")
        for w in warnings:
            print(f"  [!] {w}")
        print()
        print("[DONE] Build completed with warnings — review before distributing")
    else:
        print()
        print("[DONE] Build completed successfully")


if __name__ == "__main__":
    main()
