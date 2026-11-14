#!/usr/bin/env bash
# Register Tetris in the desktop application menu (per-user, no sudo needed).
#
# Creates ~/.local/share/applications/tetris.desktop pointing at this checkout,
# and installs icon.png into the hicolor icon theme.
set -euo pipefail

SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}" 2>/dev/null || printf '%s' "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd)"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"

# Sandboxed editors (e.g. the VS Code Flatpak) override XDG_DATA_HOME to a
# private path under ~/.var/app, which the host desktop never reads. Fall back
# to the real home so the menu entry actually shows up on CachyOS.
case "$DATA_HOME" in
    */.var/app/*)
        printf 'note: ignoring sandboxed XDG_DATA_HOME=%s\n' "$DATA_HOME"
        printf '      installing to the host location instead.\n'
        DATA_HOME="$HOME/.local/share"
        ;;
esac

APPS_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/256x256/apps"
DESKTOP_FILE="$APPS_DIR/tetris.desktop"

chmod +x "$SCRIPT_DIR/tetris"
mkdir -p "$APPS_DIR" "$ICON_DIR"
install -m 644 "$SCRIPT_DIR/icon.png" "$ICON_DIR/tetris.png"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Tetris
GenericName=Block Puzzle Game
Comment=A polished desktop Tetris built with Pygame
Exec=$SCRIPT_DIR/tetris
Icon=tetris
Terminal=false
Categories=Game;ArcadeGame;
Keywords=tetris;game;puzzle;blocks;
StartupNotify=true
EOF
chmod +x "$DESKTOP_FILE"

# Refresh caches when the helper tools are installed; not fatal if missing.
command -v update-desktop-database >/dev/null 2>&1 &&
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 &&
    gtk-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true

printf 'Installed launcher: %s\n' "$DESKTOP_FILE"
printf 'Installed icon:     %s\n' "$ICON_DIR/tetris.png"
printf '\nTetris should now appear in your application menu.\n'
printf 'To remove it later: rm "%s"\n' "$DESKTOP_FILE"
