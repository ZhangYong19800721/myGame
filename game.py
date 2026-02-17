import math
import random
from dataclasses import dataclass

import pygame


SCREEN_WIDTH = 832
SCREEN_HEIGHT = 640
TILE_SIZE = 32
GRID_WIDTH = SCREEN_WIDTH // TILE_SIZE
GRID_HEIGHT = SCREEN_HEIGHT // TILE_SIZE
FPS = 60

PLAYER_SPEED = 2.3
ENEMY_SPEED = 1.5
BULLET_SPEED = 6
PLAYER_FIRE_COOLDOWN = 320
ENEMY_FIRE_COOLDOWN_RANGE = (850, 1500)
SPAWN_INTERVAL = 1800
MAX_ACTIVE_ENEMIES = 6
TOTAL_ENEMIES = 20


DIRECTION_VECTORS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}


@dataclass
class Bullet:
    x: float
    y: float
    direction: str
    owner: str

    width: int = 8
    height: int = 8

    def update(self):
        dx, dy = DIRECTION_VECTORS[self.direction]
        self.x += dx * BULLET_SPEED
        self.y += dy * BULLET_SPEED

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)


class Tank:
    def __init__(self, x, y, color, speed, owner):
        self.x = x
        self.y = y
        self.width = 28
        self.height = 28
        self.color = color
        self.speed = speed
        self.direction = "up"
        self.owner = owner
        self.hp = 1
        self.alive = True
        self.last_shot_at = 0

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    def move(self, direction, walls, other_tanks):
        if not self.alive:
            return
        self.direction = direction
        dx, dy = DIRECTION_VECTORS[direction]
        next_rect = self.rect.move(dx * self.speed, dy * self.speed)
        if self._can_move_to(next_rect, walls, other_tanks):
            self.x += dx * self.speed
            self.y += dy * self.speed

    def _can_move_to(self, rect, walls, other_tanks):
        if rect.left < 0 or rect.right > SCREEN_WIDTH or rect.top < 0 or rect.bottom > SCREEN_HEIGHT:
            return False
        for wall in walls:
            if wall.solid and rect.colliderect(wall.rect):
                return False
        for tank in other_tanks:
            if tank is self or not tank.alive:
                continue
            if rect.colliderect(tank.rect):
                return False
        return True

    def fire(self, now):
        if now - self.last_shot_at < PLAYER_FIRE_COOLDOWN and self.owner == "player":
            return None
        self.last_shot_at = now

        dx, dy = DIRECTION_VECTORS[self.direction]
        bullet_x = self.x + self.width / 2 - 4 + dx * 14
        bullet_y = self.y + self.height / 2 - 4 + dy * 14
        return Bullet(bullet_x, bullet_y, self.direction, self.owner)


class EnemyTank(Tank):
    def __init__(self, x, y):
        super().__init__(x, y, (210, 70, 60), ENEMY_SPEED, "enemy")
        self.ai_switch_at = 0
        self.fire_at = 0

    def update_ai(self, now, walls, player, enemies):
        if now >= self.ai_switch_at:
            self.direction = random.choice(list(DIRECTION_VECTORS.keys()))
            self.ai_switch_at = now + random.randint(400, 900)

        if random.random() < 0.08:
            self._try_face_player(player)

        self.move(self.direction, walls, enemies + [player])

        if now >= self.fire_at:
            self.fire_at = now + random.randint(*ENEMY_FIRE_COOLDOWN_RANGE)
            return self.fire(now)
        return None

    def _try_face_player(self, player):
        if not player.alive:
            return
        diff_x = player.x - self.x
        diff_y = player.y - self.y
        if abs(diff_x) > abs(diff_y):
            self.direction = "right" if diff_x > 0 else "left"
        else:
            self.direction = "down" if diff_y > 0 else "up"


@dataclass
class Wall:
    rect: pygame.Rect
    breakable: bool = False
    alive: bool = True

    @property
    def solid(self):
        return self.alive


class Base:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.alive = True


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Battle City Lite - Python")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 24)
        self.big_font = pygame.font.SysFont("Arial", 42, bold=True)

        self.base = Base(SCREEN_WIDTH // 2 - TILE_SIZE // 2, SCREEN_HEIGHT - TILE_SIZE * 2)
        self.walls = self._build_map()
        self.player = Tank(SCREEN_WIDTH // 2 - 14, SCREEN_HEIGHT - TILE_SIZE * 4, (80, 170, 220), PLAYER_SPEED, "player")
        self.enemies = []
        self.bullets = []

        self.enemies_spawned = 0
        self.enemies_destroyed = 0
        self.next_spawn_at = 0
        self.game_over = False
        self.victory = False

    def _build_map(self):
        walls = []
        # 场景四周钢墙
        for gx in range(GRID_WIDTH):
            walls.append(Wall(pygame.Rect(gx * TILE_SIZE, 0, TILE_SIZE, TILE_SIZE), breakable=False))
            walls.append(Wall(pygame.Rect(gx * TILE_SIZE, SCREEN_HEIGHT - TILE_SIZE, TILE_SIZE, TILE_SIZE), breakable=False))
        for gy in range(1, GRID_HEIGHT - 1):
            walls.append(Wall(pygame.Rect(0, gy * TILE_SIZE, TILE_SIZE, TILE_SIZE), breakable=False))
            walls.append(Wall(pygame.Rect(SCREEN_WIDTH - TILE_SIZE, gy * TILE_SIZE, TILE_SIZE, TILE_SIZE), breakable=False))

        # 中间砖墙障碍
        for gy in [5, 7, 9, 11]:
            for gx in range(4, GRID_WIDTH - 4):
                if gx % 2 == 0:
                    walls.append(Wall(pygame.Rect(gx * TILE_SIZE, gy * TILE_SIZE, TILE_SIZE, TILE_SIZE), breakable=True))

        # 基地防御墙
        base_x = self.base.rect.x // TILE_SIZE
        base_y = self.base.rect.y // TILE_SIZE
        for ox, oy in [(-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]:
            walls.append(Wall(pygame.Rect((base_x + ox) * TILE_SIZE, (base_y + oy) * TILE_SIZE, TILE_SIZE, TILE_SIZE), breakable=True))

        return walls

    def spawn_enemy(self, now):
        if self.enemies_spawned >= TOTAL_ENEMIES:
            return
        if len([e for e in self.enemies if e.alive]) >= MAX_ACTIVE_ENEMIES:
            return
        if now < self.next_spawn_at:
            return

        spawn_points = [
            (TILE_SIZE * 2, TILE_SIZE * 2),
            (SCREEN_WIDTH // 2 - 14, TILE_SIZE * 2),
            (SCREEN_WIDTH - TILE_SIZE * 3, TILE_SIZE * 2),
        ]
        random.shuffle(spawn_points)
        for sx, sy in spawn_points:
            ghost = EnemyTank(sx, sy)
            blocked = any(ghost.rect.colliderect(w.rect) and w.solid for w in self.walls)
            if blocked:
                continue
            conflict_player = ghost.rect.colliderect(self.player.rect)
            conflict_enemies = any(ghost.rect.colliderect(e.rect) for e in self.enemies if e.alive)
            if conflict_player or conflict_enemies:
                continue
            self.enemies.append(ghost)
            self.enemies_spawned += 1
            self.next_spawn_at = now + SPAWN_INTERVAL
            return

        self.next_spawn_at = now + 300

    def update(self, dt, now):
        if self.game_over:
            return

        self.spawn_enemy(now)

        keys = pygame.key.get_pressed()
        if self.player.alive:
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                self.player.move("up", self.walls, self.enemies)
            elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
                self.player.move("down", self.walls, self.enemies)
            elif keys[pygame.K_a] or keys[pygame.K_LEFT]:
                self.player.move("left", self.walls, self.enemies)
            elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                self.player.move("right", self.walls, self.enemies)

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            bullet = enemy.update_ai(now, self.walls, self.player, self.enemies)
            if bullet:
                self.bullets.append(bullet)

        for bullet in list(self.bullets):
            bullet.update()
            if not pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT).contains(bullet.rect):
                self.bullets.remove(bullet)
                continue

            hit = False
            for wall in self.walls:
                if wall.alive and bullet.rect.colliderect(wall.rect):
                    if wall.breakable:
                        wall.alive = False
                    hit = True
                    break
            if hit:
                self.bullets.remove(bullet)
                continue

            if self.base.alive and bullet.rect.colliderect(self.base.rect):
                self.base.alive = False
                self.bullets.remove(bullet)
                self.game_over = True
                self.victory = False
                continue

            if bullet.owner == "player":
                for enemy in self.enemies:
                    if enemy.alive and bullet.rect.colliderect(enemy.rect):
                        enemy.alive = False
                        self.enemies_destroyed += 1
                        hit = True
                        break
            else:
                if self.player.alive and bullet.rect.colliderect(self.player.rect):
                    self.player.alive = False
                    hit = True
                    self.game_over = True
                    self.victory = False

            if hit and bullet in self.bullets:
                self.bullets.remove(bullet)

        if self.enemies_destroyed >= TOTAL_ENEMIES:
            self.game_over = True
            self.victory = True

    def draw(self):
        self.screen.fill((35, 40, 45))

        for wall in self.walls:
            if not wall.alive:
                continue
            color = (180, 120, 70) if wall.breakable else (120, 125, 135)
            pygame.draw.rect(self.screen, color, wall.rect)

        if self.base.alive:
            pygame.draw.rect(self.screen, (230, 210, 70), self.base.rect)
            pygame.draw.rect(self.screen, (50, 50, 20), self.base.rect, 2)

        if self.player.alive:
            self._draw_tank(self.player)

        for enemy in self.enemies:
            if enemy.alive:
                self._draw_tank(enemy)

        for bullet in self.bullets:
            pygame.draw.rect(self.screen, (245, 245, 245), bullet.rect)

        info = f"敌方总数: {TOTAL_ENEMIES}  已击毁: {self.enemies_destroyed}  剩余: {TOTAL_ENEMIES - self.enemies_destroyed}"
        text_surface = self.font.render(info, True, (235, 235, 235))
        self.screen.blit(text_surface, (20, 10))

        if self.game_over:
            msg = "胜利！你守住了基地" if self.victory else "失败！基地或我方坦克被摧毁"
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 130))
            self.screen.blit(overlay, (0, 0))
            over_surface = self.big_font.render(msg, True, (255, 255, 255))
            self.screen.blit(over_surface, (SCREEN_WIDTH // 2 - over_surface.get_width() // 2, SCREEN_HEIGHT // 2 - 40))
            tip = self.font.render("按 R 重新开始，按 ESC 退出", True, (255, 255, 255))
            self.screen.blit(tip, (SCREEN_WIDTH // 2 - tip.get_width() // 2, SCREEN_HEIGHT // 2 + 18))

        pygame.display.flip()

    def _draw_tank(self, tank):
        body = tank.rect
        pygame.draw.rect(self.screen, tank.color, body)
        turret_color = (20, 20, 20)
        center_x, center_y = body.center
        if tank.direction == "up":
            muzzle = (center_x, body.top - 8)
        elif tank.direction == "down":
            muzzle = (center_x, body.bottom + 8)
        elif tank.direction == "left":
            muzzle = (body.left - 8, center_y)
        else:
            muzzle = (body.right + 8, center_y)
        pygame.draw.line(self.screen, turret_color, (center_x, center_y), muzzle, 4)
        pygame.draw.circle(self.screen, (225, 225, 225), (center_x, center_y), 4)

    def reset(self):
        self.__init__()

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS)
            now = pygame.time.get_ticks()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE and self.player.alive and not self.game_over:
                        bullet = self.player.fire(now)
                        if bullet:
                            self.bullets.append(bullet)
                    elif event.key == pygame.K_r and self.game_over:
                        self.reset()

            self.update(dt, now)
            self.draw()

        pygame.quit()


if __name__ == "__main__":
    Game().run()
