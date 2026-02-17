# -*- coding: utf-8 -*-
import random
from dataclasses import dataclass

import pygame


SCREEN_WIDTH = 832
SCREEN_HEIGHT = 640
TILE_SIZE = 32
GRID_WIDTH = SCREEN_WIDTH // TILE_SIZE
GRID_HEIGHT = SCREEN_HEIGHT // TILE_SIZE
FPS = 60

PLAYER_SPEED = 2.2
ENEMY_SPEED = 1.45
BULLET_SPEED = 6
PLAYER_FIRE_COOLDOWN = 340
ENEMY_FIRE_COOLDOWN_RANGE = (900, 1700)
SPAWN_INTERVAL = 1800
MAX_ACTIVE_ENEMIES = 6
TOTAL_ENEMIES = 20
PLAYER_LIVES = 3
RESPAWN_INVULNERABLE_MS = 1300
ENEMY_SPAWN_INVULNERABLE_MS = 900

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
    owner_id: int
    power: int = 1
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
    _id_seq = 0

    def __init__(self, x, y, color, speed, owner):
        Tank._id_seq += 1
        self.tank_id = Tank._id_seq
        self.x = x
        self.y = y
        self.width = 28
        self.height = 28
        self.color = color
        self.speed = speed
        self.direction = "up"
        self.owner = owner
        self.alive = True
        self.last_shot_at = 0
        self.spawn_protected_until = 0

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
            if wall.solid and wall.alive and rect.colliderect(wall.rect):
                return False

        for tank in other_tanks:
            if tank is self or not tank.alive:
                continue
            if rect.colliderect(tank.rect):
                return False

        return True

    def fire(self, now):
        if self.owner == "player" and now - self.last_shot_at < PLAYER_FIRE_COOLDOWN:
            return None

        self.last_shot_at = now
        dx, dy = DIRECTION_VECTORS[self.direction]
        bullet_x = self.x + self.width / 2 - 4 + dx * 14
        bullet_y = self.y + self.height / 2 - 4 + dy * 14
        return Bullet(bullet_x, bullet_y, self.direction, self.owner, self.tank_id)


class EnemyTank(Tank):
    def __init__(self, x, y):
        super().__init__(x, y, (210, 70, 60), ENEMY_SPEED, "enemy")
        self.ai_switch_at = 0
        self.fire_at = 0

    def update_ai(self, now, walls, player, enemies):
        if now >= self.ai_switch_at:
            self.direction = random.choice(list(DIRECTION_VECTORS.keys()))
            self.ai_switch_at = now + random.randint(360, 860)

        if random.random() < 0.09:
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
    tile_type: str
    breakable: bool = False
    alive: bool = True

    @property
    def solid(self):
        return self.tile_type in {"brick", "steel", "water"}


class Base:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.alive = True


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Battle City Lite")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        self.supports_cjk = False
        self.font = self._create_font(23)
        self.big_font = self._create_font(42, bold=True)

        self.reset_state(pygame.time.get_ticks())

    def reset_state(self, now):
        Tank._id_seq = 0
        self.base = Base(SCREEN_WIDTH // 2 - TILE_SIZE // 2, SCREEN_HEIGHT - TILE_SIZE * 2)
        self.player_spawn = (SCREEN_WIDTH // 2 - 14, SCREEN_HEIGHT - TILE_SIZE * 4)

        self.walls = self._build_map()
        self.player = Tank(self.player_spawn[0], self.player_spawn[1], (90, 180, 235), PLAYER_SPEED, "player")
        self.enemies = []
        self.bullets = []

        self.player_lives = PLAYER_LIVES
        self.player_invulnerable_until = now + RESPAWN_INVULNERABLE_MS

        self.enemies_spawned = 0
        self.enemies_destroyed = 0
        self.next_spawn_at = 0
        self.game_over = False
        self.victory = False

    def _supports_cjk_font(self):
        return False

    def _create_font(self, size, bold=False):
        if self.supports_cjk:
            font_order = [
                "Noto Sans CJK SC",
                "Microsoft YaHei",
                "SimHei",
                "PingFang SC",
                "WenQuanYi Zen Hei",
                "Arial Unicode MS",
                "Arial",
            ]
            return pygame.font.SysFont(font_order, size, bold=bold)
        return pygame.font.SysFont("Arial", size, bold=bold)

    def _build_map(self):
        walls = []

        # Map borders
        for gx in range(GRID_WIDTH):
            walls.append(Wall(pygame.Rect(gx * TILE_SIZE, 0, TILE_SIZE, TILE_SIZE), "steel"))
            walls.append(Wall(pygame.Rect(gx * TILE_SIZE, SCREEN_HEIGHT - TILE_SIZE, TILE_SIZE, TILE_SIZE), "steel"))
        for gy in range(1, GRID_HEIGHT - 1):
            walls.append(Wall(pygame.Rect(0, gy * TILE_SIZE, TILE_SIZE, TILE_SIZE), "steel"))
            walls.append(Wall(pygame.Rect(SCREEN_WIDTH - TILE_SIZE, gy * TILE_SIZE, TILE_SIZE, TILE_SIZE), "steel"))

        # Middle brick walls
        for gy in [5, 7, 9, 11]:
            for gx in range(3, GRID_WIDTH - 3):
                if gx % 2 == 0:
                    walls.append(Wall(pygame.Rect(gx * TILE_SIZE, gy * TILE_SIZE, TILE_SIZE, TILE_SIZE), "brick", breakable=True))

        # River obstacles
        for gx in [10, 11, 14, 15]:
            walls.append(Wall(pygame.Rect(gx * TILE_SIZE, 10 * TILE_SIZE, TILE_SIZE, TILE_SIZE), "water"))

        # Grass tiles (passable)
        for gx in [6, 7, 18, 19]:
            walls.append(Wall(pygame.Rect(gx * TILE_SIZE, 8 * TILE_SIZE, TILE_SIZE, TILE_SIZE), "grass"))
            walls.append(Wall(pygame.Rect(gx * TILE_SIZE, 12 * TILE_SIZE, TILE_SIZE, TILE_SIZE), "grass"))

        # Base protection (leave top opening)
        base_x = self.base.rect.x // TILE_SIZE
        base_y = self.base.rect.y // TILE_SIZE
        for ox, oy in [(-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]:
            walls.append(Wall(pygame.Rect((base_x + ox) * TILE_SIZE, (base_y + oy) * TILE_SIZE, TILE_SIZE, TILE_SIZE), "brick", breakable=True))

        return walls

    def _owner_has_active_bullet(self, owner_id):
        return any(b.owner_id == owner_id for b in self.bullets)

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
            enemy = EnemyTank(sx, sy)
            blocked = any(enemy.rect.colliderect(w.rect) and w.solid and w.alive for w in self.walls)
            if blocked:
                continue
            if enemy.rect.colliderect(self.player.rect):
                continue
            if any(enemy.rect.colliderect(e.rect) for e in self.enemies if e.alive):
                continue

            enemy.spawn_protected_until = now + ENEMY_SPAWN_INVULNERABLE_MS
            self.enemies.append(enemy)
            self.enemies_spawned += 1
            self.next_spawn_at = now + SPAWN_INTERVAL
            return

        self.next_spawn_at = now + 300

    def _respawn_player(self, now):
        self.player.x, self.player.y = self.player_spawn
        self.player.direction = "up"
        self.player_invulnerable_until = now + RESPAWN_INVULNERABLE_MS

    def update(self, now):
        if self.game_over:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_r]:
                self.reset_state(now)
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
            if not self._owner_has_active_bullet(enemy.tank_id):
                bullet = enemy.update_ai(now, self.walls, self.player, self.enemies)
                if bullet:
                    self.bullets.append(bullet)
            else:
                enemy.move(enemy.direction, self.walls, self.enemies + [self.player])

        for bullet in list(self.bullets):
            bullet.update()
            if not pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT).contains(bullet.rect):
                self.bullets.remove(bullet)
                continue

            hit = False

            # Bullet collision
            for other in list(self.bullets):
                if other is bullet:
                    continue
                if bullet.rect.colliderect(other.rect):
                    if bullet in self.bullets:
                        self.bullets.remove(bullet)
                    if other in self.bullets:
                        self.bullets.remove(other)
                    hit = True
                    break
            if hit:
                continue

            for wall in self.walls:
                if not wall.alive:
                    continue
                if bullet.rect.colliderect(wall.rect):
                    if wall.tile_type == "brick" and wall.breakable:
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
                    if not enemy.alive:
                        continue
                    if now < enemy.spawn_protected_until:
                        continue
                    if bullet.rect.colliderect(enemy.rect):
                        enemy.alive = False
                        self.enemies_destroyed += 1
                        hit = True
                        break
            else:
                if self.player.alive and bullet.rect.colliderect(self.player.rect):
                    if now >= self.player_invulnerable_until:
                        self.player_lives -= 1
                        if self.player_lives <= 0:
                            self.player.alive = False
                            self.game_over = True
                            self.victory = False
                        else:
                            self._respawn_player(now)
                    hit = True

            if hit and bullet in self.bullets:
                self.bullets.remove(bullet)

        if self.base.alive and self.enemies_destroyed >= TOTAL_ENEMIES:
            self.game_over = True
            self.victory = True

    def draw(self, now):
        self.screen.fill((35, 40, 45))

        # ?
        for wall in self.walls:
            if wall.tile_type == "grass" and wall.alive:
                pygame.draw.rect(self.screen, (75, 120, 70), wall.rect)

        for wall in self.walls:
            if not wall.alive or wall.tile_type == "grass":
                continue
            if wall.tile_type == "brick":
                color = (180, 120, 70)
            elif wall.tile_type == "steel":
                color = (120, 125, 135)
            elif wall.tile_type == "water":
                color = (55, 95, 165)
            else:
                color = (120, 125, 135)
            pygame.draw.rect(self.screen, color, wall.rect)

        self._draw_base()

        if self.player.alive:
            self._draw_tank(self.player, now)

        for enemy in self.enemies:
            if enemy.alive:
                self._draw_tank(enemy, now)

        for bullet in self.bullets:
            pygame.draw.rect(self.screen, (245, 245, 245), bullet.rect)

        # Draw grass above tanks
        for wall in self.walls:
            if wall.tile_type == "grass" and wall.alive:
                pygame.draw.rect(self.screen, (88, 145, 82), wall.rect)

        self._draw_hud()

        if self.game_over:
            self._draw_game_over_overlay()

        pygame.display.flip()

    def _draw_base(self):
        if not self.base.alive:
            pygame.draw.rect(self.screen, (90, 45, 45), self.base.rect)
            return
        pygame.draw.rect(self.screen, (230, 210, 70), self.base.rect)
        pygame.draw.rect(self.screen, (40, 40, 20), self.base.rect, 2)
        cx, cy = self.base.rect.center
        pygame.draw.polygon(self.screen, (40, 40, 20), [(cx - 7, cy + 6), (cx, cy - 8), (cx + 7, cy + 6)])

    def _draw_hud(self):
        text = (
            f"Lives: {self.player_lives}  Enemies: {TOTAL_ENEMIES}  "
            f"Destroyed: {self.enemies_destroyed}  Left: {TOTAL_ENEMIES - self.enemies_destroyed}"
        )

        surf = self.font.render(text, True, (235, 235, 235))
        self.screen.blit(surf, (20, 10))

    def _draw_game_over_overlay(self):
        msg = "Victory! Base Defended" if self.victory else "Defeat! Base destroyed or no lives"
        tip_text = "Press R to restart, ESC to quit"

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 130))
        self.screen.blit(overlay, (0, 0))

        over_surface = self.big_font.render(msg, True, (255, 255, 255))
        self.screen.blit(over_surface, (SCREEN_WIDTH // 2 - over_surface.get_width() // 2, SCREEN_HEIGHT // 2 - 40))

        tip = self.font.render(tip_text, True, (255, 255, 255))
        self.screen.blit(tip, (SCREEN_WIDTH // 2 - tip.get_width() // 2, SCREEN_HEIGHT // 2 + 18))

    def _draw_tank(self, tank, now):
        body = tank.rect
        color = tank.color

        # Respawn/invulnerability blink
        if tank.owner == "player" and now < self.player_invulnerable_until:
            if (now // 100) % 2 == 0:
                color = (255, 255, 255)
        if tank.owner == "enemy" and now < tank.spawn_protected_until:
            if (now // 100) % 2 == 0:
                color = (250, 250, 250)

        pygame.draw.rect(self.screen, color, body)
        center_x, center_y = body.center

        if tank.direction == "up":
            muzzle = (center_x, body.top - 8)
        elif tank.direction == "down":
            muzzle = (center_x, body.bottom + 8)
        elif tank.direction == "left":
            muzzle = (body.left - 8, center_y)
        else:
            muzzle = (body.right + 8, center_y)

        pygame.draw.line(self.screen, (20, 20, 20), (center_x, center_y), muzzle, 4)
        pygame.draw.circle(self.screen, (225, 225, 225), (center_x, center_y), 4)

    def reset(self):
        self.reset_state(pygame.time.get_ticks())

    def run(self):
        running = True
        while running:
            self.clock.tick(FPS)
            now = pygame.time.get_ticks()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif self.game_over:
                        # Restart on any non-ESC key (KEYDOWN or KEYUP) to be robust.
                        self.reset_state(now)
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                        self.reset_state(now)
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and self.player.alive and not self.game_over:
                        if not self._owner_has_active_bullet(self.player.tank_id):
                            bullet = self.player.fire(now)
                            if bullet:
                                self.bullets.append(bullet)

            pygame.event.pump()
            if self.game_over and pygame.key.get_pressed()[pygame.K_r]:
                self.reset_state(now)

            self.update(now)
            self.draw(now)

        pygame.quit()


if __name__ == "__main__":
    Game().run()

