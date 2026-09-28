# Build Melodex from Source

This page runs the current development branch rather than installing the latest packaged release.

See [Release status](RELEASE_STATUS.md) for the difference.

## Prerequisites

Desktop development currently expects:

- Python 3.11 or newer;
- Git;
- platform audio/UI support required by PySide6;
- optional FFmpeg for deeper local audio analysis.

## Desktop development

From the repository root:

```bash
cd desktop
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

Windows PowerShell:

```powershell
cd desktop
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

## Optional MCP support

MCP is not required for ordinary playback.

From `desktop/` with the environment activated:

```bash
python -m pip install -r requirements-mcp.txt
```

## Desktop packaged builds

The repository's supported packaged-build workflows currently target macOS and Windows.

macOS:

```bash
cd desktop
./build_macos.sh
```

Windows PowerShell:

```powershell
cd desktop
.\build_windows.ps1
```

Those scripts create isolated build environments and use the build requirements declared by the repository.

## Android

The Android project is a Bridge-client preview rather than the desktop application ported unchanged to Android.

Repository CI builds it using Java 17, Gradle and Android SDK 35.

For local development, open `android/` in a compatible Android Studio setup or run Gradle with the required Android SDK installed.

## Provider / extension development

You do not need to run/build all of Melodex to develop an extension.

Use the [5-minute Developer Quickstart](DEVELOPER_QUICKSTART.md).

## Before opening a PR

Run the relevant checks from the repository root:

```bash
python scripts/docs_check.py
python scripts/ecosystem_check.py
python scripts/api_docs_check.py
python scripts/release_check.py
```

Desktop tests:

```bash
PYTHONPATH=desktop pytest -q desktop/tests
```

Provider SDK tests:

```bash
cd provider-sdk
pytest -q tests
```
