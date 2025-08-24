import pygame
import random
import math

# =========================
# CONFIG & CONSTANTS
# =========================
pygame.init()

WIDTH, HEIGHT = 600, 400
GRID = 20  # size of each cell
FPS_BASE = 12  # base snake speed (frames per second)
MAX_FPS = 30

LIVES_START = 3
LEVEL_UP_EVERY = 5  # points required per level

# Power-up settings
POWERUP_CHANCE = 0.08     # chance per food eaten to spawn a power-up
POWERUP_DURATION = 4500   # ms duration of power effects
POWERUP_TTL = 9000        # ms a power-up stays on the field

# Special (bonus) food settings
SPECIAL_FOOD_EVERY = 10   # seconds between spawn attempts
SPECIAL_FOOD_TTL = 6000   # ms to live
SPECIAL_FOOD_VALUE = 5

# Obstacles
NUM_STATIC_OBSTACLES = 6
NUM_MOVING_OBSTACLES = 2

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (40, 40, 48)
MID = (70, 72, 82)
RED = (220, 68, 90)
GREEN = (40, 220, 120)
BLUE = (50, 153, 213)
GOLD = (255, 200, 60)
PURPLE = (160, 120, 255)
CYAN = (80, 240, 240)

# UI
FONT = pygame.font.SysFont("bahnschrift", 22)
FONT_BIG = pygame.font.SysFont("bahnschrift", 36)
FONT_HUGE = pygame.font.SysFont("bahnschrift", 48)

SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Snake – Deluxe")
CLOCK = pygame.time.Clock()

# Sound (optional). Leave False if you don't have files.
SOUND_ENABLED = False
SND_EAT = None
SND_POWER = None
SND_HIT = None
if SOUND_ENABLED:
    try:
        SND_EAT = pygame.mixer.Sound("eat.wav")
        SND_POWER = pygame.mixer.Sound("power.wav")
        SND_HIT = pygame.mixer.Sound("hit.wav")
    except Exception:
        SOUND_ENABLED = False

# =========================
# UTILITIES
# =========================

def grid_pos(rand=True):
    """Return a random grid-aligned position inside bounds."""
    x = random.randrange(0, WIDTH // GRID) * GRID
    y = random.randrange(0, HEIGHT // GRID) * GRID
    return [x, y]


def draw_gradient_bg():
    """Simple vertical gradient background drawn per frame (no image file)."""
    top = (18, 18, 24)
    bottom = (28, 28, 40)
    for i in range(HEIGHT):
        t = i / HEIGHT
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        pygame.draw.line(SCREEN, (r, g, b), (0, i), (WIDTH, i))


def draw_scoreboard(score, level, lives, high):
    bar_h = 36
    pygame.draw.rect(SCREEN, (22, 22, 30), (0, 0, WIDTH, bar_h))
    pygame.draw.line(SCREEN, MID, (0, bar_h), (WIDTH, bar_h), 2)

    txt = FONT.render(f"Score: {score}", True, WHITE)
    lvl = FONT.render(f"Level: {level}", True, WHITE)
    life = FONT.render("❤ " * lives, True, RED)
    hi = FONT.render(f"High: {high}", True, GOLD)

    SCREEN.blit(txt, (10, 8))
    SCREEN.blit(lvl, (150, 8))
    SCREEN.blit(hi, (WIDTH - hi.get_width() - 10, 8))
    SCREEN.blit(life, (WIDTH // 2 - life.get_width() // 2, 6))


def rounded_rect(surface, color, rect, radius=6):
    pygame.draw.rect(surface, color, rect, border_radius=radius)


# =========================
# PARTICLES (for juice)
# =========================
class Particle:
    def __init__(self, pos, vel, life, size, color):
        self.x, self.y = pos
        self.vx, self.vy = vel
        self.life = life
        self.size = size
        self.color = color
        self.age = 0

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.age += dt * 1000
        return self.age < self.life

    def draw(self, surf):
        alpha = max(0, 255 - int((self.age / self.life) * 255))
        s = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (self.size, self.size), self.size)
        surf.blit(s, (self.x - self.size, self.y - self.size))


# =========================
# POWER-UPS
# =========================
POWER_TYPES = [
    ("speed", CYAN),     # faster for a short time
    ("slow", PURPLE),    # slower for a short time
    ("bonus", GOLD),     # +3 instant points
]

class PowerUp:
    def __init__(self, kind, pos):
        self.kind = kind
        self.color = dict(POWER_TYPES)[kind]
        self.pos = pos[:]  # grid position [x, y]
        self.spawn_time = pygame.time.get_ticks()

    def alive(self):
        return pygame.time.get_ticks() - self.spawn_time < POWERUP_TTL

    def rect(self):
        return pygame.Rect(self.pos[0], self.pos[1], GRID, GRID)

    def draw(self):
        t = (pygame.time.get_ticks() // 200) % 6
        pul = 2 + t  # pulsing size
        r = pygame.Rect(self.pos[0] - pul//2, self.pos[1] - pul//2, GRID + pul, GRID + pul)
        rounded_rect(SCREEN, self.color, r, radius=8)
        inner = pygame.Rect(self.pos[0]+4, self.pos[1]+4, GRID-8, GRID-8)
        rounded_rect(SCREEN, (255, 255, 255), inner, radius=6)


# =========================
# OBSTACLES
# =========================
class MovingObstacle:
    def __init__(self, rect, dx):
        self.rect = pygame.Rect(rect)
        self.dx = dx

    def update(self):
        self.rect.x += self.dx
        if self.rect.right >= WIDTH or self.rect.left <= 0:
            self.dx *= -1

    def draw(self):
        rounded_rect(SCREEN, (90, 90, 110), self.rect, radius=6)


def make_obstacles():
    obs = []
    taken = set()

    # Static obstacles
    for _ in range(NUM_STATIC_OBSTACLES):
        while True:
            x = random.randrange(1, WIDTH // GRID - 1) * GRID
            y = random.randrange(2, HEIGHT // GRID - 1) * GRID
            if (x, y) not in taken and (WIDTH//2 - 3*GRID <= x <= WIDTH//2 + 3*GRID) is False:
                taken.add((x, y))
                w = random.choice([GRID*2, GRID*3])
                h = random.choice([GRID, GRID*2])
                obs.append(pygame.Rect(x, y, w, h))
                break

    # Moving obstacles
    mobs = []
    for _ in range(NUM_MOVING_OBSTACLES):
        y = random.randrange(3, HEIGHT // GRID - 1) * GRID
        w = GRID * random.choice([2, 3])
        rect = (GRID, y, w, GRID)
        dx = random.choice([2, 3])
        mobs.append(MovingObstacle(rect, dx))

    return obs, mobs


# =========================
# GAME STATE
# =========================
class Game:
    def __init__(self):
        self.reset_all()

    def reset_all(self):
        self.score = 0
        self.high = 0
        self.level = 1
        self.lives = LIVES_START
        self.snake = [[WIDTH // 2, HEIGHT // 2 + GRID], [WIDTH // 2, HEIGHT // 2]]
        self.dir = (0, -GRID)  # moving up
        self.next_dir = self.dir
        self.food = self.spawn_food()
        self.special_food = None
        self.special_spawned_at = 0
        self.particles = []
        self.powerups = []
        self.active_power = None  # (kind, end_time)
        self.static_obstacles, self.moving_obstacles = make_obstacles()
        self.start_time = pygame.time.get_ticks()
        self.last_special_check = pygame.time.get_ticks()
        self.tick_accum = 0
        self.alive = True
        self.paused = False

    def reset_after_hit(self):
        # Reduce life and reset snake position (keep score/level)
        self.lives -= 1
        if SOUND_ENABLED and SND_HIT:
            SND_HIT.play()
        self.snake = [[WIDTH // 2, HEIGHT // 2 + GRID], [WIDTH // 2, HEIGHT // 2]]
        self.dir = (0, -GRID)
        self.next_dir = self.dir
        self.active_power = None

    def spawn_food(self):
        while True:
            pos = grid_pos()
            # avoid obstacles & snake body
            bad = any(pygame.Rect(o).colliderect(pygame.Rect(pos[0], pos[1], GRID, GRID)) for o in self.static_obstacles) if hasattr(self, 'static_obstacles') else False
            bad |= any(m.rect.colliderect(pygame.Rect(pos[0], pos[1], GRID, GRID)) for m in getattr(self, 'moving_obstacles', []))
            if pos not in self.snake and not bad and pos[1] > GRID * 2:  # keep off the top UI bar
                return pos

    def spawn_special_food(self):
        self.special_food = self.spawn_food()
        self.special_spawned_at = pygame.time.get_ticks()

    def maybe_spawn_powerup(self):
        if random.random() < POWERUP_CHANCE:
            kind, _ = random.choice(POWER_TYPES)
            pos = self.spawn_food()
            self.powerups.append(PowerUp(kind, pos))

    def apply_power(self, kind):
        end = pygame.time.get_ticks() + POWERUP_DURATION
        if kind == "bonus":
            self.score += 3
        self.active_power = (kind, end)
        if SOUND_ENABLED and SND_POWER:
            SND_POWER.play()

    def power_multiplier(self):
        if self.active_power is None:
            return 1.0
        kind, end = self.active_power
        if pygame.time.get_ticks() > end:
            self.active_power = None
            return 1.0
        return 1.4 if kind == "speed" else (0.6 if kind == "slow" else 1.0)

    def current_fps(self):
        # level-based speed + power modifier, clamped
        base = FPS_BASE + (self.level - 1) * 1.5
        return max(6, min(MAX_FPS, int(base * self.power_multiplier())))

    def update_level(self):
        self.level = 1 + self.score // LEVEL_UP_EVERY

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_w, pygame.K_UP) and self.dir[1] == 0:
                self.next_dir = (0, -GRID)
            elif event.key in (pygame.K_s, pygame.K_DOWN) and self.dir[1] == 0:
                self.next_dir = (0, GRID)
            elif event.key in (pygame.K_a, pygame.K_LEFT) and self.dir[0] == 0:
                self.next_dir = (-GRID, 0)
            elif event.key in (pygame.K_d, pygame.K_RIGHT) and self.dir[0] == 0:
                self.next_dir = (GRID, 0)
            elif event.key == pygame.K_p:
                self.paused = not self.paused

    def move_snake(self):
        # update direction once per step
        self.dir = self.next_dir
        hx, hy = self.snake[-1]
        nx, ny = hx + self.dir[0], hy + self.dir[1]
        new_head = [nx, ny]
        self.snake.append(new_head)

    def trim_tail(self, grew=False):
        if not grew:
            self.snake.pop(0)

    def check_collisions(self):
        head = self.snake[-1]
        rect_head = pygame.Rect(head[0], head[1], GRID, GRID)
        # walls
        if head[0] < 0 or head[0] >= WIDTH or head[1] < GRID*2 or head[1] >= HEIGHT:
            return True
        # self
        if head in self.snake[:-1]:
            return True
        # obstacles
        for o in self.static_obstacles:
            if rect_head.colliderect(o):
                return True
        for m in self.moving_obstacles:
            if rect_head.colliderect(m.rect):
                return True
        return False

    def eat_food(self):
        head = self.snake[-1]
        ate = head[0] == self.food[0] and head[1] == self.food[1]
        if ate:
            self.score += 1
            self.update_level()
            self.spawn_eat_particles(self.food)
            if SOUND_ENABLED and SND_EAT:
                SND_EAT.play()
            self.food = self.spawn_food()
            self.maybe_spawn_powerup()
        return ate

    def eat_special_food(self):
        if not self.special_food:
            return False
        head = self.snake[-1]
        if head[0] == self.special_food[0] and head[1] == self.special_food[1]:
            self.score += SPECIAL_FOOD_VALUE
            self.update_level()
            self.spawn_eat_particles(self.special_food, color=GOLD)
            self.special_food = None
            return True
        return False

    def pickup_powerup(self):
        head = self.snake[-1]
        head_rect = pygame.Rect(head[0], head[1], GRID, GRID)
        for i, p in enumerate(list(self.powerups)):
            if head_rect.colliderect(p.rect()):
                self.apply_power(p.kind)
                self.spawn_eat_particles(p.pos, color=p.color)
                self.powerups.pop(i)
                return True
        return False

    def spawn_eat_particles(self, pos, color=GREEN):
        for _ in range(18):
            ang = random.random() * math.tau
            spd = random.uniform(60, 140)
            vx, vy = math.cos(ang) * spd, math.sin(ang) * spd
            self.particles.append(Particle((pos[0] + GRID/2, pos[1] + GRID/2), (vx, vy), 450, random.randint(2, 4), color))

    def update_particles(self, dt):
        self.particles = [p for p in self.particles if p.update(dt)]

    def update(self, dt):
        # moving obstacles
        for m in self.moving_obstacles:
            m.update()

        # special food spawn/expire
        now = pygame.time.get_ticks()
        if not self.special_food and now - self.last_special_check > SPECIAL_FOOD_EVERY * 1000:
            # 50% chance to spawn
            self.last_special_check = now
            if random.random() < 0.5:
                self.spawn_special_food()
        if self.special_food and now - self.special_spawned_at > SPECIAL_FOOD_TTL:
            self.special_food = None

        # clean expired powerups
        self.powerups = [p for p in self.powerups if p.alive()]

        # particles
        self.update_particles(dt)

    def draw_snake(self):
        # draw with head highlight and slight shadow
        for i, seg in enumerate(self.snake):
            x, y = seg
            shadow = pygame.Rect(x+2, y+2, GRID, GRID)
            rounded_rect(SCREEN, (0,0,0,50), shadow, radius=6)
            color = (80, 220, 140) if i < len(self.snake)-1 else (120, 255, 170)
            rounded_rect(SCREEN, color, (x, y, GRID, GRID), radius=8)

    def draw_foods(self):
        # normal food (pulsing)
        fx, fy = self.food
        t = pygame.time.get_ticks() / 200.0
        pul = int((math.sin(t) + 1) * 2)  # 0..4
        r = pygame.Rect(fx - pul//2, fy - pul//2, GRID + pul, GRID + pul)
        rounded_rect(SCREEN, GREEN, r, radius=8)

        # special food (gold)
        if self.special_food:
            sx, sy = self.special_food
            pul = int((math.sin(t*1.5) + 1) * 3)
            r2 = pygame.Rect(sx - pul//2, sy - pul//2, GRID + pul, GRID + pul)
            rounded_rect(SCREEN, GOLD, r2, radius=8)
            inner = pygame.Rect(sx+5, sy+5, GRID-10, GRID-10)
            rounded_rect(SCREEN, (255,255,255), inner, radius=6)

    def draw_powerups(self):
        for p in self.powerups:
            p.draw()

    def draw_obstacles(self):
        for o in self.static_obstacles:
            rounded_rect(SCREEN, (90, 90, 110), o, radius=6)
        for m in self.moving_obstacles:
            m.draw()


# =========================
# SCREENS
# =========================

def draw_center_text(lines):
    y = HEIGHT // 2 - (len(lines) * 28) // 2
    for text, font, color in lines:
        surf = font.render(text, True, color)
        SCREEN.blit(surf, (WIDTH // 2 - surf.get_width() // 2, y))
        y += surf.get_height() + 8


def start_screen():
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); raise SystemExit
            if e.type == pygame.KEYDOWN or e.type == pygame.MOUSEBUTTONDOWN:
                return
        draw_gradient_bg()
        title = [("S N A K E  –  D E L U X E", FONT_HUGE, WHITE),
                 ("Arrows/WASD to move •  P to Pause", FONT_BIG, (210, 210, 220)),
                 ("Avoid obstacles • Eat gold for +5 ", FONT, (200,200,210)),
                 ("Press any key to start", FONT_BIG, GREEN)]
        draw_center_text(title)
        pygame.display.flip()
        CLOCK.tick(60)


def game_over_screen(game):
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); raise SystemExit
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_r:
                    return True
                if e.key in (pygame.K_q, pygame.K_ESCAPE):
                    return False
        draw_gradient_bg()
        draw_center_text([
            ("Game Over", FONT_HUGE, RED),
            (f"Score: {game.score}   High: {game.high}", FONT_BIG, WHITE),
            ("Press R to Restart  •  Q to Quit", FONT_BIG, (210,210,220)),
        ])
        pygame.display.flip()
        CLOCK.tick(60)

def main():
    game = Game()
    start_screen()

    running = True
    step_timer = 0.0

    while running:
        dt = CLOCK.tick(60) / 1000.0
        step_timer += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            game.handle_input(event)

        if game.paused:
            # simple pause overlay
            draw_gradient_bg()
            draw_scoreboard(game.score, game.level, game.lives, game.high)
            game.draw_obstacles()
            game.draw_snake()
            game.draw_foods()
            game.draw_powerups()
            for p in game.particles:
                p.draw(SCREEN)
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0,0,0,120))
            SCREEN.blit(overlay, (0,0))
            txt = FONT_BIG.render("Paused (press P)", True, WHITE)
            SCREEN.blit(txt, (WIDTH//2 - txt.get_width()//2, HEIGHT//2 - 20))
            pygame.display.flip()
            continue

        # fixed-step logic based on current FPS target
        target_step = 1.0 / game.current_fps()
        while step_timer >= target_step:
            step_timer -= target_step

            # advance snake one cell
            game.move_snake()

            grew = False
            if game.eat_food():
                grew = True
            if game.eat_special_food():
                grew = True

            # powerup pickup
            game.pickup_powerup()

            # trim tail if not grown this step
            game.trim_tail(grew)

            # collisions
            if game.check_collisions():
                game.reset_after_hit()
                if game.lives <= 0:
                    game.high = max(game.high, game.score)
                    if not game_over_screen(game):
                        running = False
                        break
                    # restart
                    game = Game()
                    step_timer = 0
                    continue

            # update world state (obstacles, particles, timers)
            game.update(target_step)

        # RENDER
        draw_gradient_bg()
        draw_scoreboard(game.score, game.level, game.lives, max(game.high, game.score))
        game.draw_obstacles()
        game.draw_foods()
        game.draw_powerups()
        game.draw_snake()
        for p in game.particles:
            p.draw(SCREEN)

        # active power indicator
        if game.active_power:
            kind, end = game.active_power
            remain = max(0, end - pygame.time.get_ticks()) / 1000.0
            txt = FONT.render(f"{kind.upper()} {remain:0.1f}s", True, CYAN if kind=="speed" else PURPLE if kind=="slow" else GOLD)
            SCREEN.blit(txt, (WIDTH - txt.get_width() - 10, HEIGHT - txt.get_height() - 8))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
