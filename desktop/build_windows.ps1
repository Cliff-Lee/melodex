$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
py -3.12 -m venv .venv-build
& .\.venv-build\Scripts\python.exe -m pip install --upgrade pip
& .\.venv-build\Scripts\pip.exe install -r requirements-build.txt
Remove-Item -Recurse -Force build,dist -ErrorAction SilentlyContinue
& .\.venv-build\Scripts\pyinstaller.exe --noconfirm --windowed --name Melodex --icon ..\assets\icon.ico --add-data "melodex/assets/melodex-mark.png;melodex/assets" --add-data "melodex/bundled_providers;melodex/bundled_providers" --collect-all PySide6 run.py
Compress-Archive -Path dist\Melodex\* -DestinationPath dist\Melodex-Windows-portable.zip -Force
