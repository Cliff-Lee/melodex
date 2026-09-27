#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python3 -m venv .venv-build
source .venv-build/bin/activate

python -m pip install --upgrade pip
pip install -r requirements-build.txt

rm -rf build dist AppDir
pyinstaller \
  --noconfirm \
  --windowed \
  --name Melodex \
  --icon ../assets/icon.png \
  --add-data "melodex/assets/melodex-mark.png:melodex/assets" --add-data "melodex/bundled_providers:melodex/bundled_providers" \
  --collect-all PySide6 \
  run.py

mkdir -p AppDir/usr/lib/melodex
cp -R dist/Melodex/* AppDir/usr/lib/melodex/

cat > AppDir/AppRun <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/melodex/Melodex" "$@"
EOF
chmod +x AppDir/AppRun

cat > AppDir/Melodex.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Melodex
Comment=Source-neutral music player with Flow
Exec=Melodex
Icon=melodex
Categories=Audio;AudioVideo;Player;
Terminal=false
EOF

cp ../assets/icon.png AppDir/melodex.png

curl -L \
  -o appimagetool-x86_64.AppImage \
  https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage

chmod +x appimagetool-x86_64.AppImage

ARCH=x86_64 \
APPIMAGE_EXTRACT_AND_RUN=1 \
./appimagetool-x86_64.AppImage \
  AppDir \
  dist/Melodex-Linux-x86_64.AppImage

chmod +x dist/Melodex-Linux-x86_64.AppImage

echo
echo "Built:"
ls -lh dist/Melodex-Linux-x86_64.AppImage
