# Build from source

## Desktop development

```bash
cd desktop
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

## Desktop packaged build

macOS:

```bash
./build_macos.sh
```

Windows PowerShell:

```powershell
.\build_windows.ps1
```

## Android

The repository CI installs Gradle and the Android SDK automatically. Locally, open `android/` in Android Studio or run Gradle with Android SDK 35 available.
