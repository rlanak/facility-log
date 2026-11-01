# -*- mode: python ; coding: utf-8 -*-
# Builds the standalone FacilityLog.exe. See CLAUDE.md ("Empacotamento") for
# the full build procedure. Run scripts/prepare_tesseract_vendor.py and
# scripts/prepare_msupps_parser_vendor.py first — this spec expects
# vendor/tesseract/ and vendor/msupps-parser/ to already exist.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH)

datas = [
    (str(ROOT / "web"), "web"),
    (str(ROOT / "data" / "foxhole"), "data/foxhole"),
    (str(ROOT / "vendor" / "tesseract"), "tesseract"),
    (str(ROOT / "vendor" / "msupps-parser"), "msupps-parser"),
    # RapidOCR's ONNX models + yaml configs ship inside the package; without
    # them it would try to download models on first use.
    *collect_data_files("rapidocr"),
]

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "python_multipart",
    # Loaded by name from its config, invisible to static analysis.
    *collect_submodules("rapidocr"),
]

a = Analysis(
    ["run.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="FacilityLog",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
