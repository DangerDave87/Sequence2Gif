# Sequence to GIF

PySide6 desktop app for converting JPG, PNG, and EXR image sequences into animated GIFs.

## Features

- Detects numbered image sequences in a folder
- Supports manual multi-file selection
- Reads JPG, PNG, and EXR frames
- Keeps PNG and EXR alpha as far as GIF allows
- Lets you set output size, FPS, loop count, dithering, transparency, alpha threshold, and matte color
- Includes a dark theme and a live frame preview
- Can be packaged into a Windows executable

## Run GUI

```powershell
python app.py
```

## Run CLI

Convert a folder-based sequence:

```powershell
python app.py convert "C:\path\to\sequence_folder" --output "C:\path\to\output.gif"
```

Convert an explicit list of files:

```powershell
python app.py convert frame_0001.png frame_0002.png frame_0003.png --output out.gif
```

Useful CLI options:

- `--scale 50`
- `--fps 12`
- `--loop-mode infinite|fixed|none`
- `--loop-count 5`
- `--matte 18,18,22`
- `--alpha-threshold 10`
- `--no-transparency`
- `--no-dither`

## Build an executable

Install the runtime dependencies and build dependency first:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Then build the app:

```bat
build_exe.bat
```

The packaged app will be created in `dist\SequenceToGif\`. Start it with `dist\SequenceToGif\SequenceToGif.exe`. That folder can be copied to another Windows PC without separately installing Python.
The build script also runs [post_build.py](/C:/Users/daten/Documents/New%20project%202/post_build.py), which prunes unused Qt and Pillow files and removes the extra non-working `dist\SequenceToGif.exe` stub.

## Notes

- GIF only supports 1-bit transparency. Semi-transparent edges are flattened against the chosen matte color.
- EXR import now prefers `OpenImageIO`, which is a better fit for EXR-heavy workflows and channel-aware image loading.
- EXR import requires `OpenImageIO`.
- Build and package the app in an environment where `OpenImageIO` is installed so EXR support is included in the executable.
- A one-folder build keeps the actual `.exe` much smaller than a single-file PyInstaller build.
- Most of the remaining size comes from bundled Qt and OpenImageIO runtime files.
