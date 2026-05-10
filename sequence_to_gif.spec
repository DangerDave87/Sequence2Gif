from pathlib import Path
import importlib.util

project_root = Path(SPECPATH)
assets_dir = project_root / "assets"

datas = []
if assets_dir.exists():
    datas.append((str(assets_dir), "assets"))

hiddenimports = []
excludes = ["imageio", "ssl", "_ssl", "PySide6.support", "PySide6.scripts"]

if importlib.util.find_spec("OpenImageIO") is not None:
    hiddenimports.append("OpenImageIO")

a = Analysis(
    ["app.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SequenceToGif",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(assets_dir / "app_icon.ico") if (assets_dir / "app_icon.ico").exists() else None,
)
