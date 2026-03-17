# forest.py - Forest level (Level 1)
# Thin subclass of BaseLevel — only forest-specific logic.
import math, random, pygame
from constants import *
from entities import Enemy
from base_level import BaseLevel
from map_gen import (generate_forest, generate_arena, draw_tile, draw_tree,
                     MAP_WIDTH, MAP_HEIGHT, ROOM_SIZES)
from level_manager import generate_floor_graph
import effects as _fx
import sound


class ForestScene(BaseLevel):

    # ── Floor / room generation (forest-specific) ────────────────────────────

    def _generate_floor(self, first=True):
        self.dream_touched = False
        self.floor_graph, self.start_pos = generate_floor_graph(self.level_mgr.floor_num)
        self.current_pos = self.start_pos
        for i, (pos, room) in enumerate(self.floor_graph.items()):
            seed      = abs(hash((pos, self.level_mgr.floor_num, i))) % 99999
            rng_state = random.getstate()
            random.seed(seed)
            rw, rh = ROOM_SIZES.get(room.get("size", "medium"), (MAP_WIDTH, MAP_HEIGHT))
            if room["type"] == "boss":
                kd = generate_arena(room["doors"], width=rw, height=rh)
            else:
                kd = generate_forest(room["doors"], width=rw, height=rh)
            room["map_data"] = kd
            random.setstate(rng_state)
        self._load_room(self.start_pos, direction=None, first=first)

    # ── Enemy spawning (forest-specific placement) ───────────────────────────

    def _spawn_group(self, e_type, count, hp_mult, damage_mult):
        sp = self.player
        cx, cy = sp.x, sp.y
        for _ in range(200):
            angle = random.uniform(0, math.pi * 2)
            d     = random.randint(280, 460)
            tx    = sp.x + math.cos(angle) * d
            ty    = sp.y + math.sin(angle) * d
            if self.get_tile(int(tx // TILE), int(ty // TILE)) in (GRASS, PATH):
                cx, cy = tx, ty
                break

        if not hasattr(self, 'campfire_positions'):
            self.campfire_positions = []
        if e_type == "ranged" and count >= 2:
            self.campfire_positions.append((cx, cy))

        group_id = random.randint(1000, 9999)
        WOLF_OFFSETS   = [(0, 0), (-18, 10), (18, 10), (-9, -14), (9, -14)]
        RANGED_OFFSETS = [(0, 0), (-50, 0), (50, 0), (0, -50), (0, 50)]

        for i in range(count):
            if e_type == "wolf":
                ox, oy = WOLF_OFFSETS[i % len(WOLF_OFFSETS)]
            else:
                ox, oy = RANGED_OFFSETS[i % len(RANGED_OFFSETS)]
            ex = cx + ox + random.uniform(-10, 10)
            ey = cy + oy + random.uniform(-10, 10)
            for _ in range(50):
                if self.get_tile(int(ex // TILE), int(ey // TILE)) in (GRASS, PATH):
                    break
                ex = cx + random.uniform(-60, 60)
                ey = cy + random.uniform(-60, 60)
            e          = Enemy(ex, ey, e_type, hp_mult, damage_mult)
            e.group_id = group_id
            self.enemies.append(e)

    # ── Collision (forest = trees block) ─────────────────────────────────────

    def is_blocked(self, tx, ty):
        return self.get_tile(tx, ty) == TREE

    # ── Drawing (forest-specific visuals) ────────────────────────────────────

    def _draw_tiles(self, surface, cam_x, cam_y):
        tx_start = max(0, cam_x // TILE)
        ty_start = max(0, cam_y // TILE)
        tx_end   = min(self.map_w, tx_start + SCREEN_W // TILE + 2)
        ty_end   = min(self.map_h, ty_start + SCREEN_H // TILE + 2)
        for ty in range(ty_start, ty_end):
            for tx in range(tx_start, tx_end):
                sx = tx * TILE - cam_x
                sy = ty * TILE - cam_y
                draw_tile(surface, tx, ty, sx, sy, self.get_tile)

    def _draw_decorations(self, surface, cam_x, cam_y):
        # Trees
        for tx, ty, size in self.trees:
            sx = tx * TILE - cam_x
            sy = ty * TILE - cam_y
            if (-TILE * 2 < sx < SCREEN_W + TILE * 2
                    and -TILE * 2 < sy < SCREEN_H + TILE * 2):
                palette = self.palette_map.get(
                    (tx, ty), ((100, 65, 30), (45, 130, 40), (30, 100, 25)))
                draw_tree(surface, tx, ty, size, palette, cam_x, cam_y)

        # Campfires
        for cx, cy in getattr(self, 'campfire_positions', []):
            sx   = int(cx - cam_x); sy = int(cy - cam_y)
            puls = 0.5 + 0.5 * math.sin(self.tick * 0.12)
            r    = int(10 + puls * 4)
            gs   = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(gs, (255, int(120 + puls * 80), 0, int(80 + puls * 60)),
                               (r + 2, r + 2), r)
            surface.blit(gs, (sx - r - 2, sy - r - 2))
            pygame.draw.circle(surface, (255, 200, 80), (sx, sy), 5)

    def _draw_rest_room_objects(self, surface, cam_x, cam_y):
        self._draw_floor_portal(surface, cam_x, cam_y)
        self._draw_rest_campfire(surface, cam_x, cam_y)

    def _draw_rest_campfire(self, surface, cam_x, cam_y):
        room = self.floor_graph[self.current_pos]
        if room["type"] != "rest":
            return

        sp        = self.player
        abandoned = room.get("abandoned_campsite", False)

        # ── No campfire placed yet ────────────────────────────────────────────
        if self.rest_campfire_pos is None:
            sx = int(sp.x - cam_x)
            sy = int(sp.y - cam_y)
            t  = self.font_s.render("Place campfire  [F]", True, (220, 180, 80))
            surface.blit(t, (sx - t.get_width() // 2, sy - 48))
            self._draw_ground_items(surface, cam_x, cam_y)
            return

        cx, cy = self.rest_campfire_pos
        sx = int(cx - cam_x)
        sy = int(cy - cam_y)
        puls = 0.5 + 0.5 * math.sin(self.tick * 0.12)

        if abandoned:
            # Warm coals — dimmer, more red/orange, no bright flame
            r  = int(8 + puls * 3)
            gs = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(gs, (180, int(50 + puls * 40), 0, int(60 + puls * 40)),
                               (r + 2, r + 2), r)
            surface.blit(gs, (sx - r - 2, sy - r - 2))
            pygame.draw.circle(surface, (200, 80, 20), (sx, sy), 4)
        else:
            # Fresh campfire — bright, tall flame
            r  = int(14 + puls * 6)
            gs = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(gs, (255, int(120 + puls * 80), 0, int(90 + puls * 60)),
                               (r + 2, r + 2), r)
            surface.blit(gs, (sx - r - 2, sy - r - 2))
            pygame.draw.circle(surface, (255, 200, 80), (sx, sy), 6)

        # ── Prompt / status ───────────────────────────────────────────────────
        if not self.rest_campfire_used:
            dist = math.hypot(sp.x - cx, sp.y - cy)
            if dist < 60:
                t = self.font_s.render("Sleep  [F]", True, (220, 200, 100))
                surface.blit(t, (sx - t.get_width() // 2, sy - 44))
        else:
            t = self.font_s.render("Rested", True, (120, 160, 100))
            surface.blit(t, (sx - t.get_width() // 2, sy - 44))

        self._draw_ground_items(surface, cam_x, cam_y)

    def _draw_ground_items(self, surface, cam_x, cam_y):
        from items import ITEMS
        sp = self.player
        for gi in self.ground_items:
            if gi["picked_up"]:
                continue
            ix, iy = gi["pos"]
            sx = int(ix - cam_x)
            sy = int(iy - cam_y)
            item  = ITEMS[gi["key"]]
            puls  = 0.5 + 0.5 * math.sin(self.tick * 0.10)
            r     = int(7 + puls * 2)
            gs    = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            kl    = item["color"]
            pygame.draw.circle(gs, (*kl, int(80 + puls * 60)), (r + 2, r + 2), r)
            surface.blit(gs, (sx - r - 2, sy - r - 2))
            pygame.draw.circle(surface, kl, (sx, sy), 5)
            # Pickup prompt when nearby
            is_nearby = (self.nearby_ground_item is gi)
            if is_nearby:
                t = self.font_s.render(f"[F]  {item['name']}", True, kl)
                surface.blit(t, (sx - t.get_width() // 2, sy - 28))

    def _draw_fountain(self, surface, cam_x, cam_y):
        if not self.fountain_pos:
            return
        fx, fy = self.fountain_pos
        sx   = int(fx - cam_x); sy = int(fy - cam_y)
        puls = 0.5 + 0.5 * math.sin(self.tick * 0.1)
        kl   = (int(60 + puls * 40), int(160 + puls * 60), 255)
        pygame.draw.circle(surface, (30, 80, 140), (sx, sy), 22)
        pygame.draw.circle(surface, kl, (sx, sy), 18)
        pygame.draw.circle(surface, (180, 220, 255), (sx, sy), 18, 2)
        if not self.fountain_used:
            t = self.font_s.render("Fountain  [walk here]", True, (180, 220, 255))
            surface.blit(t, (sx - t.get_width() // 2, sy - 36))

    def _draw_item_pedestal(self, surface, cam_x, cam_y):
        if not self.item_pedestal_pos or self.item_choice_active:
            return
        px, py = self.item_pedestal_pos
        sx   = int(px - cam_x); sy = int(py - cam_y)
        puls = 0.5 + 0.5 * math.sin(self.tick * 0.09)
        pygame.draw.rect(surface, (100, 85, 70), (sx - 18, sy - 10, 36, 20))
        pygame.draw.rect(surface, (140, 120, 95), (sx - 18, sy - 10, 36, 20), 2)
        pygame.draw.circle(surface, (255, int(180 + puls * 60), 50),
                           (sx, sy - 18), int(10 + puls * 3))
        t = self.font_s.render("Item  [walk here]", True, (255, 220, 120))
        surface.blit(t, (sx - t.get_width() // 2, sy - 42))

    def _draw_floor_portal(self, surface, cam_x, cam_y):
        if not self.floor_portal_open:
            return
        cx   = self.map_w  // 2 * TILE + TILE // 2
        cy   = self.map_h // 2 * TILE + TILE // 2
        sx   = int(cx - cam_x); sy = int(cy - cam_y)
        puls = 0.5 + 0.5 * math.sin(self.tick * 0.1)
        r    = int(28 + puls * 8)
        gs   = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
        pygame.draw.circle(gs, (80, 200, 255, int(100 + puls * 80)),
                           (r + 4, r + 4), r)
        surface.blit(gs, (sx - r - 4, sy - r - 4))
        pygame.draw.circle(surface, (120, 220, 255), (sx, sy), 22)
        pygame.draw.circle(surface, (200, 240, 255), (sx, sy), 22, 3)
        t = self.font_s.render("Next floor  [walk here]", True, (200, 240, 255))
        surface.blit(t, (sx - t.get_width() // 2, sy - 42))

    # ── Enemy death (forest-specific particles) ─────────────────────────────

    def _on_enemy_death(self, enemy):
        is_wolf = enemy.type == "wolf"
        is_boss = enemy.type == "boss"

        if is_wolf:
            kl = (200, 170, 80)
            self.particles.death_explosion(enemy.x, enemy.y, kl)
            for _ in range(8):
                angle = random.uniform(math.pi * 0.3, math.pi * 0.7)
                speed = random.uniform(4.0, 9.0)
                self.particles.particles.append(
                    _fx.Particle(enemy.x, enemy.y,
                                 math.cos(angle) * speed, math.sin(angle) * speed,
                                 (220, 200, 120), lifetime=18, radius=5, gravity=0.3))
        elif is_boss:
            self.particles.death_explosion(enemy.x, enemy.y, (55, 90, 45))
            self.particles.death_explosion(enemy.x, enemy.y, (255, 200, 50))
        else:
            self.particles.death_explosion(enemy.x, enemy.y, (220, 80, 80))

        self.shake.start(14 if is_boss else 8 if is_wolf else 6,
                         20 if is_boss else 14)
        self.freeze.start(6 if is_boss else 4 if is_wolf else 3)
        if is_boss or is_wolf:
            self._camera_punch(1.08 if is_boss else 1.04)
        sound.play("boss_death" if is_boss else "enemy_death")

        if self.player.has_item("bloodthirst"):
            heal = 8
            self.player.hp = min(self.player.hp_max, self.player.hp + heal)
            self.damage_numbers.add(self.player.x, self.player.y - 30,
                                    f"+{heal}", color_override=True,
                                    override_color=(80, 255, 120))
        if enemy in self.enemies:
            self.enemies.remove(enemy)
