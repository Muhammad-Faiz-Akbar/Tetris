# 🧱 Python Tetris

A polished desktop Tetris built with Pygame, designed to run natively on
Linux (tested on CachyOS / Arch).

## ✨ Features

- **Full screen flow:** Main Menu → Playing → Paused → Game Over, plus a
  persistent High Scores table.
- **Interactive menus:** mouse-driven buttons with hover states, and matching
  keyboard shortcuts for everything.
- **Difficulty scaling:** gravity speeds up every 10 lines, and the level
  multiplier applies to line-clear scores.
- **Local high scores:** the top 5 runs are saved to `high_score.json` next to
  the script (atomic writes, corruption-safe loading).
- **Comfort features:** 7-bag randomiser, ghost piece, wall kicks, hard drop,
  soft-drop scoring, delayed auto-shift for smooth horizontal movement.
- **Clean visuals:** gradient background, rounded blocks, grid borders,
  monospaced score readouts and a well-aligned sidebar layout.

## 🚀 Setup

```bash
cd tetris
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python tetris.py
```

Requires Python 3.10+ and Pygame 2.5+. On CachyOS/Arch you can also use the
system package instead of a venv: `sudo pacman -S python-pygame`.

## 🖱 Running it like a real app

The repo ships a `tetris` launcher (a self-locating shell script) so you don't
need to activate a virtualenv or remember paths:

```bash
./tetris                # from the project folder
```

It prefers `.venv/bin/python` when present and otherwise falls back to system
`python3`, and prints install instructions if Pygame is missing.

To add a **Tetris** entry with an icon to your CachyOS application menu:

```bash
./install-desktop.sh
```

That writes `~/.local/share/applications/tetris.desktop` plus the icon into the
hicolor theme (no `sudo` needed). Remove it later with:

```bash
rm ~/.local/share/applications/tetris.desktop
```

## 🎮 Controls

| Action | Keys |
| --- | --- |
| Move left / right | `←` / `→` (hold to auto-repeat) |
| Soft drop | `↓` (hold) |
| Rotate clockwise | `↑` or `X` |
| Rotate counter-clockwise | `Z` |
| Hard drop | `Space` |
| Pause / resume | `P` or `Esc` |
| Restart | `R` |
| Menu navigation | Mouse click, or `Enter` / `H` / `Q` |

## 📺 Gameplay

![Tetris Gameplay](tetris.gif)

## 🗂 Project layout

| File | Purpose |
| --- | --- |
| `tetris.py` | The game (single modular file) |
| `tetris` | Launcher script — `./tetris` |
| `install-desktop.sh` | Adds a menu entry + icon to your desktop |
| `icon.png` | Application icon (256×256) |
| `requirements.txt` | Pygame dependency |

`tetris.py` is intentionally a single, modular file:

- configuration constants, palette and tetromino data
- rendering helpers (fonts, text, blocks, panels, gradient background)
- `HighScoreStore` — JSON persistence
- `Tetromino` / `Board` — game model
- `Button` — reusable hover-aware widget
- `TetrisGame` — state machine, input, update and rendering
