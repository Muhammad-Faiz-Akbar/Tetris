#!/usr/bin/env bash
# Build GitHub release assets: a standalone Linux binary + a source archive.
#
# Usage:
#   ./build-release.sh            # version from `git describe`
#   ./build-release.sh v1.0.0     # explicit version label
#
# Output (in dist/):
#   tetris                 standalone one-file executable (no Python needed)
#   tetris-<version>-linux-x86_64  same binary, named for the release asset
#   tetris-<version>-source.zip    sources + launcher + installer + icon
#   SHA256SUMS.txt                 checksums for all of the above
set -euo pipefail

SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}" 2>/dev/null || printf '%s' "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd)"
cd "$SCRIPT_DIR"

VERSION="${1:-$(git describe --tags --always 2>/dev/null || echo dev)}"

if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
else
    PYTHON="$(command -v python3)"
fi

printf '==> Building Tetris %s with %s\n' "$VERSION" "$("$PYTHON" --version 2>&1)"

if ! "$PYTHON" -c 'import PyInstaller' >/dev/null 2>&1; then
    printf '==> PyInstaller missing, installing into the build environment\n'
    "$PYTHON" -m pip install --quiet --upgrade pyinstaller
fi

rm -rf build dist
mkdir -p dist

printf '==> Freezing standalone executable (this takes a moment)\n'
"$PYTHON" -m PyInstaller \
    --onefile \
    --name tetris \
    --add-data "$SCRIPT_DIR/icon.png:." \
    --distpath dist \
    --workpath build \
    --specpath build \
    --clean --noconfirm --log-level WARN \
    tetris.py

printf '==> Packaging source archive\n'
STAGE_DIR="$(mktemp -d)"
SOURCE_NAME="tetris-$VERSION"
mkdir -p "$STAGE_DIR/$SOURCE_NAME"
cp tetris.py tetris install-desktop.sh icon.png README.md requirements.txt \
    "$STAGE_DIR/$SOURCE_NAME/"
chmod +x "$STAGE_DIR/$SOURCE_NAME/tetris" "$STAGE_DIR/$SOURCE_NAME/install-desktop.sh"
( cd "$STAGE_DIR" && zip -q -r "$SCRIPT_DIR/dist/$SOURCE_NAME-source.zip" "$SOURCE_NAME" )
rm -rf "$STAGE_DIR"

mv dist/tetris "dist/tetris-$VERSION-linux-x86_64"
( cd dist && sha256sum ./* > SHA256SUMS.txt 2>/dev/null ) || true

printf '\n==> Done. Release assets in dist/:\n'
ls -lh dist
printf '\nChecksums:\n'
cat dist/SHA256SUMS.txt
