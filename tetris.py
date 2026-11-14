#!/usr/bin/env python3
"""A polished desktop Tetris built with Pygame.

Run with::

    python3 tetris.py

The module is organised in small, focused layers:

* configuration + colour palette + tetromino data,
* rendering helpers (fonts, text, blocks, panels),
* :class:`HighScoreStore` for local JSON persistence,
* the game model (:class:`Tetromino`, :class:`Board`),
* a reusable :class:`Button` widget,
* :class:`TetrisGame`, which owns the state machine and the main loop.

Only Pygame is required; everything else is part of the standard library.
"""

from __future__ import annotations

import json
import os
import random
import sys
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

import pygame

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FPS = 60
CAPTION = "Tetris"

BLOCK_SIZE = 30
GRID_WIDTH = 10
GRID_HEIGHT = 20
BOARD_WIDTH = GRID_WIDTH * BLOCK_SIZE
BOARD_HEIGHT = GRID_HEIGHT * BLOCK_SIZE

# Desktop layout: board on the left, information sidebar on the right.
BOARD_X = 28
BOARD_Y = 24
SIDEBAR_WIDTH = 232
SIDEBAR_X = BOARD_X + BOARD_WIDTH + 24
SCREEN_WIDTH = SIDEBAR_X + SIDEBAR_WIDTH + 28
SCREEN_HEIGHT = BOARD_Y * 2 + BOARD_HEIGHT

# Input tuning (all values in milliseconds).
DAS_DELAY = 160          # hold time before horizontal auto-repeat starts
DAS_REPEAT = 45          # interval between repeated horizontal moves
SOFT_DROP_INTERVAL = 40  # interval between soft-drop steps while Down is held

LINES_PER_LEVEL = 10

# Classic line-clear scoring, multiplied by the current level.
LINE_SCORES = {0: 0, 1: 100, 2: 300, 3: 500, 4: 800}
SOFT_DROP_POINTS = 1
HARD_DROP_POINTS = 2

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

BG_TOP = (10, 16, 28)
BG_BOTTOM = (18, 26, 43)
SURFACE = (23, 32, 50)
SURFACE_HOVER = (33, 46, 70)
BOARD_BG = (13, 20, 34)
GRID_LINE = (34, 46, 67)
BORDER = (51, 65, 85)

TEXT = (232, 238, 247)
TEXT_MUTED = (139, 155, 179)
TEXT_DIM = (100, 116, 139)

ACCENT = (56, 189, 248)
ACCENT_SOFT = (14, 116, 144)
DANGER = (248, 113, 113)
GOLD = (250, 204, 21)

CYAN = (34, 211, 238)     # I piece
YELLOW = (250, 204, 21)   # O piece
PURPLE = (167, 139, 250)  # T piece
GREEN = (52, 211, 153)    # S piece
RED = (248, 113, 113)     # Z piece
BLUE = (96, 165, 250)     # J piece
ORANGE = (251, 146, 60)   # L piece

# ---------------------------------------------------------------------------
# Tetromino data (spawn orientations; clockwise rotation = transpose + flip)
# ---------------------------------------------------------------------------

SHAPES = (
    ((1, 1, 1, 1),),                  # I
    ((1, 1), (1, 1)),                 # O
    ((0, 1, 0), (1, 1, 1)),           # T
    ((0, 1, 1), (1, 1, 0)),           # S
    ((1, 1, 0), (0, 1, 1)),           # Z
    ((1, 0, 0), (1, 1, 1)),           # J
    ((0, 0, 1), (1, 1, 1)),           # L
)

SHAPE_COLORS = (CYAN, YELLOW, PURPLE, GREEN, RED, BLUE, ORANGE)
SHAPE_NAMES = ("I", "O", "T", "S", "Z", "J", "L")

# Horizontal offsets tried when a rotation would collide with a wall or stack.
WALL_KICKS = (0, -1, 1, -2, 2)


def fall_interval(level: int) -> int:
    """Milliseconds between automatic gravity steps for ``level`` (1-based)."""
    return max(60, 800 - (level - 1) * 70)


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

_FONT_CANDIDATES = ("liberationsans", "notosans", "dejavusans", "freesans", "arial")
_MONO_CANDIDATES = ("dejavusansmono", "liberationmono", "freemono", "couriernew")
_font_cache: dict[tuple[str, int, bool], pygame.font.Font] = {}


def _load_font(candidates, size: int, bold: bool, cache_key: str) -> pygame.font.Font:
    key = (cache_key, size, bold)
    if key not in _font_cache:
        font = None
        for name in candidates:
            path = pygame.font.match_font(name, bold=bold)
            if path:
                font = pygame.font.Font(path, size)
                break
        _font_cache[key] = font or pygame.font.Font(None, size)
    return _font_cache[key]


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Cached sans-serif font, with graceful fallbacks for minimal systems."""
    return _load_font(_FONT_CANDIDATES, size, bold, "sans")


def get_mono_font(size: int, bold: bool = True) -> pygame.font.Font:
    """Cached monospace font, used for numeric readouts so they stay aligned."""
    return _load_font(_MONO_CANDIDATES, size, bold, "mono")


def shade(color, factor: float):
    """Multiply a colour by ``factor``, clamping to the 0-255 range."""
    return tuple(max(0, min(255, round(channel * factor))) for channel in color)


def mix(color_a, color_b, amount: float):
    """Blend two colours: ``amount=0`` -> ``color_a``, ``amount=1`` -> ``color_b``."""
    amount = max(0.0, min(1.0, amount))
    return tuple(round(a + (b - a) * amount) for a, b in zip(color_a, color_b))


def draw_text(surface, text, font, color, *, center=None, topleft=None,
              topright=None, midtop=None, midbottom=None, shadow=False,
              shadow_color=(0, 0, 0)):
    """Blit text with optional anchoring, returning the resulting rect."""
    image = font.render(text, True, color)
    rect = image.get_rect()
    anchors = {
        "center": center,
        "topleft": topleft,
        "topright": topright,
        "midtop": midtop,
        "midbottom": midbottom,
    }
    for attribute, value in anchors.items():
        if value is not None:
            setattr(rect, attribute, value)
    if shadow:
        surface.blit(font.render(text, True, shadow_color), rect.move(0, 2))
    surface.blit(image, rect)
    return rect


def draw_block(surface, color, rect, *, radius: int = 5, ghost: bool = False):
    """Draw a single tetromino cell with a subtle bevel (or a ghost outline)."""
    rect = pygame.Rect(rect)
    if ghost:
        pygame.draw.rect(surface, shade(color, 0.30), rect, border_radius=radius)
        pygame.draw.rect(surface, mix(color, BOARD_BG, 0.35), rect, width=2,
                         border_radius=radius)
        return
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    pygame.draw.rect(surface, shade(color, 1.35),
                     (rect.x + 3, rect.y + 3, rect.width - 6, 3), border_radius=2)
    pygame.draw.rect(surface, shade(color, 0.55), rect, width=1, border_radius=radius)


def draw_panel(surface, rect, *, color=SURFACE, radius: int = 14,
               border_color=BORDER, border_width: int = 1):
    """Filled rounded panel with a thin border."""
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border_width:
        pygame.draw.rect(surface, border_color, rect, width=border_width,
                         border_radius=radius)


def make_background(size) -> pygame.Surface:
    """Pre-render a vertical gradient once; reused every frame."""
    width, height = size
    surface = pygame.Surface(size).convert()
    for y in range(height):
        color = mix(BG_TOP, BG_BOTTOM, y / max(1, height - 1))
        pygame.draw.line(surface, color, (0, y), (width, y))
    return surface


# ---------------------------------------------------------------------------
# High score persistence
# ---------------------------------------------------------------------------

MAX_SCORES = 5


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle rather than source."""
    return bool(getattr(sys, "frozen", False))


def resource_path(relative: str) -> Path:
    """Locate bundled read-only data in both source and frozen builds.

    PyInstaller unpacks data to a temporary directory stored in ``sys._MEIPASS``.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def user_data_dir() -> Path:
    """Writable per-user directory for saves (never inside the bundle)."""
    override = os.environ.get("XDG_DATA_HOME")
    base = Path(override) if override else Path.home() / ".local" / "share"
    return base / "tetris"


def default_high_score_path() -> Path:
    """Where scores live.

    A frozen executable runs from a directory that is deleted on exit, so its
    saves must go to the user's data directory. Running from source keeps the
    historical behaviour of a file next to the script.
    """
    if is_frozen():
        return user_data_dir() / "high_score.json"
    return Path(__file__).resolve().with_name("high_score.json")


DEFAULT_HIGH_SCORE_FILE = default_high_score_path()


class HighScoreStore:
    """Loads and saves the local high-score table in ``high_score.json``.

    Writes are atomic (temp file + rename) so an interrupted save can never
    corrupt an existing table. Loading is defensive: a missing, unreadable or
    malformed file simply yields an empty table instead of crashing.
    """

    def __init__(self, path: Path | str = DEFAULT_HIGH_SCORE_FILE):
        self.path = Path(path)
        self.scores: list[dict] = []
        self.load()

    # -- queries ----------------------------------------------------------
    @property
    def best(self) -> int:
        return int(self.scores[0]["score"]) if self.scores else 0

    def is_high_score(self, score: int) -> bool:
        return score > 0 and score > self.best

    # -- persistence ------------------------------------------------------
    def load(self) -> None:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            self.scores = []
            return

        raw_entries: list[dict] = []
        if isinstance(data, dict):
            entries = data.get("scores")
            if isinstance(entries, list):
                raw_entries = [entry for entry in entries if isinstance(entry, dict)]
            legacy = data.get("high_score")
            if isinstance(legacy, (int, float)) and legacy > 0:
                raw_entries.append({"score": int(legacy)})
        elif isinstance(data, (int, float)):
            raw_entries = [{"score": int(data)}]

        cleaned: list[dict] = []
        for entry in raw_entries:
            try:
                score = int(entry.get("score", 0))
                lines = int(entry.get("lines", 0))
                level = int(entry.get("level", 1))
            except (TypeError, ValueError):
                continue
            if score <= 0:
                continue
            cleaned.append({
                "score": score,
                "lines": max(0, lines),
                "level": max(1, level),
                "date": str(entry.get("date", ""))[:10],
            })

        cleaned.sort(key=lambda item: item["score"], reverse=True)
        self.scores = cleaned[:MAX_SCORES]

    def add(self, score: int, lines: int, level: int) -> int | None:
        """Record a finished run and return its 1-based rank, if it placed."""
        if score <= 0:
            return None
        entry = {
            "score": int(score),
            "lines": int(lines),
            "level": int(level),
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        self.scores.append(entry)
        self.scores.sort(key=lambda item: item["score"], reverse=True)
        self.scores = self.scores[:MAX_SCORES]

        rank = None
        for index, candidate in enumerate(self.scores):
            if candidate is entry:
                rank = index + 1
                break
        self.save()
        return rank

    def save(self) -> None:
        payload = {
            "high_score": self.best,
            "scores": self.scores,
            "updated": datetime.now().isoformat(timespec="seconds"),
        }
        temp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            # A frozen build writes into ~/.local/share/tetris, which may not
            # exist yet on a first run.
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
            os.replace(temp_path, self.path)
        except OSError:
            # Persistence is a nicety: a read-only home directory must never
            # take the game down.
            pass


# ---------------------------------------------------------------------------
# Game model
# ---------------------------------------------------------------------------


class Tetromino:
    """A single falling tetromino: kind, matrix, colour and board position."""

    def __init__(self, kind: int, x: int = 0, y: int = 0):
        self.kind = kind
        self.shape = [list(row) for row in SHAPES[kind]]
        self.color = SHAPE_COLORS[kind]
        self.x = x
        self.y = y

    @classmethod
    def spawn(cls, kind: int, width: int = GRID_WIDTH) -> "Tetromino":
        """Create ``kind`` centred horizontally at the top of the board."""
        shape = SHAPES[kind]
        return cls(kind, (width - len(shape[0])) // 2, 0)

    @property
    def name(self) -> str:
        return SHAPE_NAMES[self.kind]

    def rotated_shape(self):
        """A new matrix rotated 90 degrees clockwise."""
        return [list(row) for row in zip(*self.shape[::-1])]

    def rotated_ccw(self):
        """A new matrix rotated 90 degrees counter-clockwise."""
        return [list(column) for column in zip(*self.shape)][::-1]

    def cells(self, shape=None, x: int | None = None, y: int | None = None):
        """Yield absolute ``(column, row)`` coordinates of filled cells."""
        shape = self.shape if shape is None else shape
        origin_x = self.x if x is None else x
        origin_y = self.y if y is None else y
        for row_index, row in enumerate(shape):
            for column_index, filled in enumerate(row):
                if filled:
                    yield origin_x + column_index, origin_y + row_index


class Board:
    """The playfield: locked cells plus collision, line-clear and drop logic."""

    def __init__(self, width: int = GRID_WIDTH, height: int = GRID_HEIGHT):
        self.width = width
        self.height = height
        self.grid: list[list] = []
        self.reset()

    def reset(self) -> None:
        self.grid = [[None] * self.width for _ in range(self.height)]

    def fits(self, piece: Tetromino, dx: int = 0, dy: int = 0,
             shape=None) -> bool:
        """True when ``piece`` can occupy the offset position without collision."""
        for x, y in piece.cells(shape, piece.x + dx, piece.y + dy):
            if x < 0 or x >= self.width or y >= self.height:
                return False
            if y >= 0 and self.grid[y][x] is not None:
                return False
        return True

    def lock(self, piece: Tetromino) -> tuple[int, bool]:
        """Freeze ``piece`` into the grid.

        Returns ``(lines_cleared, topped_out)`` where ``topped_out`` is True
        when part of the piece was still above the visible playfield.
        """
        topped_out = False
        for x, y in piece.cells():
            if y < 0:
                topped_out = True
                continue
            if 0 <= x < self.width and 0 <= y < self.height:
                self.grid[y][x] = piece.color
        return self.clear_lines(), topped_out

    def clear_lines(self) -> int:
        """Remove completed rows and return how many were cleared."""
        remaining = [row for row in self.grid if any(cell is None for cell in row)]
        cleared = self.height - len(remaining)
        if cleared:
            self.grid = [[None] * self.width for _ in range(cleared)] + remaining
        return cleared

    def drop_distance(self, piece: Tetromino) -> int:
        """Number of rows ``piece`` can fall before it would collide."""
        distance = 0
        while self.fits(piece, dy=distance + 1):
            distance += 1
        return distance

    def ghost_y(self, piece: Tetromino) -> int:
        """Row where ``piece`` would rest after a hard drop."""
        return piece.y + self.drop_distance(piece)


# ---------------------------------------------------------------------------
# UI widgets
# ---------------------------------------------------------------------------


class Button:
    """A rounded, hover-aware menu button.

    Buttons are pure UI: they own a rect and an action callback, and the
    owning screen decides when to draw and hit-test them.
    """

    def __init__(self, rect, label: str, action, *, accent: bool = False,
                 font_size: int = 21):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.action = action
        self.accent = accent
        self.font = get_font(font_size, bold=True)
        self.hovered = False

    def update(self, mouse_pos) -> None:
        self.hovered = self.rect.collidepoint(mouse_pos)

    def handle_click(self, mouse_pos) -> bool:
        """Run the action if clicked; returns True when the click was consumed."""
        if self.rect.collidepoint(mouse_pos):
            self.action()
            return True
        return False

    def draw(self, surface) -> None:
        active = self.hovered
        if self.accent:
            fill = ACCENT if active else ACCENT_SOFT
            text_color = BG_TOP if active else TEXT
            border = mix(ACCENT, (255, 255, 255), 0.35) if active else ACCENT_SOFT
        else:
            fill = SURFACE_HOVER if active else SURFACE
            text_color = ACCENT if active else TEXT
            border = ACCENT if active else BORDER

        pygame.draw.rect(surface, fill, self.rect, border_radius=10)
        pygame.draw.rect(surface, border, self.rect,
                         width=2 if active else 1, border_radius=10)
        draw_text(surface, self.label, self.font, text_color,
                  center=self.rect.center)


class GameState(Enum):
    """Every screen the game can display."""

    MAIN_MENU = auto()
    PLAYING = auto()
    PAUSED = auto()
    GAME_OVER = auto()
    HIGH_SCORES = auto()


def cell_rect(column: int, row: int) -> pygame.Rect:
    """Screen rect (with a 1px gutter) for a playfield cell."""
    return pygame.Rect(
        BOARD_X + column * BLOCK_SIZE + 1,
        BOARD_Y + row * BLOCK_SIZE + 1,
        BLOCK_SIZE - 2,
        BLOCK_SIZE - 2,
    )


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------


class TetrisGame:
    """Owns the window, the state machine, input handling and rendering."""

    def __init__(self, high_score_path: Path | str = DEFAULT_HIGH_SCORE_FILE):
        pygame.init()
        pygame.display.set_caption(CAPTION)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self._apply_window_icon()
        self.clock = pygame.time.Clock()
        self.background = make_background((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.high_scores = HighScoreStore(high_score_path)

        # Runtime state ----------------------------------------------------
        self.running = True
        self.state = GameState.MAIN_MENU
        self.board = Board()
        self.score = 0
        self.lines = 0
        self.level = 1
        self.current: Tetromino | None = None
        self.next_piece: Tetromino | None = None
        self._bag: list[int] = []

        # Timers (milliseconds) -------------------------------------------
        self.fall_timer = 0
        self.soft_drop_timer = 0
        self.horizontal_dir = 0
        self.horizontal_timer = 0

        # Run summary used by the game-over screen -------------------------
        self.last_rank: int | None = None
        self.new_high_score = False

        # Buttons are built once; their callbacks are bound methods. --------
        self.menu_buttons = self._build_menu_buttons()
        self.pause_buttons = self._build_pause_buttons()
        self.game_over_buttons = self._build_game_over_buttons()
        self.high_score_buttons = self._build_high_score_buttons()

    def _apply_window_icon(self) -> None:
        """Set the taskbar/window icon; purely cosmetic, so failures are ignored."""
        try:
            icon = pygame.image.load(str(resource_path("icon.png")))
        except (pygame.error, OSError):
            return
        pygame.display.set_icon(icon)

    # -- button construction ----------------------------------------------
    def _build_menu_buttons(self) -> list[Button]:
        width, height, gap, top = 264, 56, 18, 300
        left = SCREEN_WIDTH // 2 - width // 2
        entries = (
            ("Play", self.start_game, True),
            ("High Scores", self.show_high_scores, False),
            ("Quit", self.quit_game, False),
        )
        return [
            Button((left, top + index * (height + gap), width, height),
                   label, action, accent=accent)
            for index, (label, action, accent) in enumerate(entries)
        ]

    def _build_pause_buttons(self) -> list[Button]:
        width, height, gap, top = 240, 52, 12, 258
        left = SCREEN_WIDTH // 2 - width // 2
        entries = (
            ("Resume", self.resume_game, True),
            ("Restart", self.start_game, False),
            ("Main Menu", self.return_to_menu, False),
        )
        return [
            Button((left, top + index * (height + gap), width, height),
                   label, action, accent=accent)
            for index, (label, action, accent) in enumerate(entries)
        ]

    def _build_game_over_buttons(self) -> list[Button]:
        width, height, gap, top = 280, 52, 12, 372
        left = SCREEN_WIDTH // 2 - width // 2
        entries = (
            ("Retry", self.start_game, True),
            ("Main Menu", self.return_to_menu, False),
        )
        return [
            Button((left, top + index * (height + gap), width, height),
                   label, action, accent=accent)
            for index, (label, action, accent) in enumerate(entries)
        ]

    def _build_high_score_buttons(self) -> list[Button]:
        width, height = 200, 48
        return [Button((SCREEN_WIDTH // 2 - width // 2, 472, width, height),
                       "Back", self.return_to_menu)]

    def _active_buttons(self) -> list[Button]:
        return {
            GameState.MAIN_MENU: self.menu_buttons,
            GameState.PAUSED: self.pause_buttons,
            GameState.GAME_OVER: self.game_over_buttons,
            GameState.HIGH_SCORES: self.high_score_buttons,
        }.get(self.state, [])

    # -- state transitions -------------------------------------------------
    def start_game(self) -> None:
        """Reset all run state and enter the PLAYING state."""
        self.board.reset()
        self.score = 0
        self.lines = 0
        self.level = 1
        self._bag = []
        self.last_rank = None
        self.new_high_score = False
        self.fall_timer = 0
        self.soft_drop_timer = 0
        self.horizontal_dir = 0
        self.horizontal_timer = 0
        self.next_piece = self._new_piece()
        self.current = self._new_piece()
        self.state = GameState.PLAYING

    def resume_game(self) -> None:
        if self.state is GameState.PAUSED:
            self.state = GameState.PLAYING
            self.fall_timer = 0
            self.soft_drop_timer = 0
            self.horizontal_dir = 0

    def return_to_menu(self) -> None:
        self.state = GameState.MAIN_MENU

    def show_high_scores(self) -> None:
        self.state = GameState.HIGH_SCORES

    def quit_game(self) -> None:
        self.running = False

    def _end_game(self) -> None:
        """Freeze play, persist the run and switch to the GAME_OVER screen."""
        if self.state is GameState.GAME_OVER:
            return
        # Check against the table *before* inserting this run.
        self.new_high_score = self.high_scores.is_high_score(self.score)
        self.last_rank = self.high_scores.add(self.score, self.lines, self.level)
        self.state = GameState.GAME_OVER

    # -- piece helpers -----------------------------------------------------
    def _new_piece(self) -> Tetromino:
        """Draw from a shuffled 7-bag so droughts stay short and fair."""
        if not self._bag:
            self._bag = list(range(len(SHAPES)))
            random.shuffle(self._bag)
        return Tetromino.spawn(self._bag.pop())

    def _spawn_next(self) -> None:
        """Promote the preview piece; end the run if it cannot spawn."""
        self.current = self.next_piece
        self.next_piece = self._new_piece()
        self.fall_timer = 0
        if self.current is None or not self.board.fits(self.current):
            self._end_game()

    def _move(self, dx: int) -> bool:
        if self.current and self.board.fits(self.current, dx=dx):
            self.current.x += dx
            return True
        return False

    def _step_down(self) -> bool:
        if self.current and self.board.fits(self.current, dy=1):
            self.current.y += 1
            return True
        return False

    def _rotate(self, clockwise: bool = True) -> None:
        """Rotate with simple wall kicks so rotations next to walls feel right."""
        if not self.current:
            return
        shape = (self.current.rotated_shape() if clockwise
                 else self.current.rotated_ccw())
        for offset in WALL_KICKS:
            if self.board.fits(self.current, dx=offset, shape=shape):
                self.current.shape = shape
                self.current.x += offset
                return

    def _hard_drop(self) -> None:
        if not self.current:
            return
        distance = self.board.drop_distance(self.current)
        self.current.y += distance
        self.score += distance * HARD_DROP_POINTS
        self._lock_current()

    def _lock_current(self) -> None:
        """Lock the active piece, score cleared lines, then spawn the next."""
        if not self.current:
            return
        cleared, topped_out = self.board.lock(self.current)
        if cleared:
            self.lines += cleared
            self.score += LINE_SCORES.get(cleared, 0) * self.level
            self.level = 1 + self.lines // LINES_PER_LEVEL
        self._spawn_next()
        if topped_out:
            self._end_game()

    # -- input -------------------------------------------------------------
    def handle_events(self) -> None:
        """Drain the event queue: window close, mouse and keyboard."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEMOTION:
                for button in self._active_buttons():
                    button.update(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key)

    def _handle_click(self, position) -> None:
        for button in self._active_buttons():
            if button.handle_click(position):
                return

    def _handle_key(self, key: int) -> None:
        """Route a key press according to the active screen."""
        if self.state is GameState.MAIN_MENU:
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.start_game()
            elif key == pygame.K_h:
                self.show_high_scores()
            elif key == pygame.K_q:
                self.quit_game()

        elif self.state is GameState.PLAYING:
            self._handle_playing_key(key)

        elif self.state is GameState.PAUSED:
            if key in (pygame.K_p, pygame.K_ESCAPE):
                self.resume_game()
            elif key == pygame.K_r:
                self.start_game()
            elif key == pygame.K_m:
                self.return_to_menu()

        elif self.state is GameState.GAME_OVER:
            if key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.start_game()
            elif key in (pygame.K_m, pygame.K_ESCAPE):
                self.return_to_menu()

        elif self.state is GameState.HIGH_SCORES:
            if key in (pygame.K_ESCAPE, pygame.K_h, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.return_to_menu()

    def _handle_playing_key(self, key: int) -> None:
        if key == pygame.K_LEFT:
            self._begin_horizontal(-1)
        elif key == pygame.K_RIGHT:
            self._begin_horizontal(1)
        elif key == pygame.K_DOWN:
            self.soft_drop_timer = 0
            if self._step_down():
                self.score += SOFT_DROP_POINTS
        elif key in (pygame.K_UP, pygame.K_x):
            self._rotate(clockwise=True)
        elif key == pygame.K_z:
            self._rotate(clockwise=False)
        elif key == pygame.K_SPACE:
            self._hard_drop()
        elif key in (pygame.K_p, pygame.K_ESCAPE):
            self.state = GameState.PAUSED
            self.horizontal_dir = 0
            self.horizontal_timer = 0
            self.soft_drop_timer = 0
        elif key == pygame.K_r:
            self.start_game()

    # -- update ------------------------------------------------------------
    def update(self, dt: int) -> None:
        """Advance the simulation by ``dt`` milliseconds."""
        if self.state is not GameState.PLAYING or self.current is None:
            return

        self._update_horizontal(dt)
        self._update_soft_drop(dt)

        self.fall_timer += dt
        interval = fall_interval(self.level)
        while self.fall_timer >= interval:
            self.fall_timer -= interval
            if not self._step_down():
                self._lock_current()
                break
            if self.state is not GameState.PLAYING:
                break

    def _begin_horizontal(self, direction: int) -> None:
        """Move once immediately and arm the auto-shift delay."""
        self.horizontal_dir = direction
        self.horizontal_timer = 0
        self._move(direction)

    def _update_horizontal(self, dt: int) -> None:
        """Delayed auto-shift: one tap moves once, holding repeats smoothly."""
        keys = pygame.key.get_pressed()
        direction = int(keys[pygame.K_RIGHT]) - int(keys[pygame.K_LEFT])

        if direction == 0:
            self.horizontal_dir = 0
            self.horizontal_timer = 0
            return

        if direction != self.horizontal_dir:
            # Direction changed without a fresh KEYDOWN (e.g. releasing the
            # opposite key), so restart the delay for the new direction.
            self.horizontal_dir = direction
            self.horizontal_timer = 0
            return

        self.horizontal_timer += dt
        while self.horizontal_timer >= DAS_DELAY:
            self.horizontal_timer -= DAS_REPEAT
            if not self._move(direction):
                self.horizontal_timer = 0
                break

    def _update_soft_drop(self, dt: int) -> None:
        if not pygame.key.get_pressed()[pygame.K_DOWN]:
            self.soft_drop_timer = 0
            return

        self.soft_drop_timer += dt
        while self.soft_drop_timer >= SOFT_DROP_INTERVAL:
            self.soft_drop_timer -= SOFT_DROP_INTERVAL
            if self._step_down():
                self.score += SOFT_DROP_POINTS
                self.fall_timer = 0
            else:
                self.soft_drop_timer = 0
                break

    # -- rendering ---------------------------------------------------------
    def draw(self) -> None:
        """Render the screen for the current state and present the frame."""
        self.screen.blit(self.background, (0, 0))

        if self.state in (GameState.PLAYING, GameState.PAUSED):
            self._draw_game_screen()
            if self.state is GameState.PAUSED:
                self._draw_pause_overlay()
        elif self.state is GameState.GAME_OVER:
            self._draw_game_screen()
            self._draw_game_over_overlay()
        elif self.state is GameState.MAIN_MENU:
            self._draw_main_menu()
        else:
            self._draw_high_scores()

        pygame.display.flip()

    def _draw_game_screen(self) -> None:
        self._draw_board()
        self._draw_sidebar()

    def _draw_board(self) -> None:
        frame = pygame.Rect(BOARD_X - 4, BOARD_Y - 4,
                            BOARD_WIDTH + 8, BOARD_HEIGHT + 8)
        draw_panel(self.screen, frame, color=BOARD_BG, radius=12,
                   border_color=BORDER, border_width=2)

        # Grid lines give the playfield a clean, structured look.
        for column in range(1, GRID_WIDTH):
            x = BOARD_X + column * BLOCK_SIZE
            pygame.draw.line(self.screen, GRID_LINE,
                             (x, BOARD_Y), (x, BOARD_Y + BOARD_HEIGHT))
        for row in range(1, GRID_HEIGHT):
            y = BOARD_Y + row * BLOCK_SIZE
            pygame.draw.line(self.screen, GRID_LINE,
                             (BOARD_X, y), (BOARD_X + BOARD_WIDTH, y))

        for row_index, row in enumerate(self.board.grid):
            for column_index, color in enumerate(row):
                if color is not None:
                    draw_block(self.screen, color,
                               cell_rect(column_index, row_index))

        # Ghost preview + active piece are only meaningful during play.
        if self.current and self.state in (GameState.PLAYING, GameState.PAUSED):
            ghost_row = self.board.ghost_y(self.current)
            for column, row in self.current.cells(y=ghost_row):
                if row >= 0:
                    draw_block(self.screen, self.current.color,
                               cell_rect(column, row), ghost=True)
            for column, row in self.current.cells():
                if row >= 0:
                    draw_block(self.screen, self.current.color,
                               cell_rect(column, row))

    def _draw_label(self, text: str, x: int, y: int, color=TEXT_MUTED) -> None:
        """Small letter-spaced caption used for every stat heading."""
        draw_text(self.screen, " ".join(text), get_font(12, bold=True), color,
                  topleft=(x, y))

    def _draw_sidebar(self) -> None:
        panel = pygame.Rect(SIDEBAR_X, BOARD_Y, SIDEBAR_WIDTH, BOARD_HEIGHT)
        draw_panel(self.screen, panel)

        left = SIDEBAR_X + 20
        right = SIDEBAR_X + SIDEBAR_WIDTH - 20
        top = BOARD_Y
        best = max(self.high_scores.best, self.score)

        self._draw_label("SCORE", left, top + 22)
        draw_text(self.screen, f"{self.score:,}", get_mono_font(32), TEXT,
                  topleft=(left - 2, top + 40))

        self._draw_label("BEST", left, top + 92)
        draw_text(self.screen, f"{best:,}", get_mono_font(20), GOLD,
                  topleft=(left, top + 110))

        pygame.draw.line(self.screen, BORDER, (left, top + 152),
                         (right, top + 152))

        self._draw_label("LEVEL", left, top + 170)
        draw_text(self.screen, str(self.level), get_mono_font(26), ACCENT,
                  topleft=(left - 2, top + 188))
        self._draw_label("LINES", left + 106, top + 170)
        draw_text(self.screen, str(self.lines), get_mono_font(26), TEXT,
                  topleft=(left + 104, top + 188))

        self._draw_label("NEXT", left, top + 242)
        preview = pygame.Rect(left, top + 262, SIDEBAR_WIDTH - 40, 116)
        draw_panel(self.screen, preview, color=BOARD_BG, radius=10)
        self._draw_next_piece(preview)

        self._draw_controls(left, top + 412)

    def _draw_next_piece(self, rect: pygame.Rect) -> None:
        piece = self.next_piece
        if piece is None:
            return
        cell = 24
        shape = piece.shape
        origin_x = rect.centerx - (len(shape[0]) * cell) // 2
        origin_y = rect.centery - (len(shape) * cell) // 2
        for row_index, row in enumerate(shape):
            for column_index, filled in enumerate(row):
                if filled:
                    block = pygame.Rect(
                        origin_x + column_index * cell,
                        origin_y + row_index * cell,
                        cell - 3,
                        cell - 3,
                    )
                    draw_block(self.screen, piece.color, block, radius=4)

    def _draw_controls(self, x: int, y: int) -> None:
        rows = (
            ("← →", "Move"),
            ("↑ / X", "Rotate"),
            ("↓", "Soft drop"),
            ("Space", "Hard drop"),
            ("P / R", "Pause / Restart"),
        )
        key_font = get_font(12, bold=True)
        description_font = get_font(12)
        for index, (key, description) in enumerate(rows):
            row_y = y + index * 24
            draw_text(self.screen, key, key_font, ACCENT, topleft=(x, row_y))
            draw_text(self.screen, description, description_font, TEXT_MUTED,
                      topleft=(x + 74, row_y))

    def _dim(self, alpha: int = 190) -> None:
        """Darken whatever is behind a modal overlay."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((6, 10, 20, alpha))
        self.screen.blit(overlay, (0, 0))

    def _draw_main_menu(self) -> None:
        center_x = SCREEN_WIDTH // 2

        # Title with an offset accent copy behind it for depth.
        title_font = get_font(80, bold=True)
        draw_text(self.screen, "TETRIS", title_font, mix(ACCENT, BG_TOP, 0.55),
                  center=(center_x + 4, 154))
        draw_text(self.screen, "TETRIS", title_font, TEXT, center=(center_x, 150))

        # Four accent tiles under the title.
        tile_colors = (CYAN, PURPLE, GOLD, GREEN)
        tile, gap = 20, 8
        total = len(tile_colors) * tile + (len(tile_colors) - 1) * gap
        start_x = center_x - total // 2
        for index, color in enumerate(tile_colors):
            draw_block(self.screen, color,
                       (start_x + index * (tile + gap), 206, tile, tile), radius=5)

        draw_text(self.screen, "P Y G A M E   E D I T I O N",
                  get_font(13, bold=True), TEXT_DIM, center=(center_x, 250))

        best = self.high_scores.best
        best_label = f"BEST  {best:,}" if best else "NO SCORE YET"
        draw_text(self.screen, best_label, get_mono_font(15),
                  GOLD if best else TEXT_DIM, center=(center_x, 282))

        for button in self.menu_buttons:
            button.update(pygame.mouse.get_pos())
            button.draw(self.screen)

        draw_text(self.screen,
                  "Mouse or keyboard: Enter to play · H for scores · Q to quit",
                  get_font(12), TEXT_DIM, center=(center_x, 574))
        draw_text(self.screen,
                  "← →  move     ↑  rotate     Space  hard drop     P  pause",
                  get_font(12), TEXT_DIM, center=(center_x, 600))

    def _draw_pause_overlay(self) -> None:
        self._dim(180)
        card = pygame.Rect(SCREEN_WIDTH // 2 - 170, 146, 340, 364)
        draw_panel(self.screen, card, color=SURFACE, radius=18,
                   border_color=BORDER, border_width=2)
        center_x = card.centerx

        draw_text(self.screen, "PAUSED", get_font(34, bold=True), TEXT,
                  center=(center_x, 192))
        draw_text(self.screen, f"SCORE  {self.score:,}", get_mono_font(16),
                  ACCENT, center=(center_x, 228))

        for button in self.pause_buttons:
            button.update(pygame.mouse.get_pos())
            button.draw(self.screen)

        draw_text(self.screen, "P or Esc to resume", get_font(12), TEXT_DIM,
                  center=(center_x, 470))

    def _draw_game_over_overlay(self) -> None:
        self._dim(200)
        card = pygame.Rect(SCREEN_WIDTH // 2 - 190, 110, 380, 440)
        draw_panel(self.screen, card, color=SURFACE, radius=18,
                   border_color=BORDER, border_width=2)
        center_x = card.centerx

        draw_text(self.screen, "GAME OVER", get_font(38, bold=True), DANGER,
                  center=(center_x, 156), shadow=True)
        draw_text(self.screen, "F I N A L   S C O R E", get_font(12, bold=True),
                  TEXT_MUTED, center=(center_x, 204))
        draw_text(self.screen, f"{self.score:,}", get_mono_font(40), TEXT,
                  center=(center_x, 238))

        if self.new_high_score:
            message, color = "NEW HIGH SCORE!", GOLD
        else:
            message, color = f"BEST  {self.high_scores.best:,}", TEXT_MUTED
        draw_text(self.screen, message, get_font(16, bold=True), color,
                  center=(center_x, 288))

        draw_text(self.screen, f"{self.lines} lines  ·  level {self.level}",
                  get_font(13), TEXT_DIM, center=(center_x, 316))
        if self.last_rank:
            draw_text(self.screen, f"Rank #{self.last_rank} on this machine",
                      get_font(12), TEXT_DIM, center=(center_x, 338))

        for button in self.game_over_buttons:
            button.update(pygame.mouse.get_pos())
            button.draw(self.screen)

        draw_text(self.screen, "Enter to retry · Esc for main menu",
                  get_font(12), TEXT_DIM, center=(center_x, 508))

    def _draw_high_scores(self) -> None:
        center_x = SCREEN_WIDTH // 2
        card = pygame.Rect(center_x - 210, 90, 420, 480)
        draw_panel(self.screen, card, color=SURFACE, radius=18,
                   border_color=BORDER, border_width=2)

        draw_text(self.screen, "HIGH SCORES", get_font(28, bold=True), TEXT,
                  center=(center_x, 132))
        pygame.draw.line(self.screen, BORDER, (card.x + 26, 164),
                         (card.right - 26, 164))

        headers = (
            ("RANK", card.x + 26, False),
            ("SCORE", card.x + 196, True),
            ("LINES", card.x + 292, True),
            ("LVL", card.x + 364, True),
        )
        header_font = get_font(11, bold=True)
        for label, x, right_aligned in headers:
            if right_aligned:
                draw_text(self.screen, label, header_font, TEXT_DIM,
                          topright=(x, 182))
            else:
                draw_text(self.screen, label, header_font, TEXT_DIM,
                          topleft=(x, 182))

        if not self.high_scores.scores:
            draw_text(self.screen, "No scores yet.", get_font(15), TEXT_MUTED,
                      center=(center_x, 280))
            draw_text(self.screen, "Play a game to set the first record!",
                      get_font(12), TEXT_DIM, center=(center_x, 306))
        else:
            row_font = get_mono_font(17)
            small_font = get_mono_font(14)
            for index, entry in enumerate(self.high_scores.scores):
                y = 208 + index * 44
                row_rect = pygame.Rect(card.x + 16, y - 8, card.width - 32, 36)
                if self.last_rank == index + 1:
                    pygame.draw.rect(self.screen,
                                     mix(ACCENT_SOFT, SURFACE, 0.45),
                                     row_rect, border_radius=8)
                    pygame.draw.rect(self.screen, ACCENT, row_rect, width=1,
                                     border_radius=8)
                elif index % 2 == 0:
                    pygame.draw.rect(self.screen, SURFACE_HOVER, row_rect,
                                     border_radius=8)

                rank_color = GOLD if index == 0 else TEXT_MUTED
                draw_text(self.screen, f"{index + 1:>2}", row_font, rank_color,
                          topleft=(card.x + 30, y - 2))
                draw_text(self.screen, f"{entry['score']:,}", row_font, TEXT,
                          topright=(card.x + 196, y - 2))
                draw_text(self.screen, str(entry["lines"]), small_font,
                          TEXT_MUTED, topright=(card.x + 292, y + 1))
                draw_text(self.screen, str(entry["level"]), small_font,
                          TEXT_MUTED, topright=(card.x + 364, y + 1))

        for button in self.high_score_buttons:
            button.update(pygame.mouse.get_pos())
            button.draw(self.screen)

        draw_text(self.screen, "Saved locally in high_score.json",
                  get_font(11), TEXT_DIM, center=(center_x, 544))

    # -- main loop ---------------------------------------------------------
    def run(self) -> None:
        """Run the main loop at a stable 60 FPS until the window closes."""
        while self.running:
            dt = self.clock.tick(FPS)
            self.handle_events()
            # Clamp dt so dragging/stalling the window cannot fast-forward.
            self.update(min(dt, 100))
            self.draw()


def main() -> None:
    game = TetrisGame()
    try:
        game.run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
