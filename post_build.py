from __future__ import annotations

import shutil
from pathlib import Path


def remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def prune_dist() -> int:
    project_root = Path(__file__).resolve().parent
    dist_root = project_root / "dist"
    app_root = dist_root / "SequenceToGif"
    internal_root = app_root / "_internal"
    py_side_root = internal_root / "PySide6"

    if not app_root.exists():
        print("No dist/SequenceToGif folder found, skipping prune step.")
        return 0

    remove_path(dist_root / "SequenceToGif.exe")

    remove_targets = [
        py_side_root / "Qt6Quick.dll",
        py_side_root / "Qt6Qml.dll",
        py_side_root / "Qt6QmlModels.dll",
        py_side_root / "Qt6QmlMeta.dll",
        py_side_root / "Qt6QmlWorkerScript.dll",
        py_side_root / "Qt6Pdf.dll",
        py_side_root / "Qt6VirtualKeyboard.dll",
        py_side_root / "Qt6Svg.dll",
        py_side_root / "Qt6OpenGL.dll",
        py_side_root / "opengl32sw.dll",
        py_side_root / "translations",
        py_side_root / "plugins" / "generic",
        py_side_root / "plugins" / "networkinformation",
        py_side_root / "plugins" / "platforminputcontexts",
        py_side_root / "plugins" / "styles",
        py_side_root / "plugins" / "tls",
        py_side_root / "plugins" / "iconengines" / "qsvgicon.dll",
        py_side_root / "plugins" / "imageformats" / "qicns.dll",
        py_side_root / "plugins" / "imageformats" / "qpdf.dll",
        py_side_root / "plugins" / "imageformats" / "qsvg.dll",
        py_side_root / "plugins" / "imageformats" / "qtga.dll",
        py_side_root / "plugins" / "imageformats" / "qtiff.dll",
        py_side_root / "plugins" / "imageformats" / "qwbmp.dll",
        py_side_root / "plugins" / "imageformats" / "qwebp.dll",
        py_side_root / "plugins" / "platforms" / "qdirect2d.dll",
        py_side_root / "plugins" / "platforms" / "qminimal.dll",
        py_side_root / "plugins" / "platforms" / "qoffscreen.dll",
        internal_root / "PIL" / "_avif.cp311-win_amd64.pyd",
        internal_root / "PIL" / "_webp.cp311-win_amd64.pyd",
        internal_root / "PIL" / "_imagingtk.cp311-win_amd64.pyd",
    ]

    for target in remove_targets:
        remove_path(target)

    for directory in sorted(py_side_root.rglob("*"), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()

    total_bytes = sum(path.stat().st_size for path in app_root.rglob("*") if path.is_file())
    total_mb = round(total_bytes / (1024 * 1024), 2)
    print(f"Pruned dist/SequenceToGif to {total_mb} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(prune_dist())
