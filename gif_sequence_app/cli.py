from __future__ import annotations

import argparse
from pathlib import Path

from .converter import ExportSettings, load_rgba_frame, save_gif
from .sequence import choose_primary_sequence, detect_sequences, group_selected_files


def build_convert_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("convert", help="Convert an image sequence to GIF from the command line.")
    parser.add_argument(
        "inputs",
        nargs="+",
        help="A folder containing a sequence, or an explicit list of image files.",
    )
    parser.add_argument("-o", "--output", required=True, help="Output GIF path.")
    parser.add_argument("--scale", type=int, default=100, help="Output scale percentage. Default: 100.")
    parser.add_argument("--fps", type=float, default=24.0, help="Frames per second. Default: 24.")
    parser.add_argument(
        "--loop-mode",
        choices=("infinite", "fixed", "none"),
        default="infinite",
        help="Loop mode for the exported GIF.",
    )
    parser.add_argument(
        "--loop-count",
        type=int,
        default=1,
        help="Loop count when --loop-mode fixed is used. Default: 1.",
    )
    parser.add_argument(
        "--alpha-threshold",
        type=int,
        default=10,
        help="Alpha threshold for transparent pixels. Default: 10.",
    )
    parser.add_argument(
        "--matte",
        default="18,18,22",
        help="Matte color as R,G,B. Default: 18,18,22.",
    )
    parser.add_argument(
        "--no-transparency",
        action="store_true",
        help="Flatten all alpha against the matte color instead of using GIF transparency.",
    )
    parser.add_argument(
        "--no-dither",
        action="store_true",
        help="Disable dithering during GIF palette quantization.",
    )


def run_convert_command(args: argparse.Namespace) -> int:
    try:
        sequence_paths = _resolve_sequence_paths(args.inputs)
        first_frame = load_rgba_frame(sequence_paths[0])
        source_height, source_width = first_frame.shape[:2]
        width = max(1, round(source_width * args.scale / 100.0))
        height = max(1, round(source_height * args.scale / 100.0))
        matte_color = _parse_matte_color(args.matte)
        settings = ExportSettings(
            width=width,
            height=height,
            fps=args.fps,
            use_transparency=not args.no_transparency,
            matte_color=matte_color,
            dither=not args.no_dither,
            alpha_threshold=args.alpha_threshold,
            loop_count=_resolve_loop_count(args.loop_mode, args.loop_count),
        )
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        print(
            f"Converting {len(sequence_paths)} frame(s) to {output_path} at {width}x{height}, {args.fps} fps..."
        )
        save_gif(sequence_paths, output_path, settings)
    except Exception as error:  # noqa: BLE001
        print(f"Error: {error}")
        return 1

    print(f"GIF written to {output_path}")
    return 0


def _resolve_sequence_paths(inputs: list[str]) -> list[Path]:
    paths = [Path(item) for item in inputs]
    if len(paths) == 1 and paths[0].is_dir():
        groups = detect_sequences(paths[0])
        if not groups:
            raise ValueError("The selected folder does not contain JPG, PNG, or EXR images.")
        return choose_primary_sequence(groups).paths

    missing = [path for path in paths if not path.exists()]
    if missing:
        joined = ", ".join(str(path) for path in missing)
        raise ValueError(f"Input path(s) not found: {joined}")
    return group_selected_files(paths).paths


def _parse_matte_color(value: str) -> tuple[int, int, int]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise ValueError("Matte color must be provided as R,G,B.")
    try:
        color = tuple(int(part) for part in parts)
    except ValueError as error:
        raise ValueError("Matte color values must be integers.") from error
    if any(channel < 0 or channel > 255 for channel in color):
        raise ValueError("Matte color values must be between 0 and 255.")
    return color


def _resolve_loop_count(loop_mode: str, loop_count: int) -> int | None:
    if loop_mode == "infinite":
        return 0
    if loop_mode == "fixed":
        if loop_count < 1 or loop_count > 9999:
            raise ValueError("Loop count must be between 1 and 9999.")
        return loop_count
    return None
