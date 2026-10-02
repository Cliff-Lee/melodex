# Desktop bundle size

An external tester reported that the installed macOS app was approximately
673 MB. Campaign 8 treats bundle size as a measured build-quality problem rather
than guessing which dependency is responsible.

## Campaign 8A — measure before trimming

The macOS build now writes:

- `dist/Melodex-bundle-size.json`
- `dist/Melodex-bundle-size.md`

The report records:

- installed `.app` bytes
- DMG bytes when available
- total files
- largest bundle areas
- largest individual files
- size grouped by file extension

Symlinks are excluded from byte totals so framework symlink layouts are not
double-counted.

The GitHub macOS build also appends the readable report to the workflow summary
and uploads both report files alongside the DMG.

## Local use

After building Melodex:

```bash
cd desktop
python tools/report_bundle_size.py dist/Melodex.app \
  --archive dist/Melodex.dmg \
  --json-out dist/Melodex-bundle-size.json \
  --markdown-out dist/Melodex-bundle-size.md
```

Campaign 8A intentionally changes **no bundled dependencies**. Its output is the
baseline for the next small campaign, which will trim Qt/PySide components and
compare the result against exactly the same report.

## Acceptance checks

- every macOS build produces a machine-readable and human-readable size report
- installed bundle and compressed DMG sizes are reported separately
- the largest framework/resource areas are visible without unpacking the app manually
- symlinked framework files are not counted twice
- size reporting does not change runtime contents or behaviour


## Campaign 8B — minimal Qt bundle

The 8A Intel baseline measured:

- installed `Melodex.app`: **701,886,703 bytes (669.4 MB)**
- compressed DMG: **306,247,025 bytes (292.1 MB)**
- `Contents/Frameworks/PySide6`: **605,719,380 bytes**
- `Contents/Resources/PySide6`: **50,434,264 bytes**
- `QtWebEngineCore` alone: **247,131,536 bytes**

Melodex source imports only four Qt families:

```text
QtCore
QtGui
QtWidgets
QtMultimedia
QtNetwork
```

8B therefore removes PyInstaller's blanket `--collect-all PySide6` from both
macOS and Windows builds and lets the PyInstaller Qt hooks collect the imported
modules plus their runtime dependencies.

A build-time guard verifies the five required PySide modules remain present and
rejects heavyweight families that Melodex does not use, including WebEngine,
QML/Quick, Quick3D, Designer, PDF, Charts, Bluetooth, NFC, Sensors, Serial and
Qt SQL drivers.

`--collect-all keyring` is deliberately unchanged in this campaign. Python,
NumPy and other dependency trimming belongs to 8C.

### 8B acceptance checks

- macOS Intel and Apple Silicon frozen builds still launch and pass child-process/provider smoke tests
- Windows frozen build still passes the same smoke tests
- QtCore, QtGui, QtWidgets, QtMultimedia and QtNetwork remain present
- QtWebEngine and the other explicitly unused heavyweight Qt families are absent
- installed macOS size is materially below the 669.4 MB 8A baseline
- the same 8A report is generated so before/after numbers are directly comparable


## Campaign 8C — non-Qt runtime audit

After the Qt cleanup, the Intel macOS bundle is approximately **124 MB**. The
largest remaining non-Qt components are now real runtime features rather than
obvious accidental payload:

- NumPy: about **10.5 MB** — used by Flow and local audio analysis
- Python runtime / dynamic modules: about **16 MB** — required by the frozen app
- OpenSSL libraries: about **4.9 MB** — required for HTTPS
- keyring package/data: small, but the previous build still used blanket
  `--collect-all keyring`

8C therefore starts conservatively. It removes blanket keyring collection and
relies on PyInstaller's keyring hooks to include only the platform-appropriate
backend. A frozen-runtime smoke probe then verifies that:

- NumPy FFT/percentile operations work
- Requests can locate its CA bundle
- OpenSSL is available
- macOS and Windows discover a usable native keyring backend

The build also emits `Melodex-runtime-audit.json` and
`Melodex-runtime-audit.md` for both macOS and Windows so further cuts are based
on measured payload rather than disabling features blindly.

### 8C acceptance checks

- macOS Intel, Apple Silicon and Windows frozen builds pass the runtime smoke
- plugin secret storage still discovers a usable system keyring on macOS/Windows
- NumPy-based Flow analysis remains bundled and functional
- HTTPS certificate data remains available
- no Qt changes are made in this campaign
- any further non-Qt removal must have measurable benefit and a matching feature smoke test
