$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
py -3.12 -m venv .venv-build
& .\.venv-build\Scripts\python.exe -m pip install --upgrade pip
& .\.venv-build\Scripts\pip.exe install -r requirements-build.txt
Remove-Item -Recurse -Force build,dist -ErrorAction SilentlyContinue
& .\.venv-build\Scripts\pyinstaller.exe --noconfirm --windowed --name Melodex --icon ..\assets\icon.ico --add-data "melodex/assets/melodex-mark.png;melodex/assets" --add-data "melodex/bundled_providers;melodex/bundled_providers" --collect-all PySide6 --collect-all keyring run.py
& .\.venv-build\Scripts\python.exe .\check_bundled_provider_payload.py .\dist\Melodex
& .\.venv-build\Scripts\python.exe .\frozen_child_smoke.py .\dist\Melodex\Melodex.exe
Compress-Archive -Path dist\Melodex\* -DestinationPath dist\Melodex-Windows-portable.zip -Force
