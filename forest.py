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
        rescued = self.save.get("npcs_rescued", [])
        killed  = self.save.get("npcs_killed",  [])
        npc_key = None
        edric_done   = "edric"  in rescued or "edric"  in killed
        corvin_done  = "corvin" in rescued or "corvin" in killed
        if self.level_mgr.floor_num >= 2 and not edric_done:
            npc_key = "edric"
        elif self.level_mgr.floor_num >= 3 and edric_done and not corvin_done:
            npc_key = "corvin"
        self.floor_graph, self.start_pos = generate_floor_graph(self.level_mgr.floor_num, npc_key=npc_key)
        self.current_pos = self.start_pos
        for i, (pos, room) in enumerate(self.floor_graph.items()):
            seed      = abs(hash((pos, self.level_mgr.floor_num, i))) % 99999
            rng_state = random.getstate()
            random.seed(seed)
            rw, rh = ROOM_SIZES.get(room.get("size", "medium"), (MAP_WIDTH, MAP_HEIGHT))
            if room["type"] == "boss":
                kd = generate_arena(room["doors"], width=rw, height=rh)
            else:
                clear = room["type"] in ("rest", "npc")
                kd = generate_forest(room["doors"], width=rw, height=rh, clear_center=clear)
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

    def _draw_ground_items(self, surface, cam_x, cam_y):
        from items import ITEMS
        # Draw chest (behind items)
        if self.chest:
            cx, cy   = self.chest["pos"]
            sx       = int(cx - cam_x)
            sy       = int(cy - cam_y)
            opened   = self.chest["opened"]
            is_iron  = self.chest["type"] == "iron"
            if is_iron:
                body_kl = (85, 100, 115)
                lid_kl  = (110, 125, 140)
                rim_kl  = (160, 170, 180)
                clasp_kl = (190, 195, 200)
            else:
                body_kl = (140, 85, 30)
                lid_kl  = (175, 115, 45)
                rim_kl  = (100, 60, 20)
                clasp_kl = (210, 165, 35)

            bw, bh = 24, 10   # body width/height
            lh     = 9        # lid height

            if opened:
                # Open chest: body + lid leaning back
                pygame.draw.rect(surface, body_kl, (sx - bw//2, sy - bh//2, bw, bh))
                pygame.draw.rect(surface, rim_kl,  (sx - bw//2, sy - bh//2, bw, bh), 2)
                # Lid drawn flat/tilted above
                pygame.draw.rect(surface, lid_kl,  (sx - bw//2, sy - bh//2 - lh - 2, bw, 5))
                pygame.draw.rect(surface, rim_kl,  (sx - bw//2, sy - bh//2 - lh - 2, bw, 5), 1)
            else:
                # Closed chest: body + lid on top
                pygame.draw.rect(surface, lid_kl,  (sx - bw//2, sy - bh//2 - lh, bw, lh))
                pygame.draw.rect(surface, body_kl, (sx - bw//2, sy - bh//2,       bw, bh))
                pygame.draw.rect(surface, rim_kl,  (sx - bw//2, sy - bh//2 - lh, bw, lh + bh), 2)
                # Clasp
                pygame.draw.circle(surface, clasp_kl, (sx, sy - bh//2), 3)
                pygame.draw.circle(surface, rim_kl,   (sx, sy - bh//2), 3, 1)
                if self.nearby_chest:
                    label = f"[F]  {'Iron' if is_iron else 'Wooden'} Chest"
                    t = self.font_s.render(label, True, clasp_kl)
                    surface.blit(t, (sx - t.get_width() // 2, sy - bh//2 - lh - 20))

        for gi in self.ground_items:
            if gi["picked_up"]:
                continue
            ix, iy = gi["pos"]
            sx = int(ix - cam_x)
            sy = int(iy - cam_y)
            puls = 0.5 + 0.5 * math.sin(self.tick * 0.10)
            is_nearby = (self.nearby_ground_item is gi)

            if gi["key"] == "gold_bag":
                # Draw a small coin bag: rounded body + knot on top
                kl  = (220, 185, 55)
                kl2 = (255, 220, 80)
                bob = int(puls * 2)  # gentle bob
                # Glow
                gr = int(11 + puls * 3)
                gs = pygame.Surface((gr * 2 + 4, gr * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(gs, (*kl, int(50 + puls * 40)), (gr + 2, gr + 2), gr)
                surface.blit(gs, (sx - gr - 2, sy - gr - 2 - bob))
                # Bag body
                pygame.draw.ellipse(surface, kl,  (sx - 7, sy - 6 - bob, 14, 12))
                pygame.draw.ellipse(surface, kl2, (sx - 5, sy - 5 - bob, 10,  8))
                # Knot
                pygame.draw.circle(surface, kl,  (sx, sy - 10 - bob), 3)
                pygame.draw.circle(surface, kl2, (sx, sy - 10 - bob), 2)
                if is_nearby:
                    amount = gi.get("amount", 0)
                    t = self.font_s.render(f"[F]  {amount}g", True, kl2)
                    surface.blit(t, (sx - t.get_width() // 2, sy - 30 - bob))
            else:
                item  = ITEMS[gi["key"]]
                r     = int(7 + puls * 2)
                gs    = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
                kl    = item["color"]
                pygame.draw.circle(gs, (*kl, int(80 + puls * 60)), (r + 2, r + 2), r)
                surface.blit(gs, (sx - r - 2, sy - r - 2))
                pygame.draw.circle(surface, kl, (sx, sy), 5)
                if is_nearby:
                    t = self.font_s.render(f"[F]  {item['name']}", True, kl)
                    surface.blit(t, (sx - t.get_width() // 2, sy - 28))

    def _draw_npc_room_objects(self, surface, cam_x, cam_y):
        if not self.npc_cage_pos:
            return
        room = self.floor_graph.get(self.current_pos, {})
        if room.get("type") != "npc":
            return

        cx, cy    = self.npc_cage_pos
        sx        = int(cx - cam_x)
        sy        = int(cy - cam_y)
        npc_state = room.get("npc_state", "caged")
        cw, ch    = 88, 64
        ox = sx - cw // 2
        oy = sy - ch // 2

        pygame.draw.rect(surface, (35, 28, 22), (ox, oy, cw, ch))
        bar_col = (82, 80, 72)

        if npc_state == "caged":
            pygame.draw.rect(surface, bar_col, (ox - 3, oy - 4, cw + 6, 8))
            pygame.draw.rect(surface, bar_col, (ox - 3, oy + ch - 4, cw + 6, 8))
            pygame.draw.rect(surface, bar_col, (ox - 3, oy + ch // 2 - 2, cw + 6, 4))
            for i in range(7):
                bx = ox + int(i * cw / 6)
                pygame.draw.rect(surface, bar_col, (bx - 2, oy - 4, 4, ch + 8))
        elif npc_state == "cage_open":
            pygame.draw.rect(surface, bar_col, (ox - 3, oy - 4, cw + 6, 8))
            pygame.draw.rect(surface, bar_col, (ox - 3, oy + ch - 4, cw + 6, 8))
            for i in range(4):
                bx = ox + int(i * (cw * 0.55) / 3)
                pygame.draw.rect(surface, bar_col, (bx - 2, oy - 4, 4, ch + 8))

        npc_key = room.get("npc_key", "edric")
        if npc_state not in ("rescued", "killed"):
            ex = sx - 8 if npc_state == "caged" else sx + cw // 2 + 22
            ey = sy
            if npc_key == "corvin":
                # Corvin: darker skin, greenish jacket
                pygame.draw.circle(surface, (55, 70, 50),    (ex, ey),      14)
                pygame.draw.circle(surface, (140, 115, 85),  (ex, ey - 10),  7)
                t = self.font_s.render("Corvin", True, (160, 200, 140))
            else:
                pygame.draw.circle(surface, (75, 62, 48),    (ex, ey),      14)
                pygame.draw.circle(surface, (180, 148, 100), (ex, ey - 10),  7)
                t = self.font_s.render("Edric", True, (200, 175, 120))
            surface.blit(t, (ex - t.get_width() // 2, ey - 30))

        sp   = self.player
        dist = math.hypot(sp.x - cx, sp.y - cy)
        if dist < 75 and npc_state not in ("rescued", "killed"):
            if npc_key == "corvin":
                prompt = "[F] Talk to Corvin"
                kl     = (160, 200, 140)
            else:
                has_key = "rusted_key" in self.save.get("items", [])
                if npc_state == "caged":
                    prompt = "[F] Open cage" if has_key else "[F] Talk"
                    kl     = (215, 195, 100) if has_key else (160, 155, 135)
                else:
                    prompt = "[F] Talk to Edric"
                    kl     = (215, 195, 100)
            t = self.font_s.render(prompt, True, kl)
            surface.blit(t, (sx - t.get_width() // 2, oy - 30))

    def _handle_npc_interaction(self, room):
        if room.get("npc_key") == "edric":
            self._handle_edric_interaction(room)
        elif room.get("npc_key") == "corvin":
            self._handle_corvin_interaction(room)

    def _handle_edric_interaction(self, room):
        if not self.npc_cage_pos:
            return
        sp     = self.player
        cx, cy = self.npc_cage_pos
        dist   = math.hypot(sp.x - cx, sp.y - cy)
        if dist > 75:
            return
        npc_state = room.get("npc_state", "caged")
        if npc_state in ("rescued", "killed"):
            return
        has_key = "rusted_key" in self.save.get("items", [])

        if npc_state == "caged":
            if has_key:
                self.save["items"].remove("rusted_key")
                room["npc_state"] = "cage_open"
                self._start_dialogue(
                    "Edric",
                    [
                        "There's a fort not far. Used to mean something.",
                        "I'll find my way.",
                    ],
                    choices=[
                        {"text": "Send him to the fort", "action": lambda: self._edric_rescue(room)},
                        {"text": "Attack",               "action": lambda: self._edric_kill(room)},
                    ]
                )
            else:
                if not room.get("npc_talked"):
                    room["npc_talked"] = True
                    self._start_dialogue(
                        "Edric",
                        [
                            "You're not one of theirs. I can see that much.",
                            "There's a man. Calls himself the Iron Warden.",
                            "He has the key to this cage. Find him, and you find it.",
                            "What you do with me after that is your own business.",
                        ]
                    )
                else:
                    self._start_dialogue(
                        "Edric",
                        ["Find the Warden. He has the key."]
                    )
        elif npc_state == "cage_open" and not self.dialogue:
            self._start_dialogue(
                "Edric",
                ["Well. What is it going to be?"],
                choices=[
                    {"text": "Send him to the fort", "action": lambda: self._edric_rescue(room)},
                    {"text": "Attack",               "action": lambda: self._edric_kill(room)},
                ]
            )

    def _handle_corvin_interaction(self, room):
        if not self.npc_cage_pos:
            return
        sp     = self.player
        cx, cy = self.npc_cage_pos
        if math.hypot(sp.x - cx, sp.y - cy) > 75:
            return
        npc_state = room.get("npc_state", "caged")
        if npc_state in ("rescued", "killed"):
            return
        if npc_state == "caged":
            if not room.get("npc_talked"):
                room["npc_talked"] = True
                self._start_dialogue(
                    "Corvin",
                    [
                        "You're not one of theirs. Good.",
                        "I don't need much. Just need the door open.",
                        "I can be useful. There's a fort nearby, yeah?",
                    ],
                    choices=[
                        {"text": "Open the cage",  "action": lambda: self._corvin_rescue(room)},
                        {"text": "Walk away",       "action": None},
                    ]
                )
            else:
                self._start_dialogue(
                    "Corvin",
                    ["Still here. The offer stands."],
                    choices=[
                        {"text": "Open the cage",  "action": lambda: self._corvin_rescue(room)},
                        {"text": "Walk away",       "action": None},
                    ]
                )

    def _corvin_rescue(self, room):
        room["npc_state"] = "rescued"
        self.save.setdefault("npcs_rescued", []).append("corvin")
        sound.play("level_up")

    def _edric_rescue(self, room):
        room["npc_state"] = "rescued"
        self.save.setdefault("npcs_rescued", []).append("edric")
        sound.play("level_up")

    def _edric_kill(self, room):
        room["npc_state"] = "killed"
        self.save.setdefault("npcs_killed", []).append("edric")
        cx, cy = self.npc_cage_pos
        self.ground_items.append({
            "pos":       (cx + 25, cy + 15),
            "key":       "edrics_chain",
            "picked_up": False,
        })

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

        if enemy.type == "iron_warden":
            self.particles.death_explosion(enemy.x, enemy.y, (80, 80, 90))
            self.particles.death_explosion(enemy.x, enemy.y, (160, 150, 120))
            self.shake.start(10, 16)
            self.freeze.start(4)
            self._camera_punch(1.05)
            sound.play("enemy_death")
            if enemy in self.enemies:
                self.enemies.remove(enemy)
            return

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
