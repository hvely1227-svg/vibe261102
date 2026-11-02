"""
AERO STRIKE - pygame 종스크롤 슈팅 게임

공중 적은 샷으로, 지상 적은 폭탄으로 공격하는 종스크롤 슈팅입니다.
그래픽과 효과음은 모두 코드로 만들므로 별도의 이미지/사운드 파일이 필요 없습니다.
P 아이템을 먹을 때마다 샷이 2 → 4 → 8 → 16발로 강화됩니다.

조작:
  방향키 / WASD : 이동
  Z / Space     : 공중 공격(샷) - 누르고 있으면 연사
  X             : 지상 공격(폭탄) - 기체 앞의 조준점에 떨어짐
  P             : 일시정지
  ESC           : 종료

실행:
  pip install pygame
  python shooting.py
"""
import math
import random
import sys
from array import array

import pygame

WIDTH, HEIGHT = 480, 640
FPS = 60
TILE = 32
SCROLL_SPEED = 1.2
BOMB_RANGE = 150  # 기체에서 조준점까지의 거리
MAX_SHOT_LEVEL = 4  # 레벨 n에서 2**n발 (2, 4, 8, 16)

GRASS, FOREST, WATER, SAND, ROAD = range(5)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def dist2(ax, ay, bx, by):
    return (ax - bx) ** 2 + (ay - by) ** 2


def load_font(size):
    # 한글 출력을 위해 시스템의 한글 폰트를 우선 사용
    for name in ("malgungothic", "applegothic", "nanumgothic", "notosanscjkkr"):
        path = pygame.font.match_font(name)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size + 6)


# ---------------------------------------------------------------- 배경 지형
def make_tile(kind, variant):
    s = pygame.Surface((TILE, TILE))
    rnd = random.Random(kind * 31 + variant * 7)
    if kind == GRASS:
        s.fill((62, 128, 58))
        for _ in range(16):
            s.set_at((rnd.randrange(TILE), rnd.randrange(TILE)), (86, 156, 74))
        for _ in range(6):
            s.set_at((rnd.randrange(TILE), rnd.randrange(TILE)), (44, 100, 44))
    elif kind == FOREST:
        s.fill((40, 96, 44))
        for _ in range(4):
            x, y = rnd.randrange(5, TILE - 5), rnd.randrange(5, TILE - 5)
            pygame.draw.circle(s, (26, 68, 32), (x + 2, y + 3), 7)
            pygame.draw.circle(s, (54, 122, 58), (x, y), 6)
            pygame.draw.circle(s, (74, 146, 70), (x - 2, y - 2), 2)
    elif kind == WATER:
        s.fill((40, 90, 170))
        for y in range(4 + variant * 3, TILE, 10):
            x0 = rnd.randrange(0, 12)
            pygame.draw.line(s, (76, 134, 214), (x0, y), (x0 + rnd.randrange(8, 18), y), 1)
    elif kind == SAND:
        s.fill((196, 180, 120))
        for _ in range(12):
            s.set_at((rnd.randrange(TILE), rnd.randrange(TILE)), (170, 152, 98))
    elif kind == ROAD:
        s.fill((104, 104, 108))
        pygame.draw.line(s, (70, 70, 74), (0, 2), (TILE, 2), 2)
        pygame.draw.line(s, (70, 70, 74), (0, TILE - 3), (TILE, TILE - 3), 2)
        pygame.draw.line(s, (220, 206, 110), (4, TILE // 2), (TILE - 12, TILE // 2), 2)
    return s


class Terrain:
    def __init__(self):
        self.cols = WIDTH // TILE
        self.rows = HEIGHT // TILE + 2
        self.tiles = {k: [make_tile(k, v) for v in range(3)]
                      for k in (GRASS, FOREST, WATER, SAND, ROAD)}
        self.reset()

    def reset(self):
        self.river_x = self.cols / 2
        self.river_w = 3.0
        self.n = 0
        self.road_cd = 12
        self.offset = 0.0
        self.grid = [self._gen_row() for _ in range(self.rows)]

    def _gen_row(self):
        self.n += 1
        self.river_x = clamp(self.river_x + random.uniform(-0.5, 0.5), 2, self.cols - 3)
        self.river_w = clamp(self.river_w + random.uniform(-0.25, 0.25), 1.2, 4.5)
        self.road_cd -= 1
        is_road = self.road_cd <= 0
        if is_road:
            self.road_cd = random.randint(14, 30)
        row = []
        for c in range(self.cols):
            d = abs(c + 0.5 - self.river_x)
            if is_road:
                kind = ROAD  # 강 위에서는 다리
            elif d < self.river_w / 2:
                kind = WATER
            elif d < self.river_w / 2 + 0.9:
                kind = SAND
            else:
                f = math.sin(c * 0.55 + self.n * 0.21) + math.sin(c * 0.23 - self.n * 0.13 + 1.7)
                kind = FOREST if f > 0.9 else GRASS
            row.append((kind, random.randrange(3)))
        return row

    def update(self, speed):
        self.offset += speed
        while self.offset >= TILE:
            self.offset -= TILE
            self.grid.pop()
            self.grid.insert(0, self._gen_row())

    def top_row(self):
        """화면 위쪽(막 생성된) 행의 타일 목록과 그 행 중심의 y좌표."""
        return self.grid[0], -TILE + self.offset + TILE / 2

    def draw(self, surf):
        for r, row in enumerate(self.grid):
            y = (r - 1) * TILE + self.offset
            for c, (kind, var) in enumerate(row):
                surf.blit(self.tiles[kind][var], (c * TILE, y))


# ---------------------------------------------------------------- 이펙트
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size")

    def __init__(self, x, y, color, speed=3.0, size=3):
        a = random.uniform(0, math.tau)
        s = random.uniform(0.5, speed)
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(a) * s, math.sin(a) * s
        self.life = self.max_life = random.randint(20, 40)
        self.color = color
        self.size = size

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.94
        self.vy *= 0.94
        self.life -= 1

    def draw(self, surf):
        r = max(1, int(self.size * self.life / self.max_life))
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), r)


class Ring:
    def __init__(self, x, y, max_r):
        self.x, self.y = x, y
        self.r = 2
        self.max_r = max_r

    def update(self):
        self.r += (self.max_r - self.r) * 0.2 + 0.5

    @property
    def dead(self):
        return self.r >= self.max_r

    def draw(self, surf):
        w = max(1, int(4 * (1 - self.r / self.max_r)))
        pygame.draw.circle(surf, (255, 240, 200), (int(self.x), int(self.y)), int(self.r), w)


# ---------------------------------------------------------------- 플레이어 / 탄
class Player:
    def __init__(self):
        self.x, self.y = WIDTH / 2, HEIGHT - 90
        self.speed = 4.2
        self.radius = 5  # 피격 판정은 작게
        self.cooldown = 0
        self.invincible = 120
        self.tilt = 0.0

    def update(self, keys):
        dx = int(keys[pygame.K_RIGHT] or keys[pygame.K_d]) - int(keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = int(keys[pygame.K_DOWN] or keys[pygame.K_s]) - int(keys[pygame.K_UP] or keys[pygame.K_w])
        k = 0.7071 if dx and dy else 1.0
        self.x = clamp(self.x + dx * self.speed * k, 16, WIDTH - 16)
        self.y = clamp(self.y + dy * self.speed * k, 40, HEIGHT - 24)
        self.tilt += (dx - self.tilt) * 0.2
        if self.cooldown > 0:
            self.cooldown -= 1
        if self.invincible > 0:
            self.invincible -= 1

    def draw(self, surf, frame):
        if self.invincible > 0 and (frame // 4) % 2:
            return
        x, y = self.x, self.y
        w = 16 * (1 - abs(self.tilt) * 0.35)
        fl = random.randint(6, 12)
        pygame.draw.polygon(surf, (255, 160, 40), [(x - 4, y + 12), (x + 4, y + 12), (x, y + 12 + fl)])
        pygame.draw.polygon(surf, (255, 240, 160), [(x - 2, y + 12), (x + 2, y + 12), (x, y + 8 + fl)])
        pygame.draw.polygon(surf, (140, 152, 176),
                            [(x, y - 6), (x + w, y + 8), (x + w, y + 14), (x, y + 8),
                             (x - w, y + 14), (x - w, y + 8)])
        pygame.draw.polygon(surf, (232, 236, 246),
                            [(x, y - 18), (x + 6, y + 4), (x + 4, y + 14), (x - 4, y + 14), (x - 6, y + 4)])
        pygame.draw.polygon(surf, (60, 140, 230), [(x, y - 10), (x + 3, y - 2), (x - 3, y - 2)])
        pygame.draw.line(surf, (220, 60, 60), (x - w + 2, y + 10), (x - w + 6, y + 10), 2)
        pygame.draw.line(surf, (220, 60, 60), (x + w - 6, y + 10), (x + w - 2, y + 10), 2)


class Bullet:
    def __init__(self, x, y, vx, vy, radius=4, color=(255, 120, 200), player=False):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.radius = radius
        self.color = color
        self.player = player
        self.dead = False

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if self.x < -20 or self.x > WIDTH + 20 or self.y < -20 or self.y > HEIGHT + 20:
            self.dead = True

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        if self.player:
            pygame.draw.rect(surf, (255, 220, 90), (x - 2, y - 8, 4, 14), border_radius=2)
            pygame.draw.rect(surf, (255, 255, 230), (x - 1, y - 7, 2, 10))
        else:
            pygame.draw.circle(surf, self.color, (x, y), self.radius)
            pygame.draw.circle(surf, (255, 255, 255), (x, y), max(1, self.radius - 2))


class Bomb:
    """기체에서 조준점으로 떨어지는 폭탄. 조준점은 지면과 함께 스크롤된다."""

    def __init__(self, x, y):
        self.sx, self.sy = x, y
        self.tx, self.ty = x, y - BOMB_RANGE
        self.x, self.y = x, y
        self.t = 0
        self.duration = 30

    @property
    def landed(self):
        return self.t >= self.duration

    def update(self):
        self.t += 1
        self.ty += SCROLL_SPEED
        k = self.t / self.duration
        self.x = self.sx + (self.tx - self.sx) * k
        self.y = self.sy + (self.ty - self.sy) * k

    def draw(self, surf):
        r = max(2, int(6 * (1 - self.t / self.duration)) + 2)
        pygame.draw.circle(surf, (40, 40, 40), (int(self.x), int(self.y)), r + 1)
        pygame.draw.circle(surf, (255, 200, 60), (int(self.x), int(self.y)), r)


class Item:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.t = 0
        self.dead = False

    def update(self):
        self.t += 1
        self.y += 1.4
        self.x += math.sin(self.t * 0.08) * 0.8
        if self.y > HEIGHT + 20:
            self.dead = True

    def draw(self, surf, font):
        x, y = int(self.x), int(self.y)
        c = (255, 220, 60) if (self.t // 6) % 2 else (255, 140, 40)
        pygame.draw.circle(surf, c, (x, y), 11)
        pygame.draw.circle(surf, (255, 255, 255), (x, y), 11, 2)
        txt = font.render("P", True, (120, 30, 0))
        surf.blit(txt, txt.get_rect(center=(x, y)))


# ---------------------------------------------------------------- 적
class AirEnemy:
    ground = False
    # 체력, 반지름, 점수
    STATS = {"spinner": (1, 12, 100), "weaver": (2, 13, 150), "hunter": (6, 16, 400)}

    def __init__(self, kind, x, y):
        self.kind = kind
        self.x, self.y = x, y
        self.base_x = x
        self.hp, self.radius, self.score = self.STATS[kind]
        self.vx, self.vy = 0.0, 0.0
        self.t = 0
        self.fire_cd = random.randint(50, 130)
        self.flash = 0
        self.dead = False

    def update(self, game):
        self.t += 1
        p = game.player
        if self.kind == "spinner":
            # 내려오다가 플레이어 반대쪽으로 꺾어 위로 빠져나간다
            if self.t < 45:
                self.y += 3.6
            else:
                self.vx += 0.3 if self.x >= p.x else -0.3
                self.vy -= 0.1
                self.x += self.vx
                self.y += 3.6 + self.vy
        elif self.kind == "weaver":
            self.y += 2.0
            self.x = self.base_x + math.sin(self.t * 0.05) * 70
        else:  # hunter: 내려와 머물며 쏘다가 아래로 이탈
            leaving = self.t > 420
            target_y = HEIGHT + 100 if leaving else 150
            self.y += clamp(target_y - self.y, -2, 4 if leaving else 2)
            self.x += clamp(p.x - self.x, -1.2, 1.2)

        self.fire_cd -= 1
        if self.fire_cd <= 0 and 0 < self.y < HEIGHT - 160:
            speed = 3.0 + game.difficulty * 0.3
            if self.kind == "hunter":
                game.fire_spread(self.x, self.y + 10, 3, 0.25, speed)
                self.fire_cd = random.randint(45, 70)
            else:
                game.fire_at(self.x, self.y, speed)
                self.fire_cd = random.randint(80, 160)
        if self.flash:
            self.flash -= 1
        if (self.y > HEIGHT + 50 or (self.t > 60 and self.y < -60)
                or self.x < -60 or self.x > WIDTH + 60):
            self.dead = True

    def draw(self, surf, frame):
        x, y = self.x, self.y
        white = self.flash > 0
        if self.kind == "spinner":
            a = self.t * 0.2
            pts = [(x + math.cos(a + i * math.pi / 2) * 13, y + math.sin(a + i * math.pi / 2) * 13)
                   for i in range(4)]
            pygame.draw.polygon(surf, (255, 255, 255) if white else (190, 196, 210), pts)
            pygame.draw.polygon(surf, (90, 96, 110), pts, 2)
            pygame.draw.circle(surf, (230, 60, 60), (int(x), int(y)), 5)
        elif self.kind == "weaver":
            body = (255, 255, 255) if white else (210, 120, 60)
            pygame.draw.polygon(surf, body, [(x - 14, y - 10), (x + 14, y - 10), (x, y + 14)])
            pygame.draw.polygon(surf, (120, 60, 30), [(x - 14, y - 10), (x + 14, y - 10), (x, y + 14)], 2)
            pygame.draw.circle(surf, (255, 230, 120), (int(x), int(y - 2)), 4)
        else:
            body = (255, 255, 255) if white else (110, 70, 160)
            pygame.draw.polygon(surf, body, [(x - 22, y - 8), (x - 6, y - 14), (x + 6, y - 14),
                                             (x + 22, y - 8), (x + 10, y + 6), (x, y + 18), (x - 10, y + 6)])
            pygame.draw.polygon(surf, (60, 30, 90), [(x - 22, y - 8), (x - 6, y - 14), (x + 6, y - 14),
                                                     (x + 22, y - 8), (x + 10, y + 6), (x, y + 18),
                                                     (x - 10, y + 6)], 2)
            c = (255, 80, 80) if (frame // 10) % 2 else (255, 200, 80)
            pygame.draw.circle(surf, c, (int(x), int(y)), 5)


class GroundEnemy:
    ground = True
    # 점수, 반지름
    STATS = {"turret": (150, 12), "tank": (250, 12), "bunker": (600, 18)}

    def __init__(self, kind, x, y):
        self.kind = kind
        self.x, self.y = x, y
        self.score, self.radius = self.STATS[kind]
        self.vx = random.choice((-0.6, 0.6)) if kind == "tank" else 0.0
        self.angle = math.pi / 2
        self.fire_cd = random.randint(50, 130)
        self.t = 0
        self.dead = False

    def update(self, game):
        self.t += 1
        self.y += SCROLL_SPEED
        self.x += self.vx
        if self.x < 20 or self.x > WIDTH - 20:
            self.vx = -self.vx
        p = game.player
        self.angle = math.atan2(p.y - self.y, p.x - self.x)
        if self.kind != "bunker":
            self.fire_cd -= 1
            if self.fire_cd <= 0 and 20 < self.y < p.y - 80:
                game.fire_at(self.x + math.cos(self.angle) * 14, self.y + math.sin(self.angle) * 14,
                             2.6 + game.difficulty * 0.3)
                self.fire_cd = random.randint(90, 170)
        if self.y > HEIGHT + 40:
            self.dead = True

    def draw(self, surf, frame):
        x, y = int(self.x), int(self.y)
        bx, by = x + math.cos(self.angle) * 15, y + math.sin(self.angle) * 15
        if self.kind == "turret":
            pts = [(x + math.cos(i * math.pi / 4 + math.pi / 8) * 13,
                    y + math.sin(i * math.pi / 4 + math.pi / 8) * 13) for i in range(8)]
            pygame.draw.polygon(surf, (90, 92, 96), pts)
            pygame.draw.polygon(surf, (50, 50, 54), pts, 2)
            pygame.draw.line(surf, (40, 40, 44), (x, y), (bx, by), 4)
            pygame.draw.circle(surf, (150, 150, 160), (x, y), 7)
        elif self.kind == "tank":
            pygame.draw.rect(surf, (40, 44, 36), (x - 13, y - 11, 26, 22), border_radius=3)
            pygame.draw.rect(surf, (96, 110, 70), (x - 10, y - 9, 20, 18), border_radius=2)
            pygame.draw.line(surf, (30, 34, 28), (x, y), (bx, by), 4)
            pygame.draw.circle(surf, (120, 136, 90), (x, y), 6)
        else:
            pygame.draw.circle(surf, (70, 70, 76), (x, y), 20)
            pygame.draw.circle(surf, (150, 150, 160), (x, y), 16)
            pygame.draw.line(surf, (90, 90, 100), (x - 16, y), (x + 16, y), 2)
            pygame.draw.line(surf, (90, 90, 100), (x, y - 16), (x, y + 16), 2)
            c = (255, 60, 60) if (frame // 15) % 2 else (120, 20, 20)
            pygame.draw.circle(surf, c, (x, y), 5)


class Boss:
    ground = False

    def __init__(self, level):
        self.level = level
        self.x, self.y = WIDTH / 2, -120
        self.max_hp = self.hp = 150 + 60 * level  # 16발 샷을 고려한 체력
        self.radius = 48
        self.score = 5000 * level
        self.t = 0
        self.flash = 0
        self.dead = False

    def update(self, game):
        self.t += 1
        if self.y < 130:
            self.y += 1.2
        else:
            self.x = WIDTH / 2 + math.sin(self.t * 0.012) * 130
        if self.flash:
            self.flash -= 1
        if self.y < 100:
            return
        t = self.t
        speed = 2.6 + self.level * 0.3
        if t % 100 == 0:
            game.fire_ring(self.x, self.y, 14 + self.level * 2, speed, t * 0.05)
        if t % 40 == 0:
            game.fire_spread(self.x, self.y + 30, 3 + self.level // 2 * 2, 0.22, speed + 1)
        if (t // 240) % 2 == 1 and t % 7 == 0:
            a = t * 0.13
            for k in (0, math.pi):
                game.enemy_bullets.append(Bullet(self.x, self.y, math.cos(a + k) * speed,
                                                 math.sin(a + k) * speed, color=(120, 200, 255)))

    def draw(self, surf, frame):
        x, y = self.x, self.y
        hull = [(x + math.cos(i * math.pi / 4 + math.pi / 8) * 62,
                 y + math.sin(i * math.pi / 4 + math.pi / 8) * 46) for i in range(8)]
        pygame.draw.polygon(surf, (200, 200, 210) if self.flash else (84, 88, 104), hull)
        pygame.draw.polygon(surf, (40, 42, 52), hull, 3)
        pygame.draw.rect(surf, (60, 64, 78), (x - 80, y - 8, 160, 16), border_radius=4)
        for side in (-1, 1):
            pygame.draw.circle(surf, (110, 114, 130), (int(x + side * 78), int(y)), 12)
            pygame.draw.circle(surf, (40, 42, 52), (int(x + side * 78), int(y)), 12, 2)
        for i in range(8):
            a = self.t * 0.04 + i * math.pi / 4
            lx, ly = x + math.cos(a) * 36, y + math.sin(a) * 26
            c = (255, 220, 80) if (i + frame // 8) % 2 else (120, 90, 30)
            pygame.draw.circle(surf, c, (int(lx), int(ly)), 4)
        pulse = 14 + int(math.sin(self.t * 0.15) * 3)
        pygame.draw.circle(surf, (120, 20, 30), (int(x), int(y)), pulse + 4)
        pygame.draw.circle(surf, (255, 70, 70), (int(x), int(y)), pulse)
        pygame.draw.circle(surf, (255, 200, 200), (int(x - 4), int(y - 4)), 4)


# ---------------------------------------------------------------- 효과음
class SoundFX:
    """효과음을 실행 시점에 직접 합성한다. 오디오 장치가 없으면 소리 없이 동작."""

    def __init__(self):
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            self.rate, _, self.channels = pygame.mixer.get_init()
            pygame.mixer.set_num_channels(24)
        except pygame.error:
            return
        self.sounds = {
            "shot": self.synth([(0.05, 1200, 500)], "square", 0.10),
            "bomb": self.synth([(0.25, 1000, 300)], "sine", 0.25),
            "explode": self.synth([(0.35, 1400, 120)], "noise", 0.45),
            "big_explode": self.synth([(1.0, 700, 40)], "noise", 0.65),
            "hit": self.synth([(0.7, 2200, 60)], "noise", 0.6),
            "item": self.synth([(0.06, 523, 523), (0.06, 659, 659),
                                (0.06, 784, 784), (0.14, 1047, 1047)], "square", 0.2, decay=False),
            "warning": self.synth([(0.18, 440, 440), (0.18, 330, 330)] * 3, "square", 0.18, decay=False),
        }

    def synth(self, parts, wave, vol, decay=True):
        """parts: (길이(초), 시작 주파수, 끝 주파수) 목록을 이어 붙인 소리를 만든다."""
        buf = array("h")
        rnd = random.Random(1)
        noise_val = 0.0
        for dur, f0, f1 in parts:
            n = int(self.rate * dur)
            phase = 0.0
            for i in range(n):
                t = i / n
                prev = phase
                phase += (f0 + (f1 - f0) * t) / self.rate
                if wave == "square":
                    v = 1.0 if phase % 1 < 0.5 else -1.0
                elif wave == "sine":
                    v = math.sin(math.tau * phase)
                else:  # 주파수에 맞춰 값이 바뀌는 노이즈 -> 낮을수록 묵직한 폭발음
                    if int(phase) != int(prev):
                        noise_val = rnd.uniform(-1, 1)
                    v = noise_val
                env = (1 - t) ** 2 if decay else min(1.0, (1 - t) * 8)
                env *= min(1.0, i / (self.rate * 0.003) + 0.01)
                s = int(clamp(v * env * vol, -1, 1) * 32767)
                for _ in range(self.channels):
                    buf.append(s)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, name):
        snd = self.sounds.get(name)
        if snd:
            snd.play()


# ---------------------------------------------------------------- 게임
class Game:
    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        self.sfx = SoundFX()
        pygame.display.set_caption("AERO STRIKE - 종스크롤 슈팅")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.shadow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.clock = pygame.time.Clock()
        self.font_big = load_font(44)
        self.font = load_font(20)
        self.font_small = load_font(15)
        self.terrain = Terrain()
        self.high_score = 0
        self.state = "title"
        self.reset()

    def reset(self):
        self.terrain.reset()
        self.player = Player()
        self.bullets = []
        self.enemy_bullets = []
        self.air = []
        self.ground = []
        self.items = []
        self.particles = []
        self.rings = []
        self.craters = []
        self.delayed_explosions = []
        self.bomb = None
        self.boss = None
        self.boss_count = 0
        self.next_boss = 60 * 50
        self.warning = 0
        self.score = 0
        self.lives = 3
        self.shot_level = 1
        self.frame = 0
        self.shake = 0
        self.gameover_timer = 0
        self.paused = False

    @property
    def difficulty(self):
        return 1 + self.frame / (60 * 45) + self.boss_count * 0.5

    # --- 탄 발사 도우미
    def fire_at(self, x, y, speed):
        a = math.atan2(self.player.y - y, self.player.x - x)
        self.enemy_bullets.append(Bullet(x, y, math.cos(a) * speed, math.sin(a) * speed))

    def fire_spread(self, x, y, n, spread, speed):
        base = math.atan2(self.player.y - y, self.player.x - x)
        for i in range(n):
            a = base + (i - (n - 1) / 2) * spread
            self.enemy_bullets.append(Bullet(x, y, math.cos(a) * speed, math.sin(a) * speed,
                                             color=(255, 160, 60)))

    def fire_ring(self, x, y, n, speed, offset=0.0):
        for i in range(n):
            a = offset + i * math.tau / n
            self.enemy_bullets.append(Bullet(x, y, math.cos(a) * speed, math.sin(a) * speed,
                                             radius=5, color=(200, 90, 255)))

    def shoot(self):
        p = self.player
        if p.cooldown > 0:
            return
        p.cooldown = 6
        # 레벨 1: 2발 평행, 이후 4/8/16발 부채꼴
        n = 2 ** self.shot_level
        step = 0 if n == 2 else 0.32 / math.sqrt(n)
        for i in range(n):
            k = i - (n - 1) / 2
            a = k * step
            self.bullets.append(Bullet(p.x + k * (12 if n == 2 else 3), p.y - 14,
                                       math.sin(a) * 11, -math.cos(a) * 11, player=True))
        self.sfx.play("shot")

    def crosshair(self):
        return self.player.x, self.player.y - BOMB_RANGE

    # --- 폭발 / 피격
    def explode(self, x, y, size=1.0, ground=False):
        for _ in range(int(16 * size)):
            color = random.choice(((255, 230, 120), (255, 150, 50), (240, 80, 40), (200, 200, 200)))
            self.particles.append(Particle(x, y, color, speed=3.2 * size, size=int(3 + 2 * size)))
        self.rings.append(Ring(x, y, int(26 * size)))
        self.sfx.play("big_explode" if size >= 2.5 else "explode")
        if ground:
            self.craters.append([x, y, int(9 * size)])

    def kill_enemy(self, e):
        e.dead = True
        self.score += e.score
        if isinstance(e, Boss):
            for i in range(14):
                self.delayed_explosions.append([i * 6, e.x + random.uniform(-60, 60),
                                                e.y + random.uniform(-40, 40)])
            self.explode(e.x, e.y, 3.0)
            self.shake = 45
            self.enemy_bullets.clear()
            self.items.append(Item(e.x, e.y))
            self.boss = None
            self.boss_count += 1
            self.next_boss = self.frame + 60 * 50
        else:
            self.explode(e.x, e.y, 1.6 if e.radius > 15 else 1.0, ground=e.ground)
            if getattr(e, "kind", "") in ("bunker", "hunter") and random.random() < 0.5:
                self.items.append(Item(e.x, e.y))

    def hit_player(self):
        p = self.player
        if p.invincible > 0:
            return
        self.explode(p.x, p.y, 2.0)
        self.sfx.play("hit")
        self.shake = 18
        self.lives -= 1
        self.shot_level = max(1, self.shot_level - 1)
        self.enemy_bullets.clear()
        self.bomb = None
        if self.lives < 0:
            self.state = "gameover"
            self.gameover_timer = 0
            self.high_score = max(self.high_score, self.score)
        else:
            self.player = Player()

    # --- 적 출현
    def spawn(self):
        f, d = self.frame, self.difficulty
        air_interval = max(45, int(150 - d * 25)) * (3 if self.boss else 1)
        if f % air_interval == 0:
            r = random.random()
            if r < 0.45:
                x0 = random.randint(60, WIDTH - 60)
                side = random.choice((-1, 1))
                for i in range(4):
                    self.air.append(AirEnemy("spinner", clamp(x0 + side * i * 22, 20, WIDTH - 20),
                                             -20 - i * 34))
            elif r < 0.8 or d < 1.3:
                x0 = random.randint(90, WIDTH - 90)
                for i in range(3):
                    self.air.append(AirEnemy("weaver", x0, -20 - i * 40))
            else:
                self.air.append(AirEnemy("hunter", random.randint(60, WIDTH - 60), -30))

        ground_interval = max(55, int(120 - d * 12))
        if f % ground_interval == 30:
            row, y = self.terrain.top_row()
            land = [c for c, (kind, _) in enumerate(row) if kind in (GRASS, FOREST, SAND, ROAD)]
            if land:
                c = random.choice(land)
                kind = random.choices(("turret", "tank", "bunker"), (0.5, 0.35, 0.15))[0]
                self.ground.append(GroundEnemy(kind, c * TILE + TILE / 2, y))

        if not self.boss and f >= self.next_boss:
            self.boss = Boss(self.boss_count + 1)
            self.warning = 180
            self.sfx.play("warning")

    # --- 업데이트
    def update(self, keys):
        playing = self.state == "play"
        self.frame += 1
        self.terrain.update(SCROLL_SPEED)

        if playing:
            self.player.update(keys)
            if keys[pygame.K_z] or keys[pygame.K_SPACE]:
                self.shoot()
            if keys[pygame.K_x] and self.bomb is None:
                self.bomb = Bomb(self.player.x, self.player.y)
                self.sfx.play("bomb")
            self.spawn()
        else:
            self.gameover_timer += 1

        for group in (self.air, self.ground):
            for e in group:
                e.update(self)
        if self.boss:
            self.boss.update(self)
        for b in self.bullets:
            b.update()
        for b in self.enemy_bullets:
            b.update()
        for it in self.items:
            it.update()
        for c in self.craters:
            c[1] += SCROLL_SPEED

        # 폭탄 착탄
        if self.bomb:
            self.bomb.update()
            if self.bomb.landed:
                bx, by = self.bomb.x, self.bomb.y
                self.explode(bx, by, 0.8, ground=True)
                for g in self.ground:
                    if not g.dead and dist2(bx, by, g.x, g.y) < (g.radius + 16) ** 2:
                        self.kill_enemy(g)
                self.bomb = None

        # 샷 vs 공중 적
        targets = self.air + ([self.boss] if self.boss else [])
        for b in self.bullets:
            for e in targets:
                if not e.dead and dist2(b.x, b.y, e.x, e.y) < (e.radius + 4) ** 2:
                    b.dead = True
                    e.hp -= 1
                    e.flash = 3
                    if e.hp <= 0:
                        self.kill_enemy(e)
                    break

        if playing:
            p = self.player
            for b in self.enemy_bullets:
                if dist2(b.x, b.y, p.x, p.y) < (b.radius + p.radius) ** 2:
                    b.dead = True
                    self.hit_player()
                    break
        if self.state == "play":
            p = self.player
            for e in targets:
                if not e.dead and dist2(e.x, e.y, p.x, p.y) < (e.radius + p.radius + 4) ** 2:
                    if not isinstance(e, Boss) and p.invincible <= 0:
                        self.kill_enemy(e)
                    self.hit_player()
                    break
        if self.state == "play":
            p = self.player
            for it in self.items:
                if dist2(it.x, it.y, p.x, p.y) < 24 ** 2:
                    it.dead = True
                    self.sfx.play("item")
                    if self.shot_level < MAX_SHOT_LEVEL:
                        self.shot_level += 1
                    else:
                        self.score += 1000
                    self.rings.append(Ring(it.x, it.y, 30))

        for de in self.delayed_explosions:
            de[0] -= 1
            if de[0] <= 0:
                self.explode(de[1], de[2], 1.5)
        self.delayed_explosions = [de for de in self.delayed_explosions if de[0] > 0]

        for p in self.particles:
            p.update()
        for r in self.rings:
            r.update()

        self.air = [e for e in self.air if not e.dead]
        self.ground = [e for e in self.ground if not e.dead]
        self.bullets = [b for b in self.bullets if not b.dead]
        self.enemy_bullets = [b for b in self.enemy_bullets if not b.dead]
        self.items = [i for i in self.items if not i.dead]
        self.particles = [p for p in self.particles if p.life > 0]
        self.rings = [r for r in self.rings if not r.dead]
        self.craters = [c for c in self.craters if c[1] < HEIGHT + 20]

        if self.warning:
            self.warning -= 1
        if self.shake:
            self.shake -= 1

    # --- 그리기
    def text(self, surf, s, font, color, center=None, topleft=None, topright=None):
        img = font.render(s, True, color)
        shadow = font.render(s, True, (0, 0, 0))
        if center:
            rect = img.get_rect(center=center)
        elif topright:
            rect = img.get_rect(topright=topright)
        else:
            rect = img.get_rect(topleft=topleft)
        surf.blit(shadow, rect.move(2, 2))
        surf.blit(img, rect)

    def draw_crosshair(self, surf):
        cx, cy = self.crosshair()
        locked = any(dist2(cx, cy, g.x, g.y) < (g.radius + 10) ** 2 for g in self.ground)
        c = (255, 60, 60) if locked else (230, 230, 230)
        s = 10
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            x, y = cx + dx * s, cy + dy * s
            pygame.draw.line(surf, c, (x, y), (x - dx * 5, y), 2)
            pygame.draw.line(surf, c, (x, y), (x, y - dy * 5), 2)
        pygame.draw.circle(surf, c, (int(cx), int(cy)), 2)

    def draw_hud(self, surf):
        self.text(surf, f"SCORE {self.score:08d}", self.font, (255, 255, 255), topleft=(10, 8))
        self.text(surf, f"HI {max(self.high_score, self.score):08d}", self.font, (255, 220, 120),
                  topright=(WIDTH - 10, 8))
        for i in range(max(0, self.lives)):
            x, y = 18 + i * 22, HEIGHT - 20
            pygame.draw.polygon(surf, (230, 236, 246), [(x, y - 9), (x + 8, y + 7), (x - 8, y + 7)])
        self.text(surf, f"SHOT x{2 ** self.shot_level}", self.font_small, (160, 220, 255),
                  topright=(WIDTH - 10, HEIGHT - 28))
        if self.boss:
            w = WIDTH - 40
            pygame.draw.rect(surf, (40, 0, 0), (20, 40, w, 8))
            pygame.draw.rect(surf, (255, 70, 70), (20, 40, int(w * self.boss.hp / self.boss.max_hp), 8))
            pygame.draw.rect(surf, (255, 255, 255), (20, 40, w, 8), 1)

    def overlay(self, surf, alpha=140):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 20, alpha))
        surf.blit(dim, (0, 0))

    def draw(self):
        c = self.canvas
        self.terrain.draw(c)
        for x, y, r in self.craters:
            pygame.draw.circle(c, (52, 44, 34), (int(x), int(y)), r + 3)
            pygame.draw.circle(c, (30, 26, 22), (int(x), int(y)), r)
        for g in self.ground:
            g.draw(c, self.frame)
        if self.bomb:
            self.bomb.draw(c)

        # 공중 물체의 그림자
        self.shadow.fill((0, 0, 0, 0))
        flyers = list(self.air) + ([self.boss] if self.boss else [])
        if self.state == "play":
            flyers.append(self.player)
        for f in flyers:
            r = 40 if isinstance(f, Boss) else 10
            pygame.draw.ellipse(self.shadow, (0, 0, 0, 70),
                                (f.x + 24 - r, f.y + 36 - r * 0.6, r * 2, r * 1.2))
        c.blit(self.shadow, (0, 0))

        for it in self.items:
            it.draw(c, self.font_small)
        if self.boss:
            self.boss.draw(c, self.frame)
        for e in self.air:
            e.draw(c, self.frame)
        if self.state == "play":
            self.draw_crosshair(c)
            self.player.draw(c, self.frame)
        for b in self.bullets:
            b.draw(c)
        for r in self.rings:
            r.draw(c)
        for p in self.particles:
            p.draw(c)
        for b in self.enemy_bullets:
            b.draw(c)

        if self.state == "title":
            self.overlay(c)
            self.text(c, "AERO STRIKE", self.font_big, (255, 220, 90), center=(WIDTH / 2, 190))
            self.text(c, "종스크롤 슈팅", self.font, (200, 220, 255), center=(WIDTH / 2, 240))
            lines = ["방향키 / WASD : 이동",
                     "Z / Space : 공중 공격 (샷)",
                     "X : 지상 공격 (폭탄)",
                     "P : 일시정지    ESC : 종료"]
            for i, s in enumerate(lines):
                self.text(c, s, self.font_small, (230, 230, 230), center=(WIDTH / 2, 320 + i * 28))
            if (pygame.time.get_ticks() // 500) % 2:
                self.text(c, "Enter 키를 눌러 시작", self.font, (255, 255, 255), center=(WIDTH / 2, 480))
        else:
            self.draw_hud(c)
            if self.warning and (self.warning // 15) % 2:
                self.text(c, "WARNING", self.font_big, (255, 60, 60), center=(WIDTH / 2, HEIGHT / 2 - 40))
                self.text(c, "거대 요새 접근 중!", self.font, (255, 200, 200), center=(WIDTH / 2, HEIGHT / 2 + 10))
            if self.paused:
                self.overlay(c, 100)
                self.text(c, "PAUSE", self.font_big, (255, 255, 255), center=(WIDTH / 2, HEIGHT / 2))
            if self.state == "gameover":
                self.overlay(c, min(150, self.gameover_timer * 3))
                self.text(c, "GAME OVER", self.font_big, (255, 90, 90), center=(WIDTH / 2, 250))
                self.text(c, f"SCORE {self.score}", self.font, (255, 255, 255), center=(WIDTH / 2, 310))
                if self.gameover_timer > 60 and (pygame.time.get_ticks() // 500) % 2:
                    self.text(c, "Enter 키를 눌러 다시 시작", self.font, (255, 255, 255),
                              center=(WIDTH / 2, 390))

        ox = oy = 0
        if self.shake:
            m = min(8, self.shake // 3 + 1)
            ox, oy = random.randint(-m, m), random.randint(-m, m)
        self.screen.fill((0, 0, 0))
        self.screen.blit(c, (ox, oy))
        pygame.display.flip()

    # --- 메인 루프
    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()
                    if self.state == "title" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.reset()
                        self.state = "play"
                    elif (self.state == "gameover" and self.gameover_timer > 60
                          and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER)):
                        self.reset()
                        self.state = "play"
                    elif self.state == "play" and event.key == pygame.K_p:
                        self.paused = not self.paused

            keys = pygame.key.get_pressed()
            if self.state == "title":
                self.terrain.update(SCROLL_SPEED)
            elif not self.paused:
                self.update(keys)
            self.draw()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
