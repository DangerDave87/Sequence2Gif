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

## Start GUI

```powershell
.\dist\SequenceToGif.exe
```

## Use CLI

Convert a folder-based sequence:

```powershell
.\dist\SequenceToGif.exe convert "C:\path\to\sequence_folder" --output "C:\path\to\output.gif"
```

Convert an explicit list of files:

```powershell
.\dist\SequenceToGif.exe convert frame_0001.png frame_0002.png frame_0003.png --output out.gif
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

For development without building an exe first, you can still use:

```powershell
python app.py
```

```powershell
python app.py convert "C:\path\to\sequence_folder" --output "C:\path\to\output.gif"
```

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
The packaged app will be created as `dist\SequenceToGif.exe`. That single file can be copied to another Windows PC without separately installing Python.
The build script also runs [post_build.py](/C:/Users/daten/Documents/New%20project%202/post_build.py), which removes any leftover folder-based build output so only the single executable remains.

## Notes

- GIF only supports 1-bit transparency. Semi-transparent edges are flattened against the chosen matte color.
- EXR import now prefers `OpenImageIO`, which is a better fit for EXR-heavy workflows and channel-aware image loading.
- EXR import requires `OpenImageIO`.
- Build and package the app in an environment where `OpenImageIO` is installed so EXR support is included in the executable.
- A single-file build is easier to move around, but it will usually be larger and start a bit slower than a folder-based build.
- Most of the size comes from bundled Qt, Python, NumPy, Pillow, and OpenImageIO runtime files.
