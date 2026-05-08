@echo off
python -m PyInstaller --noconfirm --clean sequence_to_gif.spec
python "%~dp0post_build.py"
