from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".exr"}
_TRAILING_FRAME_RE = re.compile(r"^(?P<prefix>.*?)(?P<frame>\d+)$")


@dataclass(slots=True)
class SequenceGroup:
    name: str
    paths: list[Path]

    @property
    def first_frame(self) -> int | None:
        if not self.paths:
            return None
        match = _TRAILING_FRAME_RE.match(self.paths[0].stem)
        return int(match.group("frame")) if match else None

    @property
    def last_frame(self) -> int | None:
        if not self.paths:
            return None
        match = _TRAILING_FRAME_RE.match(self.paths[-1].stem)
        return int(match.group("frame")) if match else None


def supported_image_paths(folder: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=natural_sort_key,
    )


def natural_sort_key(path: Path) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", path.name.lower())
    key: list[object] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        elif part:
            key.append(part)
    return tuple(key)


def detect_sequences(folder: Path) -> list[SequenceGroup]:
    paths = supported_image_paths(folder)
    if not paths:
        return []

    numbered: dict[tuple[str, str, int], list[Path]] = {}
    fallback: list[Path] = []
    for path in paths:
        match = _TRAILING_FRAME_RE.match(path.stem)
        if not match:
            fallback.append(path)
            continue
        prefix = match.group("prefix")
        digits = len(match.group("frame"))
        key = (prefix, path.suffix.lower(), digits)
        numbered.setdefault(key, []).append(path)

    groups: list[SequenceGroup] = []
    for (prefix, extension, digits), items in sorted(numbered.items()):
        if len(items) < 2:
            fallback.extend(items)
            continue
        items.sort(key=natural_sort_key)
        first = _TRAILING_FRAME_RE.match(items[0].stem)
        last = _TRAILING_FRAME_RE.match(items[-1].stem)
        first_frame = first.group("frame") if first else "?"
        last_frame = last.group("frame") if last else "?"
        label_prefix = prefix or "sequence_"
        label = f"{label_prefix}[{first_frame}-{last_frame}] {extension}"
        groups.append(SequenceGroup(name=label, paths=items))

    if fallback:
        fallback.sort(key=natural_sort_key)
        groups.append(SequenceGroup(name="All supported images", paths=fallback))

    return groups


def group_selected_files(paths: list[Path]) -> SequenceGroup:
    ordered = sorted(paths, key=natural_sort_key)
    if not ordered:
        return SequenceGroup(name="Empty selection", paths=[])
    name = f"Manual selection ({len(ordered)} frames)"
    return SequenceGroup(name=name, paths=ordered)


def choose_primary_sequence(groups: list[SequenceGroup]) -> SequenceGroup:
    if not groups:
        raise ValueError("No sequence groups available.")
    return max(groups, key=lambda group: (len(group.paths), group.name))
