# Install on macOS

## Release build

Download the macOS asset from GitHub Releases and drag Melodex into Applications.

Unsigned development builds may require **System Settings → Privacy & Security → Open Anyway**.

## Run from source

```bash
cd desktop
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

For deep Flow analysis install FFmpeg:

```bash
brew install ffmpeg
```
