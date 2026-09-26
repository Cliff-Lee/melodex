# Install on Windows

Download the Windows installer or portable archive from GitHub Releases.

## Run from source

PowerShell:

```powershell
cd desktop
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Install FFmpeg and make `ffmpeg.exe` available on PATH for deep Flow analysis.
