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
