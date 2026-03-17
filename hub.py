# hub.py - Castle courtyard (hub world)
import math, pygame
from constants import *

# Hub-local tile types
STONE     = 4
WALL      = 5
HUB_GRASS = 6

C_STONE      = (130, 120, 110)
C_STONE_D    = (115, 105,  95)
C_WALL       = ( 85,  75,  70)
C_HUB_GRASS  = ( 70, 140,  60)
C_HUB_GRASS_D = ( 55, 120,  45)

HUB_W = 24
HUB_H = 18

EXIT_TILES = [(x, 17) for x in range(10, 14)]


def make_hub_map():
    tilemap = [[STONE] * HUB_W for _ in range(HUB_H)]
    for x in range(HUB_W):
        tilemap[0][x]       = WALL
        tilemap[HUB_H-1][x] = WALL
    for y in range(HUB_H):
        tilemap[y][0]       = WALL
        tilemap[y][HUB_W-1] = WALL
    for y in range(6, 9):
        for x in range(8, 16):
            tilemap[y][x] = HUB_GRASS
    for x in range(10, 14):
        tilemap[HUB_H-1][x] = STONE
    return tilemap


class HubScene:
    def __init__(self, screen, clock, save):
        self.screen  = screen
        self.clock   = clock
        self.save    = save
        self.tilemap = make_hub_map()
        self.player_x = float(HUB_W // 2 * TILE + TILE // 2)
        self.player_y = float((HUB_H - 3) * TILE)
        self.fx = 0.0; self.fy = -1.0
        self.font_s = pygame.font.SysFont("monospace", 15)
        self.font_m = pygame.font.SysFont("monospace", 20)
        self.font_g = pygame.font.SysFont("monospace", 28, bold=True)
        self.welcome_timer = 3 * FPS if save.get("highest_floor", 0) > 0 else 0

    def get_tile(self, tx, ty):
        if 0 <= tx < HUB_W and 0 <= ty < HUB_H:
            return self.tilemap[ty][tx]
        return WALL

    def is_blocked(self, tx, ty):
        return self.get_tile(tx, ty) == WALL

    def at_exit(self):
        return int(self.player_y // TILE) >= HUB_H - 1

    def run(self):
        while True:
            self.clock.tick(FPS)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return "quit"
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    return "quit"

            keys = pygame.key.get_pressed()
            mx, my = 0.0, 0.0
            if keys[pygame.K_w]: my -= 1
            if keys[pygame.K_s]: my += 1
            if keys[pygame.K_a]: mx -= 1
            if keys[pygame.K_d]: mx += 1
            length = math.hypot(mx, my)
            if length:
                mx, my = mx / length, my / length
            if mx or my:
                self.fx, self.fy = mx, my

            speed = 2.5; r = 13
            nx = self.player_x + mx * speed
            if not any(self.is_blocked(int((nx + ox) // TILE),
                                       int((self.player_y + oy) // TILE))
                       for ox in (-r, r) for oy in (-r, r)):
                self.player_x = nx
            ny = self.player_y + my * speed
            if not any(self.is_blocked(int((self.player_x + ox) // TILE),
                                       int((ny + oy) // TILE))
                       for ox in (-r, r) for oy in (-r, r)):
                self.player_y = ny

            if self.at_exit():
                return "forest"

            if self.welcome_timer > 0:
                self.welcome_timer -= 1
            self.draw()
            pygame.display.flip()

    def draw(self):
        cam_x = max(0, min(int(self.player_x - SCREEN_W / 2), HUB_W * TILE - SCREEN_W))
        cam_y = max(0, min(int(self.player_y - SCREEN_H / 2), HUB_H * TILE - SCREEN_H))

        self.screen.fill((20, 20, 20))

        for ty in range(HUB_H):
            for tx in range(HUB_W):
                sx = tx * TILE - cam_x
                sy = ty * TILE - cam_y
                t  = self.get_tile(tx, ty)
                r  = pygame.Rect(sx, sy, TILE, TILE)
                if t == STONE:
                    kl = C_STONE if (tx + ty) % 2 == 0 else C_STONE_D
                    pygame.draw.rect(self.screen, kl, r)
                elif t == WALL:
                    pygame.draw.rect(self.screen, C_WALL, r)
                    pygame.draw.rect(self.screen, (60, 52, 48), r, 2)
                elif t == HUB_GRASS:
                    kl = C_HUB_GRASS if (tx + ty) % 2 == 0 else C_HUB_GRASS_D
                    pygame.draw.rect(self.screen, kl, r)

        # Exit portal
        for etx, ety in EXIT_TILES:
            sx = etx * TILE - cam_x
            sy = ety * TILE - cam_y
            pygame.draw.rect(self.screen, (80, 160, 80), (sx, sy, TILE, TILE))
        if self.player_y // TILE >= HUB_H - 2:
            t = self.font_s.render("The Forest", True, (200, 255, 200))
            self.screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, SCREEN_H - 40))

        # Player
        ssx = int(self.player_x - cam_x)
        ssy = int(self.player_y - cam_y)
        pygame.draw.ellipse(self.screen, C_SHADOW, (ssx - 11, ssy + 9, 22, 11))
        pygame.draw.circle(self.screen, C_PLAYER, (ssx, ssy), 15)
        pygame.draw.circle(self.screen, C_EYE,
            (int(ssx + self.fx * 9), int(ssy + self.fy * 9)), 5)

        self.draw_hud()

        # Welcome back banner
        if self.welcome_timer > 0:
            alpha         = min(255, self.welcome_timer * 5)
            floor_reached = self.save.get("highest_floor", 0)
            if floor_reached > 0:
                overlay = pygame.Surface((SCREEN_W, 120), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, min(160, alpha)))
                self.screen.blit(overlay, (0, SCREEN_H // 2 - 70))
                t1 = self.font_g.render("Welcome back, knight!", True, (220, 200, 120))
                t1.set_alpha(alpha)
                self.screen.blit(t1, (SCREEN_W // 2 - t1.get_width() // 2, SCREEN_H // 2 - 55))
                t2 = self.font_m.render(f"Highest floor reached: Floor {floor_reached}",
                                        True, (180, 220, 255))
                t2.set_alpha(alpha)
                self.screen.blit(t2, (SCREEN_W // 2 - t2.get_width() // 2, SCREEN_H // 2 - 10))

    def draw_hud(self):
        t = self.font_s.render("Hub  —  WASD to move  |  walk to the portal",
                               True, (220, 220, 180))
        self.screen.blit(t, (10, 10))