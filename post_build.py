from __future__ import annotations

from pathlib import Path


def finalize_dist() -> int:
    project_root = Path(__file__).resolve().parent
    dist_root = project_root / "dist"
    app_folder = dist_root / "SequenceToGif"
    exe_path = dist_root / "SequenceToGif.exe"

    if app_folder.exists():
        for child in sorted(app_folder.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        app_folder.rmdir()

    if not exe_path.exists():
        print("No dist/SequenceToGif.exe found, skipping finalize step.")
        return 0

    total_bytes = exe_path.stat().st_size
    total_mb = round(total_bytes / (1024 * 1024), 2)
    print(f"Built dist/SequenceToGif.exe at {total_mb} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(finalize_dist())
