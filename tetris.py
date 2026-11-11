import random
import pygame

# Initialize Pygame
pygame.init()

# Global Constants
SPS = 60  # Frames per second
BLOCK_SIZE = 30
GRID_WIDTH = 10
GRID_HEIGHT = 20
SCREEN_WIDTH = BLOCK_SIZE * (GRID_WIDTH + 6)  # Extra space for sidebar
SCREEN_HEIGHT = BLOCK_SIZE * GRID_HEIGHT

# Colors (RGB)
BLACK = (15, 23, 42)      # Deep slate background
GRAY = (51, 65, 85)       # Grid lines
WHITE = (248, 250, 252)   # Text color
CYAN = (56, 189, 248)     # I piece
YELLOW = (250, 204, 21)   # O piece
PURPLE = (168, 85, 247)   # T piece
GREEN = (74, 222, 128)    # S piece
RED = (248, 113, 113)     # Z piece
BLUE = (96, 165, 250)     # J piece
ORANGE = (251, 146, 60)   # L piece

SHAPES = [
    [[1, 1, 1, 1]],                    # I
    [[1, 1], [1, 1]],                  # O
    [[0, 1, 0], [1, 1, 1]],            # T
    [[0, 1, 1], [1, 1, 0]],            # S
    [[1, 1, 0], [0, 1, 1]],            # Z
    [[1, 0, 0], [1, 1, 1]],            # J
    [[0, 0, 1], [1, 1, 1]]             # L
]

SHAPE_COLORS = [CYAN, YELLOW, PURPLE, GREEN, RED, BLUE, ORANGE]

class Tetromino:
    def __init__(self, x, y, shape_idx):
        self.x = x
        self.y = y
        self.shape_idx = shape_idx
        self.shape = SHAPES[shape_idx]
        self.color = SHAPE_COLORS[shape_idx]

    def rotate(self):
        # Transpose and reverse rows to rotate 90 degrees clockwise
        self.shape = [list(row) for row in zip(*self.shape[::-1])]

class TetrisGame:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Tetris in Python")
        self.clock = pygame.time.Clock()
        self.grid = [[BLACK for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        
        self.current_piece = self.new_piece()
        self.next_piece = self.new_piece()
        self.game_over = False
        self.score = 0
        self.lines_cleared = 0

        # Timing variables for piece falling
        self.fall_time = 0
        self.fall_speed = 400  # Milliseconds per drop (lower = faster)

    def new_piece(self):
        idx = random.randint(0, len(SHAPES) - 1)
        # Spawn near the top middle
        return Tetromino(GRID_WIDTH // 2 - len(SHAPES[idx][0]) // 2, 0, idx)

    def valid_space(self, piece, offset_x=0, offset_y=0, test_shape=None):
        shape = test_shape if test_shape else piece.shape
        for r_idx, row in enumerate(shape):
            for c_idx, cell in enumerate(row):
                if cell:
                    new_x = piece.x + c_idx + offset_x
                    new_y = piece.y + r_idx + offset_y
                    if new_x < 0 or new_x >= GRID_WIDTH or new_y >= GRID_HEIGHT:
                        return False
                    if new_y >= 0 and self.grid[new_y][new_x] != BLACK:
                        return False
        return True

    def lock_piece(self):
        for r_idx, row in enumerate(self.current_piece.shape):
            for c_idx, cell in enumerate(row):
                if cell:
                    if self.current_piece.y + r_idx < 0:
                        self.game_over = True
                        return
                    self.grid[self.current_piece.y + r_idx][self.current_piece.x + c_idx] = self.current_piece.color
        
        self.clear_lines()
        self.current_piece = self.next_piece
        self.next_piece = self.new_piece()
        if not self.valid_space(self.current_piece):
            self.game_over = True

    def clear_lines(self):
        full_rows = []
        for r_idx, row in enumerate(self.grid):
            if BLACK not in row:
                full_rows.append(r_idx)

        for r in full_rows:
            del self.grid[r]
            self.grid.insert(0, [BLACK for _ in range(GRID_WIDTH)])

        # Scoring system based on lines cleared simultaneously
        if full_rows:
            num_lines = len(full_rows)
            self.lines_cleared += num_lines
            self.score += (num_lines ** 2) * 100

    def get_ghost_y(self):
        ghost_y = self.current_piece.y
        while self.valid_space(self.current_piece, offset_y=(ghost_y - self.current_piece.y + 1)):
            ghost_y += 1
        return ghost_y

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(SPS)
            self.fall_time += dt

            # Handle player controls
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN and not self.game_over:
                    if event.key == pygame.K_LEFT:
                        if self.valid_space(self.current_piece, offset_x=-1):
                            self.current_piece.x -= 1
                    elif event.key == pygame.K_RIGHT:
                        if self.valid_space(self.current_piece, offset_x=1):
                            self.current_piece.x += 1
                    elif event.key == pygame.K_DOWN:
                        if self.valid_space(self.current_piece, offset_y=1):
                            self.current_piece.y += 1
                    elif event.key == pygame.K_UP:
                        # Rotation with wall-kick check
                        rotated = [list(row) for row in zip(*self.current_piece.shape[::-1])]
                        if self.valid_space(self.current_piece, test_shape=rotated):
                            self.current_piece.shape = rotated
                    elif event.key == pygame.K_SPACE:
                        # Hard Drop
                        while self.valid_space(self.current_piece, offset_y=1):
                            self.current_piece.y += 1
                        self.lock_piece()
                        self.fall_time = 0

                    elif event.key == pygame.K_r and self.game_over:
                        # Restart Game
                        self.__init__()

            # Automatic falling over time
            if not self.game_over and self.fall_time >= self.fall_speed:
                if self.valid_space(self.current_piece, offset_y=1):
                    self.current_piece.y += 1
                else:
                    self.lock_piece()
                self.fall_time = 0

            self.draw()

        pygame.quit()

    def draw(self):
        self.screen.fill(BLACK)

        # Draw Grid Board
        for r_idx, row in enumerate(self.grid):
            for c_idx, color in enumerate(row):
                pygame.draw.rect(self.screen, color, (c_idx * BLOCK_SIZE, r_idx * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE))
                pygame.draw.rect(self.screen, GRAY, (c_idx * BLOCK_SIZE, r_idx * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE), 1)

        # Draw Ghost Piece
        if not self.game_over:
            ghost_y = self.get_ghost_y()
            for r_idx, row in enumerate(self.current_piece.shape):
                for c_idx, cell in enumerate(row):
                    if cell:
                        gx = (self.current_piece.x + c_idx) * BLOCK_SIZE
                        gy = (ghost_y + r_idx) * BLOCK_SIZE
                        pygame.draw.rect(self.screen, (30, 41, 59), (gx, gy, BLOCK_SIZE, BLOCK_SIZE))
                        pygame.draw.rect(self.screen, GRAY, (gx, gy, BLOCK_SIZE, BLOCK_SIZE), 1)

        # Draw Active Piece
        if not self.game_over:
            for r_idx, row in enumerate(self.current_piece.shape):
                for c_idx, cell in enumerate(row):
                    if cell:
                        px = (self.current_piece.x + c_idx) * BLOCK_SIZE
                        py = (self.current_piece.y + r_idx) * BLOCK_SIZE
                        pygame.draw.rect(self.screen, self.current_piece.color, (px, py, BLOCK_SIZE, BLOCK_SIZE))
                        pygame.draw.rect(self.screen, WHITE, (px, py, BLOCK_SIZE, BLOCK_SIZE), 1)

        # Draw Sidebar UI
        sidebar_x = GRID_WIDTH * BLOCK_SIZE
        pygame.draw.line(self.screen, WHITE, (sidebar_x, 0), (sidebar_x, SCREEN_HEIGHT), 2)

        font = pygame.font.SysFont('Arial', 20, bold=True)
        score_surface = font.render(f"SCORE:", True, WHITE)
        score_val = font.render(f"{self.score}", True, CYAN)
        lines_surface = font.render(f"LINES:", True, WHITE)
        lines_val = font.render(f"{self.lines_cleared}", True, CYAN)
        next_surface = font.render(f"NEXT:", True, WHITE)

        self.screen.blit(score_surface, (sidebar_x + 20, 30))
        self.screen.blit(score_val, (sidebar_x + 20, 60))
        self.screen.blit(lines_surface, (sidebar_x + 20, 110))
        self.screen.blit(lines_val, (sidebar_x + 20, 140))
        self.screen.blit(next_surface, (sidebar_x + 20, 200))

        # Draw Next Piece Preview in Sidebar
        for r_idx, row in enumerate(self.next_piece.shape):
            for c_idx, cell in enumerate(row):
                if cell:
                    nx = sidebar_x + 20 + (c_idx * 25)
                    ny = 240 + (r_idx * 25)
                    pygame.draw.rect(self.screen, self.next_piece.color, (nx, ny, 24, 24))

        # Game Over Overlay
        if self.game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((15, 23, 42, 220))  # Dark translucent screen
            self.screen.blit(overlay, (0, 0))

            go_font = pygame.font.SysFont('Arial', 28, bold=True)
            msg1 = go_font.render("GAME OVER", True, RED)
            msg2 = font.render("Press 'R' to Restart", True, WHITE)

            self.screen.blit(msg1, (SCREEN_WIDTH // 2 - msg1.get_width() // 2, SCREEN_HEIGHT // 2 - 40))
            self.screen.blit(msg2, (SCREEN_WIDTH // 2 - msg2.get_width() // 2, SCREEN_HEIGHT // 2 + 10))

        pygame.display.flip()

if __name__ == "__main__":
    game = TetrisGame()
    game.run()
