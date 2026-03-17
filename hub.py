# hub.py - Castle courtyard (hub world)
import math, pygame
from constants import *
from weapons import WEAPONS

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

EXIT_TILES  = [(x, 17) for x in range(10, 14)]
EDRIC_POS          = (4 * TILE + TILE // 2,  4 * TILE + TILE // 2)
CORVIN_POS         = (13 * TILE + TILE // 2, 7 * TILE + TILE // 2)  # grass area (merchant)

SHIELD_COST        = 60
UPGRADE_COSTS      = {1: 120, 2: 320, 3: 750}   # cost to reach that tier
CORVIN_UPGRADE_COSTS = {1: 170, 2: 450}           # +40%, max tier 2
CORVIN_CONSUMABLES = [
    {"key": "health_potion", "label": "Health Potion  —  25g",  "cost": 25},
    {"key": "fire_potion",   "label": "Fire Potion    —  35g",  "cost": 35},
]


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
        self.welcome_timer  = 3 * FPS if save.get("highest_floor", 0) > 0 else 0
        self.tick           = 0
        self.shop_active    = False
        self.shop_cursor    = 0
        self.shop_msg       = ""
        self.shop_msg_timer = 0

    def get_tile(self, tx, ty):
        if 0 <= tx < HUB_W and 0 <= ty < HUB_H:
            return self.tilemap[ty][tx]
        return WALL

    def is_blocked(self, tx, ty):
        return self.get_tile(tx, ty) == WALL

    def at_exit(self):
        return int(self.player_y // TILE) >= HUB_H - 1

    def _edric_present(self):
        return "edric" in self.save.get("npcs_rescued", [])

    def _near_edric(self):
        return math.hypot(self.player_x - EDRIC_POS[0],
                          self.player_y - EDRIC_POS[1]) < 60

    def _corvin_present(self):
        return "corvin" in self.save.get("npcs_rescued", [])

    def _corvin_at_forge(self):
        """Corvin runs the forge when Edric is dead."""
        return (self._corvin_present()
                and "edric" in self.save.get("npcs_killed", []))

    def _corvin_as_merchant(self):
        """Corvin is a traveling merchant when Edric is alive in the hub."""
        return (self._corvin_present()
                and "edric" in self.save.get("npcs_rescued", []))

    def _corvin_pos(self):
        return EDRIC_POS if self._corvin_at_forge() else CORVIN_POS

    def _near_corvin(self):
        pos = self._corvin_pos()
        return math.hypot(self.player_x - pos[0], self.player_y - pos[1]) < 60

    def _build_shop_items(self):
        """Return list of shop option dicts."""
        items    = []
        shields  = self.save.get("inventory_shields", [])
        weapon   = self.save.get("main_hand", "sword")
        upgrades = self.save.get("weapon_upgrades", {})
        tier     = upgrades.get(weapon, 0)
        gold     = self.save.get("gold", 0)
        wname    = WEAPONS.get(weapon, {}).get("name", weapon.capitalize())

        if "wooden_shield" not in shields:
            items.append({
                "label":      f"Wooden Shield  —  {SHIELD_COST}g",
                "affordable": gold >= SHIELD_COST,
                "action":     "buy_shield",
            })
        if tier < 3:
            next_tier = tier + 1
            cost      = UPGRADE_COSTS[next_tier]
            items.append({
                "label":      f"Upgrade {wname} to +{next_tier}  —  {cost}g",
                "affordable": gold >= cost,
                "action":     f"upgrade_{next_tier}",
            })
        if not items:
            items.append({
                "label":      "Nothing left to offer.",
                "affordable": False,
                "action":     None,
            })
        return items

    def _build_corvin_shop(self):
        gold  = self.save.get("gold", 0)
        items = []
        if self._corvin_as_merchant():
            for c in CORVIN_CONSUMABLES:
                items.append({
                    "label":      c["label"],
                    "affordable": gold >= c["cost"],
                    "action":     f"buy_{c['key']}",
                    "cost":       c["cost"],
                    "key":        c["key"],
                })
        elif self._corvin_at_forge():
            weapon   = self.save.get("main_hand", "sword")
            upgrades = self.save.get("weapon_upgrades", {})
            tier     = upgrades.get(weapon, 0)
            wname    = WEAPONS.get(weapon, {}).get("name", weapon.capitalize())
            if tier < 2:
                next_tier = tier + 1
                cost      = CORVIN_UPGRADE_COSTS[next_tier]
                items.append({
                    "label":      f"Upgrade {wname} to +{next_tier}  —  {cost}g",
                    "affordable": gold >= cost,
                    "action":     f"upgrade_{next_tier}",
                })
            else:
                items.append({"label": "That's the best I can do.",
                               "affordable": False, "action": None})
        if not items:
            items.append({"label": "Nothing for you today.",
                          "affordable": False, "action": None})
        return items

    def _corvin_shop_confirm(self, shop_items):
        if self.shop_cursor >= len(shop_items):
            return
        item = shop_items[self.shop_cursor]
        if not item["affordable"] or not item["action"]:
            self.shop_msg = "Not enough gold."
            self.shop_msg_timer = 90
            return
        gold   = self.save.get("gold", 0)
        action = item["action"]
        if action.startswith("buy_"):
            key  = action[4:]
            cost = item["cost"]
            self.save["gold"] = gold - cost
            inv     = self.save.setdefault("items", [])
            charges = self.save.setdefault("item_charges", {})
            from items import ITEMS
            if key not in inv:
                inv.append(key)
                charges[key] = ITEMS[key].get("charges", 1)
            else:
                charges[key] = charges.get(key, 0) + ITEMS[key].get("charges", 1)
            self.shop_msg = f"Bought {ITEMS[key]['name']}."
        elif action.startswith("upgrade_"):
            tier   = int(action.split("_")[1])
            cost   = CORVIN_UPGRADE_COSTS[tier]
            self.save["gold"] = gold - cost
            weapon = self.save.get("main_hand", "sword")
            self.save.setdefault("weapon_upgrades", {})[weapon] = tier
            self.shop_msg = f"Weapon upgraded to +{tier}."
        self.shop_msg_timer = 120

    def _shop_confirm(self, shop_items):
        if self.shop_cursor >= len(shop_items):
            return
        item = shop_items[self.shop_cursor]
        if not item["affordable"] or not item["action"]:
            self.shop_msg       = "Not enough gold."
            self.shop_msg_timer = 90
            return
        gold   = self.save.get("gold", 0)
        action = item["action"]
        if action == "buy_shield":
            self.save["gold"] = gold - SHIELD_COST
            self.save.setdefault("inventory_shields", []).append("wooden_shield")
            self.shop_msg = "Shield added to inventory."
        elif action.startswith("upgrade_"):
            tier = int(action.split("_")[1])
            cost = UPGRADE_COSTS[tier]
            self.save["gold"] = gold - cost
            weapon = self.save.get("main_hand", "sword")
            self.save.setdefault("weapon_upgrades", {})[weapon] = tier
            self.shop_msg = f"Weapon upgraded to +{tier}."
        self.shop_msg_timer = 120

    def run(self):
        while True:
            self.clock.tick(FPS)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return "quit"
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        if self.shop_active:
                            self.shop_active = False
                        else:
                            return "quit"
                    if self.shop_active:
                        shop_items = self._build_shop_items()
                        if e.key == pygame.K_UP:
                            self.shop_cursor = max(0, self.shop_cursor - 1)
                        elif e.key == pygame.K_DOWN:
                            self.shop_cursor = min(len(shop_items) - 1,
                                                   self.shop_cursor + 1)
                        elif e.key in (pygame.K_f, pygame.K_RETURN, pygame.K_KP_ENTER):
                            if getattr(self, "shop_npc", "edric") == "corvin":
                                self._corvin_shop_confirm(self._build_corvin_shop())
                            else:
                                self._shop_confirm(shop_items)
                    elif e.key == pygame.K_f:
                        if self._edric_present() and self._near_edric():
                            self.shop_active = True
                            self.shop_cursor = 0
                            self.shop_npc    = "edric"
                        elif self._corvin_present() and self._near_corvin():
                            self.shop_active = True
                            self.shop_cursor = 0
                            self.shop_npc    = "corvin"

            self.tick += 1
            if self.shop_msg_timer > 0:
                self.shop_msg_timer -= 1

            keys = pygame.key.get_pressed()
            mx, my = 0.0, 0.0
            if not self.shop_active:
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

        # Forge (always visible)
        fx_w = int(EDRIC_POS[0] - cam_x)
        fy_w = int(EDRIC_POS[1] - cam_y) - 28
        pygame.draw.rect(self.screen, (55, 45, 38), (fx_w - 20, fy_w - 12, 40, 24))
        pygame.draw.rect(self.screen, (80, 70, 60), (fx_w - 20, fy_w - 12, 40, 24), 2)
        puls = 0.5 + 0.5 * math.sin(self.tick * 0.10)
        glow = pygame.Surface((28, 14), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255, int(100 + puls * 80), 0, int(80 + puls * 60)),
                            (0, 0, 28, 14))
        self.screen.blit(glow, (fx_w - 14, fy_w - 8))

        # Edric NPC
        if self._edric_present():
            ex = int(EDRIC_POS[0] - cam_x)
            ey = int(EDRIC_POS[1] - cam_y)
            pygame.draw.ellipse(self.screen, C_SHADOW, (ex - 11, ey + 9, 22, 11))
            pygame.draw.circle(self.screen, (75, 62, 48),    (ex, ey),      14)
            pygame.draw.circle(self.screen, (180, 148, 100), (ex, ey - 10),  7)
            t = self.font_s.render("Edric", True, (200, 175, 120))
            self.screen.blit(t, (ex - t.get_width() // 2, ey - 30))
            if self._near_edric() and not self.shop_active:
                t = self.font_s.render("[F] Trade", True, (215, 195, 100))
                self.screen.blit(t, (ex - t.get_width() // 2, ey - 46))

        # Corvin NPC
        if self._corvin_present():
            cpos = self._corvin_pos()
            cvx  = int(cpos[0] - cam_x)
            cvy  = int(cpos[1] - cam_y)
            pygame.draw.ellipse(self.screen, C_SHADOW, (cvx - 11, cvy + 9, 22, 11))
            pygame.draw.circle(self.screen, (55, 70, 50),    (cvx, cvy),      14)
            pygame.draw.circle(self.screen, (140, 115, 85),  (cvx, cvy - 10),  7)
            label = "Corvin"
            kl    = (160, 200, 140)
            t = self.font_s.render(label, True, kl)
            self.screen.blit(t, (cvx - t.get_width() // 2, cvy - 30))
            if self._near_corvin() and not self.shop_active:
                if self._corvin_at_forge():
                    prompt = "[F] Forge"
                else:
                    prompt = "[F] Trade"
                t = self.font_s.render(prompt, True, kl)
                self.screen.blit(t, (cvx - t.get_width() // 2, cvy - 46))

        # Player
        ssx = int(self.player_x - cam_x)
        ssy = int(self.player_y - cam_y)
        pygame.draw.ellipse(self.screen, C_SHADOW, (ssx - 11, ssy + 9, 22, 11))
        pygame.draw.circle(self.screen, C_PLAYER, (ssx, ssy), 15)
        pygame.draw.circle(self.screen, C_EYE,
            (int(ssx + self.fx * 9), int(ssy + self.fy * 9)), 5)

        self.draw_hud()
        if self.shop_active:
            self.draw_shop()

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
        xp   = self.save.get("exp",  0)
        gold = self.save.get("gold", 0)
        t = self.font_s.render(f"XP  {xp:,}", True, (190, 160, 55))
        self.screen.blit(t, (10, SCREEN_H - 42))
        t = self.font_s.render(f"G   {gold:,}", True, (220, 185, 55))
        self.screen.blit(t, (10, SCREEN_H - 24))

    def draw_shop(self):
        npc = getattr(self, "shop_npc", "edric")
        if npc == "corvin":
            shop_items = self._build_corvin_shop()
            if self._corvin_at_forge():
                title = "Corvin's Forge"
                title_kl = (160, 200, 140)
            else:
                title = "Corvin — Traveling Merchant"
                title_kl = (160, 200, 140)
        else:
            shop_items = self._build_shop_items()
            title      = "Edric's Forge"
            title_kl   = (220, 185, 100)

        bx, by = SCREEN_W // 2 - 220, SCREEN_H // 2 - 120
        bw, bh = 440, 240
        bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
        bg.fill((10, 10, 15, 220))
        self.screen.blit(bg, (bx, by))
        rim_kl = (80, 110, 80) if npc == "corvin" else (100, 90, 70)
        pygame.draw.rect(self.screen, rim_kl, (bx, by, bw, bh), 2)

        t = self.font_m.render(title, True, title_kl)
        self.screen.blit(t, (bx + bw // 2 - t.get_width() // 2, by + 10))

        for i, item in enumerate(shop_items):
            selected = (i == self.shop_cursor)
            kl = (title_kl if selected and item["affordable"] else
                  (120, 100, 60) if not item["affordable"] else
                  (180, 175, 160))
            prefix = "► " if selected else "  "
            t = self.font_s.render(prefix + item["label"], True, kl)
            self.screen.blit(t, (bx + 20, by + 48 + i * 28))

        if self.shop_msg_timer > 0:
            t = self.font_s.render(self.shop_msg, True, (160, 220, 140))
            self.screen.blit(t, (bx + 20, by + bh - 36))

        t = self.font_s.render("↑↓ navigate   [F] buy   [Esc] close",
                               True, (120, 115, 100))
        self.screen.blit(t, (bx + 20, by + bh - 20))