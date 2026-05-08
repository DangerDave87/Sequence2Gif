from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import OpenImageIO as oiio
except ImportError:  # pragma: no cover - depends on local runtime
    oiio = None

from .sequence import SUPPORTED_EXTENSIONS

CHECKER_LIGHT = np.array([84, 92, 106], dtype=np.uint8)
CHECKER_DARK = np.array([58, 64, 74], dtype=np.uint8)


@dataclass(slots=True)
class ExportSettings:
    width: int
    height: int
    fps: float
    use_transparency: bool
    matte_color: tuple[int, int, int]
    dither: bool
    alpha_threshold: int
    loop_count: int | None


def load_rgba_frame(path: Path) -> np.ndarray:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported image type: {path.suffix}")
    if suffix == ".exr":
        return _load_exr_rgba(path)
    image = Image.open(path)
    return np.asarray(image.convert("RGBA"), dtype=np.uint8)


def render_preview_frame(
    frame_rgba: np.ndarray,
    preview_size: tuple[int, int],
    matte_color: tuple[int, int, int],
    use_transparency: bool,
    alpha_threshold: int,
) -> Image.Image:
    width, height = preview_size
    source_height, source_width = frame_rgba.shape[:2]
    scale = min(width / max(source_width, 1), height / max(source_height, 1))
    scale = max(scale, 0.01)
    fit_width = max(1, round(source_width * scale))
    fit_height = max(1, round(source_height * scale))
    fit = resize_rgba(frame_rgba, width=fit_width, height=fit_height)
    rgb, alpha = composite_to_rgb(
        fit,
        matte_color=matte_color,
        keep_transparency=use_transparency,
        alpha_threshold=alpha_threshold,
    )
    if alpha is None:
        return Image.fromarray(rgb)
    checker = checkerboard(rgb.shape[1], rgb.shape[0])
    blended = np.where(alpha[..., None] == 0, checker, rgb)
    return Image.fromarray(blended)


def resize_rgba(frame_rgba: np.ndarray, width: int, height: int) -> np.ndarray:
    image = Image.fromarray(frame_rgba)
    resized = image.resize((width, height), Image.Resampling.LANCZOS)
    return np.asarray(resized, dtype=np.uint8)


def composite_to_rgb(
    frame_rgba: np.ndarray,
    matte_color: tuple[int, int, int],
    keep_transparency: bool,
    alpha_threshold: int,
) -> tuple[np.ndarray, np.ndarray | None]:
    rgba = frame_rgba.astype(np.float32) / 255.0
    rgb = rgba[..., :3]
    alpha = rgba[..., 3:4]
    matte = np.asarray(matte_color, dtype=np.float32).reshape(1, 1, 3) / 255.0
    blended = rgb * alpha + matte * (1.0 - alpha)
    blended_uint8 = np.clip(np.round(blended * 255.0), 0, 255).astype(np.uint8)

    if not keep_transparency:
        return blended_uint8, None

    alpha_channel = frame_rgba[..., 3]
    opaque_mask = alpha_channel > alpha_threshold
    flattened = blended_uint8.copy()
    flattened[~opaque_mask] = matte_color
    return flattened, opaque_mask.astype(np.uint8)


def checkerboard(width: int, height: int, tile: int = 12) -> np.ndarray:
    grid_y, grid_x = np.indices((height, width))
    mask = ((grid_x // tile) + (grid_y // tile)) % 2 == 0
    image = np.empty((height, width, 3), dtype=np.uint8)
    image[mask] = CHECKER_LIGHT
    image[~mask] = CHECKER_DARK
    return image


def save_gif(paths: list[Path], output_path: Path, settings: ExportSettings) -> None:
    if not paths:
        raise ValueError("No frames selected.")
    if settings.width <= 0 or settings.height <= 0:
        raise ValueError("Width and height must be positive.")
    if settings.fps <= 0:
        raise ValueError("FPS must be greater than zero.")

    prepared_frames: list[np.ndarray] = []
    transparency_masks: list[np.ndarray | None] = []
    for path in paths:
        rgba = load_rgba_frame(path)
        resized = resize_rgba(rgba, width=settings.width, height=settings.height)
        rgb, mask = composite_to_rgb(
            resized,
            matte_color=settings.matte_color,
            keep_transparency=settings.use_transparency,
            alpha_threshold=settings.alpha_threshold,
        )
        prepared_frames.append(rgb)
        transparency_masks.append(mask)

    duration_ms = max(1, round(1000 / settings.fps))
    dither_method = Image.Dither.FLOYDSTEINBERG if settings.dither else Image.Dither.NONE
    save_kwargs = {
        "save_all": True,
        "append_images": None,
        "duration": duration_ms,
        "optimize": False,
        "disposal": 2,
    }
    if settings.loop_count is not None:
        save_kwargs["loop"] = settings.loop_count

    if settings.use_transparency:
        palette_image = build_palette(prepared_frames, color_count=255)
        frames = [
            quantize_with_transparency(frame, mask, palette_image, dither_method)
            for frame, mask in zip(prepared_frames, transparency_masks)
        ]
        save_kwargs["append_images"] = frames[1:]
        frames[0].save(
            output_path,
            transparency=255,
            **save_kwargs,
        )
        return

    palette_image = build_palette(prepared_frames, color_count=256)
    frames = [
        Image.fromarray(frame).quantize(palette=palette_image, dither=dither_method)
        for frame in prepared_frames
    ]
    save_kwargs["append_images"] = frames[1:]
    frames[0].save(
        output_path,
        **save_kwargs,
    )


def build_palette(frames: list[np.ndarray], color_count: int) -> Image.Image:
    sampled = [downsample_for_palette(frame) for frame in sample_frames(frames)]
    widths = [frame.shape[1] for frame in sampled]
    heights = [frame.shape[0] for frame in sampled]
    canvas = Image.new("RGB", (sum(widths), max(heights)))
    offset_x = 0
    for frame in sampled:
        image = Image.fromarray(frame)
        canvas.paste(image, (offset_x, 0))
        offset_x += frame.shape[1]

    palette_base = canvas.quantize(colors=color_count, method=Image.Quantize.MEDIANCUT)
    if color_count == 256:
        return palette_base

    raw_palette = palette_base.getpalette()[: color_count * 3]
    transparent_rgb = [0, 0, 0]
    palette = raw_palette + transparent_rgb
    palette.extend([0] * (768 - len(palette)))
    palette_image = Image.new("P", (1, 1))
    palette_image.putpalette(palette)
    return palette_image


def sample_frames(frames: list[np.ndarray], limit: int = 12) -> list[np.ndarray]:
    if len(frames) <= limit:
        return frames
    indices = np.linspace(0, len(frames) - 1, num=limit, dtype=int)
    return [frames[index] for index in indices]


def downsample_for_palette(frame: np.ndarray, max_side: int = 160) -> np.ndarray:
    height, width = frame.shape[:2]
    scale = min(1.0, max_side / max(width, height))
    new_width = max(1, math.floor(width * scale))
    new_height = max(1, math.floor(height * scale))
    if new_width == width and new_height == height:
        return frame
    image = Image.fromarray(frame)
    resized = image.resize((new_width, new_height), Image.Resampling.BILINEAR)
    return np.asarray(resized, dtype=np.uint8)


def quantize_with_transparency(
    frame_rgb: np.ndarray,
    alpha_mask: np.ndarray | None,
    palette_image: Image.Image,
    dither: Image.Dither,
) -> Image.Image:
    if alpha_mask is None:
        raise ValueError("Alpha mask is required when transparency is enabled.")
    quantized = Image.fromarray(frame_rgb).quantize(
        palette=palette_image,
        dither=dither,
    )
    frame_data = np.asarray(quantized, dtype=np.uint8).copy()
    frame_data[alpha_mask == 0] = 255
    transparent_frame = Image.fromarray(frame_data, mode="P")
    transparent_frame.putpalette(palette_image.getpalette())
    transparent_frame.info["transparency"] = 255
    return transparent_frame


def _load_exr_rgba(path: Path) -> np.ndarray:
    if oiio is None:
        raise ValueError("EXR reading is unavailable. Install OpenImageIO.")
    return _load_exr_with_openimageio(path)


def _load_exr_with_openimageio(path: Path) -> np.ndarray:
    input_file = oiio.ImageInput.open(str(path))
    if input_file is None:
        error_text = oiio.geterror() or f"Could not open EXR file: {path.name}"
        raise ValueError(error_text)
    try:
        spec = input_file.spec()
        channel_count = spec.nchannels
        pixel_data = input_file.read_image(format=oiio.FLOAT)
    finally:
        input_file.close()

    if pixel_data is None:
        error_text = oiio.geterror() or f"Could not read EXR file: {path.name}"
        raise ValueError(error_text)

    array = np.asarray(pixel_data, dtype=np.float32)
    if array.ndim == 1:
        array = array.reshape((spec.height, spec.width, channel_count))
    else:
        array = array.reshape((spec.height, spec.width, channel_count))
    return _exr_channels_to_rgba(array, spec.channelnames)


def _exr_channels_to_rgba(array: np.ndarray, channel_names: list[str]) -> np.ndarray:
    if array.ndim != 3:
        raise ValueError("Unexpected EXR image layout.")

    lowered = [name.lower() for name in channel_names]

    def get_channel(*candidates: str) -> np.ndarray | None:
        for candidate in candidates:
            if candidate in lowered:
                index = lowered.index(candidate)
                return array[..., index]
        return None

    red = get_channel("r", "red")
    green = get_channel("g", "green")
    blue = get_channel("b", "blue")
    alpha = get_channel("a", "alpha")

    if red is None or green is None or blue is None:
        if array.shape[2] == 1:
            mono = array[..., 0]
            red = green = blue = mono
        elif array.shape[2] >= 3:
            red = array[..., 0]
            green = array[..., 1]
            blue = array[..., 2]
        else:
            raise ValueError("EXR file does not contain readable color channels.")

    if alpha is None:
        alpha = np.ones_like(red, dtype=np.float32)

    rgba = np.stack([red, green, blue, alpha], axis=-1).astype(np.float32, copy=False)
    return _finalize_exr_rgba(rgba)


def _finalize_exr_rgba(rgba: np.ndarray) -> np.ndarray:
    rgba = rgba.astype(np.float32, copy=False)
    rgba[..., :3] = _linear_to_srgb(np.clip(rgba[..., :3], 0.0, None))
    rgba[..., 3] = np.clip(rgba[..., 3], 0.0, 1.0)
    return np.clip(np.round(rgba * 255.0), 0, 255).astype(np.uint8)


def _linear_to_srgb(values: np.ndarray) -> np.ndarray:
    threshold = 0.0031308
    low = values * 12.92
    high = 1.055 * np.power(np.clip(values, threshold, None), 1.0 / 2.4) - 0.055
    return np.where(values <= threshold, low, high)
