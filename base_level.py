# base_level.py - Shared level logic for all level types
# Subclass this and implement the abstract methods to create a new level.
import math, random, pygame
from constants import *
from entities import Player, Enemy, Boss, Arrow, normalize, angle_diff
from effects import ScreenShake, FreezeFrames, ParticleSystem, DamageNumberSystem, HitFlash
from level_manager import LevelManager, generate_floor_graph, OPPOSITE
from items import ITEMS, RARITY_COLOR, RARITY_NAME, pick_items
import sound


def pulse_color(base, highlight, t, speed=0.08):
    f = (math.sin(t * speed) + 1) / 2
    return tuple(int(base[i] + (highlight[i] - base[i]) * f) for i in range(3))


class BaseLevel:
    """Base class for all levels. Override the abstract methods for level-specific behavior."""

    def __init__(self, screen, clock, save):
        self.screen    = screen
        self.clock     = clock
        self.save      = save
        self.level_mgr = LevelManager()
        self.font_s    = pygame.font.SysFont("monospace", 15)
        self.font_m    = pygame.font.SysFont("monospace", 22)
        self.font_g    = pygame.font.SysFont("monospace", 52, bold=True)
        self.tick      = 0
        self.player    = None
        self.cam_zoom        = 1.0
        self.cam_zoom_target = 1.0
        self._generate_floor(first=True)

    # ═════════════════════════════════════════════════════════════════════════
    #  ABSTRACT — subclass MUST implement these
    # ═════════════════════════════════════════════════════════════════════════

    def _generate_floor(self, first=True):
        """Generate the floor graph and load the first room."""
        raise NotImplementedError

    def _spawn_group(self, e_type, count, hp_mult, damage_mult):
        """Spawn a group of enemies using level-specific placement logic."""
        raise NotImplementedError

    def is_blocked(self, tx, ty):
        """Return True if tile (tx, ty) blocks movement."""
        raise NotImplementedError

    def _draw_tiles(self, surface, cam_x, cam_y):
        """Draw the level-specific terrain tiles."""
        raise NotImplementedError

    def _draw_decorations(self, surface, cam_x, cam_y):
        """Draw level-specific decorations (trees, campfires, etc.)."""
        raise NotImplementedError

    def _draw_rest_room_objects(self, surface, cam_x, cam_y):
        """Draw fountain, item pedestal, floor portal, etc."""
        raise NotImplementedError

    def _on_enemy_death(self, enemy):
        """Handle enemy death with level-specific particles and effects."""
        raise NotImplementedError

    # ═════════════════════════════════════════════════════════════════════════
    #  ROOM LOADING — mostly generic, calls abstract _generate_floor
    # ═════════════════════════════════════════════════════════════════════════

    def _load_room(self, grid_pos, direction=None, first=False):
        self.current_pos = grid_pos
        room = self.floor_graph[grid_pos]
        room["visited"] = True
        self._unpack_map_data(room)

        if direction is None:
            entry = "W" if "W" in self._spawn_positions else list(self._spawn_positions.keys())[0]
        else:
            entry = OPPOSITE[direction]
            if entry not in self._spawn_positions:
                entry = list(self._spawn_positions.keys())[0]
        stx, sty = self._spawn_positions[entry]
        sp_x = stx * TILE + TILE // 2
        sp_y = sty * TILE + TILE // 2

        if first:
            self.player = Player(sp_x, sp_y, self.save)
            self.cam_x  = float(sp_x - SCREEN_W / 2)
            self.cam_y  = float(sp_y - SCREEN_H / 2)
        else:
            self.player.x = float(sp_x)
            self.player.y = float(sp_y)
            self.player.dodge_timer     = 0
            self.player.dodge_cooldown  = 0
            self.player.flinch_cooldown = 0

        self.arrows             = []
        self.shake              = ScreenShake()
        self.freeze             = FreezeFrames()
        self.particles          = ParticleSystem()
        self.damage_numbers     = DamageNumberSystem()
        self.flash              = HitFlash()
        self.dodge_trail_timer  = 0
        self.transition_timer   = 0
        self._pending_room      = None
        self.room_intro_timer   = 2 * FPS
        self.floor_portal_open  = False
        self.cam_zoom           = 1.0
        self.cam_zoom_target    = 1.0

        self.level_mgr.room_type = room["type"]

        self.enemies            = []
        self.boss               = None
        self.campfire_positions = []
        self.equip_menu_active  = False
        self.equip_cursor       = 0

        if not room["cleared"]:
            for group in room["enemy_config"]:
                e_type, count, hp_mult = group
                if e_type == "boss":
                    cx = self.map_w // 2 * TILE + TILE // 2
                    cy = self.map_h // 2 * TILE + TILE // 2
                    self.boss = Boss(cx, cy, damage_mult=hp_mult)
                else:
                    self._spawn_group(e_type, count, hp_mult, room["damage_mult"])
        else:
            self.floor_portal_open = (room["type"] == "boss")

        self.fountain_pos       = None
        self.fountain_used      = room.get("fountain_used", False)
        self.item_pedestal_pos  = None
        self.item_choice_active = False
        self.item_choices       = []

        if room["type"] == "rest":
            fx = self.map_w // 2 * TILE + TILE // 2
            fy = self.map_h // 2 * TILE + TILE // 2
            self.fountain_pos = (fx, fy)
            if not room.get("item_taken", False):
                self.item_pedestal_pos = (fx - 100, fy)

    def _unpack_map_data(self, room):
        """Unpack map data from room dict. Override for different map formats."""
        tilemap, trees, palette_map, spawn_positions, get_tile = room["map_data"]
        self.tilemap         = tilemap
        self.trees           = trees
        self.palette_map     = palette_map
        self._spawn_positions = spawn_positions
        self.get_tile        = get_tile
        # Derive map dimensions from actual tilemap (supports variable room sizes)
        self.map_h = len(tilemap)
        self.map_w = len(tilemap[0]) if self.map_h > 0 else 26

    # ═════════════════════════════════════════════════════════════════════════
    #  MAIN LOOP
    # ═════════════════════════════════════════════════════════════════════════

    def run(self):
        while True:
            self.clock.tick(FPS)
            events = pygame.event.get()
            result = self._handle_events(events)
            if result:
                return result

            if self.freeze.update():
                self._draw()
                pygame.display.flip()
                continue

            self._update(events)
            self._draw()
            pygame.display.flip()
            self.tick += 1
            sound.update()

    # ═════════════════════════════════════════════════════════════════════════
    #  INPUT
    # ═════════════════════════════════════════════════════════════════════════

    def _handle_events(self, events):
        for e in events:
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    if self.equip_menu_active:
                        self.equip_menu_active = False
                    else:
                        return "quit"
                if e.key == pygame.K_q:
                    self._use_active_item()
                if e.key == pygame.K_TAB:
                    self.equip_menu_active = not self.equip_menu_active
                    self.equip_cursor = 0

        if self.equip_menu_active:
            self._handle_equip_events(events)
            return None

        if self.item_choice_active:
            for e in events:
                if e.type == pygame.KEYDOWN:
                    if e.key in (pygame.K_1, pygame.K_KP1) and len(self.item_choices) >= 1:
                        self._take_item(self.item_choices[0])
                    elif e.key in (pygame.K_2, pygame.K_KP2) and len(self.item_choices) >= 2:
                        self._take_item(self.item_choices[1])
                    elif e.key in (pygame.K_3, pygame.K_KP3) and len(self.item_choices) >= 3:
                        self._take_item(self.item_choices[2])
        return None

    def _use_active_item(self):
        items   = self.save.get("items", [])
        charges = self.save.get("item_charges", {})
        effects = self.save.get("active_effects", {})
        active_items = [k for k in items if ITEMS[k]["type"] == "active"]
        if not active_items:
            return
        key  = active_items[0]
        item = ITEMS[key]
        c    = charges.get(key, item.get("charges", 1))
        if c <= 0:
            return
        if key == "invis_potion":
            effects["invis"] = item["duration"]
        elif key == "fire_potion":
            effects["fire_potion"] = item["duration"]
        elif key == "health_potion":
            heal = item.get("heal", 35)
            self.player.hp = min(self.player.hp_max, self.player.hp + heal)
            self.damage_numbers.add(self.player.x, self.player.y - 20,
                                    f"+{heal}", color_override=True,
                                    override_color=(80, 255, 120))
            sound.play("fountain")
        charges[key] = c - 1
        self.save["item_charges"]   = charges
        self.save["active_effects"] = effects

    def _take_item(self, key):
        item    = ITEMS[key]
        items   = self.save.setdefault("items", [])
        charges = self.save.setdefault("item_charges", {})
        if item["type"] == "passive":
            if key not in items:
                items.append(key)
        else:
            if key not in items:
                items.append(key)
            charges[key] = item.get("charges", 1)
        self.item_choice_active = False
        self.item_choices       = []
        room = self.floor_graph[self.current_pos]
        room["item_taken"] = True
        self.item_pedestal_pos = None
        sound.play("level_up")

    # ── Equipment menu ───────────────────────────────────────────────────────

    def _handle_equip_events(self, events):
        for e in events:
            if e.type != pygame.KEYDOWN:
                continue
            if e.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.equip_cursor = 1 - self.equip_cursor
            if e.key in (pygame.K_1, pygame.K_KP1):
                self._equip_slot(0)
            elif e.key in (pygame.K_2, pygame.K_KP2):
                self._equip_slot(1)
            elif e.key in (pygame.K_3, pygame.K_KP3):
                self._equip_slot(2)
            elif e.key in (pygame.K_4, pygame.K_KP4):
                self._equip_slot(3)
            elif e.key in (pygame.K_5, pygame.K_KP5):
                self._equip_slot(4)
            elif e.key in (pygame.K_0, pygame.K_KP0):
                if self.equip_cursor == 1:
                    self.save["off_hand"] = None
                    sound.play("level_up")

    def _equip_slot(self, idx):
        from weapons import WEAPONS, SHIELDS
        if self.equip_cursor == 0:
            inv = self.save.get("inventory_weapons", ["sword"])
            if idx < len(inv):
                self.save["main_hand"] = inv[idx]
                sound.play("level_up")
        else:
            inv = self.save.get("inventory_shields", [])
            if idx < len(inv):
                self.save["off_hand"] = inv[idx]
                sound.play("level_up")

    def _draw_equip_menu(self):
        from weapons import WEAPONS, SHIELDS, get_weapon, get_shield, combo_length
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        t = self.font_m.render("Equipment  [Tab to close]", True, (220, 200, 120))
        self.screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 40))

        tabs = ["Weapons  [\u2190\u2192]", "Shields  [\u2190\u2192]"]
        for i, label in enumerate(tabs):
            kl = (255, 220, 100) if i == self.equip_cursor else (120, 110, 80)
            tt = self.font_s.render(label, True, kl)
            x = SCREEN_W // 2 - 120 + i * 180
            self.screen.blit(tt, (x, 72))
            if i == self.equip_cursor:
                pygame.draw.line(self.screen, kl, (x, 90), (x + tt.get_width(), 90), 2)

        if self.equip_cursor == 0:
            inv      = self.save.get("inventory_weapons", ["sword"])
            equipped = self.save.get("main_hand", "sword")
            items    = [(k, WEAPONS.get(k, {})) for k in inv]
        else:
            inv      = self.save.get("inventory_shields", [])
            equipped = self.save.get("off_hand")
            items    = [(k, SHIELDS.get(k, {})) for k in inv]

        card_w, card_h = 160, 180
        total_w = len(items) * (card_w + 16) - 16
        start_x = SCREEN_W // 2 - total_w // 2

        for i, (key, data) in enumerate(items):
            cx = start_x + i * (card_w + 16)
            cy = SCREEN_H // 2 - card_h // 2 + 20
            is_equipped = (key == equipped)

            bg_kl = (50, 50, 40) if not is_equipped else (60, 55, 35)
            pygame.draw.rect(self.screen, bg_kl,
                             (cx, cy, card_w, card_h), border_radius=8)
            border_kl = (255, 220, 80) if is_equipped else data.get("color", (140, 140, 140))
            pygame.draw.rect(self.screen, border_kl,
                             (cx, cy, card_w, card_h), 2, border_radius=8)

            if is_equipped:
                et = self.font_s.render("EQUIPPED", True, (255, 220, 80))
                self.screen.blit(et, (cx + card_w // 2 - et.get_width() // 2, cy + 8))

            icon_kl = data.get("color", (180, 180, 180))
            pygame.draw.circle(self.screen, icon_kl,
                               (cx + card_w // 2, cy + 55), 22)

            nt = self.font_m.render(data.get("name", key), True, (240, 230, 210))
            self.screen.blit(nt, (cx + card_w // 2 - nt.get_width() // 2, cy + 85))

            if self.equip_cursor == 0:
                w = get_weapon(key)
                stats = [
                    f"DMG: {w['damage']:.0f}",
                    f"Reach: {w['reach']}",
                    f"Combo: {combo_length(w)} hits",
                    f"Stam: {w['stamina_cost']}",
                ]
                if w.get("can_block"):
                    stats.append(f"Block: {w['block_stamina']:.0f} stam")
                    stats.append(f"Parry: {w['parry_window']}f")
                else:
                    stats.append("No block")
            else:
                s = get_shield(key)
                if s:
                    stats = [
                        f"Block: {s['stamina_cost']:.0f} stam",
                        f"Parry: {s['parry_window']}f window",
                    ]
                else:
                    stats = []

            for j, line in enumerate(stats):
                st = self.font_s.render(line, True, (160, 155, 140))
                self.screen.blit(st, (cx + card_w // 2 - st.get_width() // 2,
                                      cy + 112 + j * 16))

            ht = self.font_m.render(f"[{i+1}]", True, (200, 190, 140))
            self.screen.blit(ht, (cx + card_w // 2 - ht.get_width() // 2,
                                  cy + card_h - 26))

        if self.equip_cursor == 1:
            ut = self.font_s.render("[0] Unequip shield", True, (140, 130, 110))
            self.screen.blit(ut, (SCREEN_W // 2 - ut.get_width() // 2,
                                  SCREEN_H // 2 + card_h // 2 + 50))

    # ═════════════════════════════════════════════════════════════════════════
    #  UPDATE
    # ═════════════════════════════════════════════════════════════════════════

    def _update(self, events):
        sp = self.player
        if not sp.alive:
            return

        if self.equip_menu_active:
            return

        if self.transition_timer > 0:
            self.transition_timer -= 1
            if self.transition_timer == 0 and self._pending_room:
                direction, next_pos = self._pending_room
                self._pending_room  = None
                self._load_room(next_pos, direction=direction)
            return

        keys  = pygame.key.get_pressed()
        mouse = pygame.mouse.get_pos()
        block = (pygame.mouse.get_pressed()[2]
                 and sp._can_block()
                 and not sp.shield_broken
                 and sp.dodge_timer == 0
                 and sp.flinch_timer == 0)

        if not self.item_choice_active:
            sp.handle_events(events, block)
            sp.update(keys, mouse, int(self.cam_x), int(self.cam_y),
                      self.is_blocked, None, block)

        if getattr(sp, 'dodge_burst_pending', False):
            sp.dodge_burst_pending = False
            self.particles.dodge_burst(sp.x, sp.y)

        self._update_dodge_trail()
        self._update_sword_hits()
        self._update_enemies(block)
        self._update_arrows(block)
        self._update_boss(block)
        self._check_room_clear()
        self._check_door_transition()
        self._check_fountain()
        self._check_item_pedestal()
        self._update_camera()

        self.cam_zoom += (self.cam_zoom_target - self.cam_zoom) * 0.15
        if abs(self.cam_zoom - 1.0) < 0.001:
            self.cam_zoom        = 1.0
            self.cam_zoom_target = 1.0

        self.particles.update()
        self.damage_numbers.update()
        self.shake.update()

    def _update_dodge_trail(self):
        sp = self.player
        if sp.dodge_timer > 0:
            self.dodge_trail_timer -= 1
            if self.dodge_trail_timer <= 0:
                self.dodge_trail_timer = 3
                self.particles.dodge_trail(sp.x, sp.y)

    def _camera_punch(self, strength=1.06):
        self.cam_zoom_target = strength

    def _update_sword_hits(self):
        sp      = self.player
        targets = self.enemies + ([self.boss] if self.boss else [])

        # Charge hit detection
        if sp.charge_timer > 0:
            for target, damage, kb_nx, kb_ny in sp.charge_hits(targets):
                fire = sp.has_item("fire_damage") or sp.has_active_effect("fire_potion")
                dead = target.take_damage_swing(damage, kb_nx, kb_ny)
                if fire and not getattr(target, 'burning_timer', 0) > 0:
                    target.burning_timer = 360
                    target.burning_tick  = 120
                angle = math.degrees(math.atan2(kb_ny, kb_nx))
                self.particles.sword_sparks(target.x, target.y, angle)
                self.particles.blood_splatter(target.x, target.y, angle)
                self.damage_numbers.add(target.x, target.y - 20, damage)
                self.freeze.start(3)
                self.shake.start(6, 10)
                self._camera_punch(1.05)
                sound.play("sword_hit")
                if dead:
                    self._on_enemy_death(target)
            return

        # Normal swing hit detection
        hits = sp.sword_hits(targets)

        from weapons import combo_step_data as _csd
        cur_swing = _csd(sp._weapon(), max(1, sp.combo_step))["swing_frames"] if sp.combo_step > 0 else 10
        if not hits and sp.combo_timer > 0 and sp.combo_timer == cur_swing - 1:
            sound.play("sword_miss")

        from weapons import is_finisher as _is_fin, combo_step_data as _csd2
        step_data = _csd2(sp._weapon(), max(1, sp.combo_step))
        hs = step_data.get("hitstop", 2)
        ss = step_data.get("shake_strength", 4)
        sd = step_data.get("shake_duration", 8)
        h_sq = step_data.get("hit_squash")

        for target, damage, kb_nx, kb_ny in hits:
            fire = sp.has_item("fire_damage") or sp.has_active_effect("fire_potion")
            dead = target.take_damage_swing(damage, kb_nx, kb_ny, hitstop=hs, hit_squash=h_sq)
            if fire and not getattr(target, 'burning_timer', 0) > 0:
                target.burning_timer = 360
                target.burning_tick  = 120
            angle = math.degrees(math.atan2(kb_ny, kb_nx))
            self.particles.sword_sparks(target.x, target.y, angle)
            self.particles.blood_splatter(target.x, target.y, angle)
            self.damage_numbers.add(target.x, target.y - 20, damage)

            hit_is_finisher = (_is_fin(sp._weapon(), sp.combo_step) and not sp.is_dash_strike)
            is_boss_target  = target.type == "boss"

            if is_boss_target:
                self.freeze.start(max(hs, 6))
                self.shake.start(max(ss, 7), sd)
                self._camera_punch(1.05)
            else:
                self.freeze.start(hs)
                self.shake.start(ss, sd)
            if hit_is_finisher:
                self._camera_punch(1.07)

            sound.play("sword_hit")
            if dead:
                self._on_enemy_death(target)

    def _update_enemies(self, block):
        sp   = self.player
        fh   = math.degrees(math.atan2(sp.fy, sp.fx))
        dead = []
        # Group aggro — if one wakes, wake all in same group
        newly_aggroed = set()
        for e in self.enemies:
            if not e.aggro:
                dist = math.hypot(sp.x - e.x, sp.y - e.y)
                if dist < e.aggro_range or e.flinch_timer > 0:
                    newly_aggroed.add(e.group_id)
        if newly_aggroed:
            for e in self.enemies:
                if e.group_id in newly_aggroed and not e.aggro:
                    e.aggro    = True
                    e.sleeping = False
        for e in self.enemies:
            result = e.update(sp.x, sp.y, self.is_blocked, fh,
                              block, sp.flinch_cooldown)
            if result is None:
                continue
            attack_type = result[0]
            if attack_type == "melee":
                _, ax, ay, dmg = result
                dist = math.hypot(sp.x - e.x, sp.y - e.y)
                if dist < e.radius + 28:
                    self._enemy_hits_player(e, ax, ay, dmg, block, is_arrow=False)
            elif attack_type == "arrow":
                _, ax, ay, adx, ady, admg = result
                self.arrows.append(Arrow(ax, ay, adx, ady, admg))
            if e.hp <= 0:
                dead.append(e)
        for e in dead:
            if e in self.enemies:
                self._on_enemy_death(e)

    def _update_boss(self, block):
        if not self.boss:
            return
        sp     = self.player
        fh     = math.degrees(math.atan2(sp.fy, sp.fx))
        result, phase2_trigger = self.boss.update(
            sp.x, sp.y, self.is_blocked, fh, block, sp.flinch_cooldown)

        if phase2_trigger:
            self.shake.start(14, 25)
            self.freeze.start(8)
            self._camera_punch(1.10)
            sound.play("phase2")
            for _ in range(30):
                angle = random.uniform(0, math.pi * 2)
                speed = random.uniform(2, 6)
                import effects as _fx
                self.particles.particles.append(
                    _fx.Particle(
                        self.boss.x, self.boss.y,
                        math.cos(angle) * speed, math.sin(angle) * speed,
                        (200, 40, 20), lifetime=40, radius=6, gravity=0.05))

        if (self.boss and self.boss.state == "charge_windup"
                and not getattr(self.boss, '_charge_warned', False)):
            self.boss._charge_warned = True
            self.shake.start(5, 8)
            self.flash.start(40)
            sound.play("finisher_charge")

        if self.boss and self.boss.state != "charge_windup":
            if hasattr(self.boss, '_charge_warned'):
                self.boss._charge_warned = False

        # Jump attack — lock target to player position at windup start
        if (self.boss and self.boss.state == "jump_windup"
                and not getattr(self.boss, '_jump_targeted', False)):
            self.boss._jump_targeted = True
            self.boss.jump_target_x = sp.x
            self.boss.jump_target_y = sp.y
            self.boss.jump_origin_x = self.boss.x
            self.boss.jump_origin_y = self.boss.y
            self.shake.start(4, 6)

        if self.boss and self.boss.state not in ("jump_windup", "jump_air", "jump_land"):
            self.boss._jump_targeted = False

        if result:
            attack_type = result[0]
            if attack_type in ("melee", "charge"):
                _, ax, ay, dmg = result
                dist = math.hypot(sp.x - self.boss.x, sp.y - self.boss.y)
                hit_range = (self.boss._atk["melee"]["reach"]
                             if attack_type == "melee"
                             else self.boss.radius + 40)
                if dist < hit_range:
                    self._enemy_hits_player(self.boss, ax, ay, dmg, block,
                                            is_arrow=False,
                                            knockback=KNOCKBACK * (2.0 if attack_type == "charge" else 1.0))
            elif attack_type == "jump_land":
                _, ax, ay, dmg = result
                land_r = self.boss._atk["jump"]["land_radius"]
                dist   = math.hypot(sp.x - ax, sp.y - ay)
                # Screen shake + camera punch on landing
                self.shake.start(16, 22)
                self._camera_punch(1.12)
                sound.play("boss_death")  # heavy impact sound
                # Dust particles at landing
                import effects as _fx
                for _ in range(20):
                    angle = random.uniform(0, math.pi * 2)
                    speed = random.uniform(2, 6)
                    self.particles.particles.append(
                        _fx.Particle(ax, ay,
                                     math.cos(angle) * speed, math.sin(angle) * speed,
                                     (180, 160, 120), lifetime=25, radius=5, gravity=0.15))
                if dist < land_r and sp.flinch_cooldown <= 0:
                    self._enemy_hits_player(self.boss, ax, ay, dmg, block,
                                            is_arrow=False, knockback=KNOCKBACK * 2.5)

        if self.boss and self.boss.state == "stamp_active":
            for ring in self.boss.shockwave_rings:
                dist = math.hypot(sp.x - ring["x"], sp.y - ring["y"])
                if abs(dist - ring["r"]) < 18 and sp.flinch_cooldown <= 0:
                    dmg = self.boss._atk["stamp"]["damage"] * self.boss.damage_mult
                    self._enemy_hits_player(self.boss, ring["x"], ring["y"], dmg,
                                            block, is_arrow=False)

        if self.boss and self.boss.hp <= 0:
            self._on_enemy_death(self.boss)
            self.boss = None

    def _update_arrows(self, block):
        sp        = self.player
        to_remove = []
        for arrow in self.arrows:
            hit_wall = arrow.update(self.is_blocked)
            if hit_wall:
                to_remove.append(arrow)
                continue
            dist = math.hypot(sp.x - arrow.x, sp.y - arrow.y)
            if dist < 18:
                arrow_source  = math.degrees(math.atan2(-arrow.dy, -arrow.dx))
                player_facing = math.degrees(math.atan2(sp.fy, sp.fx))
                angle_to_arrow = abs(angle_diff(player_facing, arrow_source))
                if block and sp._can_block() and angle_to_arrow < 70 and not sp.shield_broken:
                    shield = sp._shield()
                    arrow_stam = shield.get("stamina_cost_arrow", STAMINA_SHIELD_ARROW) if shield else STAMINA_SHIELD_ARROW
                    result = sp.handle_block(arrow.x, arrow.y, arrow_stam, can_parry=False)
                    if result:
                        sound.play("shield_block")
                        self.particles.sword_sparks(sp.x, sp.y, arrow_source)
                        leak = arrow.damage * BLOCK_DAMAGE_THROUGH
                        if leak > 0 and sp.take_damage(leak, arrow.x, arrow.y):
                            self._player_got_hit(leak)
                    else:
                        if sp.take_damage(arrow.damage, arrow.x, arrow.y):
                            self._player_got_hit(arrow.damage)
                else:
                    if sp.take_damage(arrow.damage, arrow.x, arrow.y):
                        self._player_got_hit(arrow.damage)
                to_remove.append(arrow)
        for arrow in to_remove:
            if arrow in self.arrows:
                self.arrows.remove(arrow)

    def _enemy_hits_player(self, enemy, from_x, from_y, damage, block,
                           is_arrow=False, knockback=None):
        sp = self.player
        if block and sp._can_block() and not sp.shield_broken:
            player_facing = math.degrees(math.atan2(sp.fy, sp.fx))
            attack_angle  = math.degrees(math.atan2(from_y - sp.y, from_x - sp.x))
            angle_to_hit  = abs(angle_diff(player_facing, attack_angle))
            if angle_to_hit < 75:
                is_boss = hasattr(enemy, 'bdef')
                result = sp.handle_block(from_x, from_y, can_parry=not is_boss)
                if result == "parry":
                    self._on_parry(enemy)
                    return
                elif result == "block":
                    sound.play("shield_block")
                    self.particles.sword_sparks(sp.x, sp.y,
                        math.degrees(math.atan2(sp.y - from_y, sp.x - from_x)))
                    leak = damage * BLOCK_DAMAGE_THROUGH
                    if leak > 0 and sp.take_damage(leak, from_x, from_y):
                        self._player_got_hit(leak)
                    return
        if knockback is not None:
            knx, kny = normalize(sp.x - from_x, sp.y - from_y)
            sp.flinch_dx = knx * knockback
            sp.flinch_dy = kny * knockback
        if sp.take_damage(damage, from_x, from_y):
            self._player_got_hit(damage)

    def _player_got_hit(self, damage):
        sp = self.player
        self.damage_numbers.add(sp.x, sp.y - 20, damage, is_player_damage=True)
        self.shake.start(8, 14)
        self.freeze.start(4)
        self.flash.start(90)
        self._camera_punch(1.06)
        sound.play("player_hit")

    def _on_parry(self, enemy):
        sp      = self.player
        stats   = sp._block_stats()
        stagger = stats[3] if stats else 60

        knx, kny = normalize(enemy.x - sp.x, enemy.y - sp.y)
        kb = KNOCKBACK * getattr(enemy, 'edef', {}).get("kb_mult", 1.0)
        enemy.flinch_timer = stagger
        enemy.flinch_dx    = knx * kb
        enemy.flinch_dy    = kny * kb

        if hasattr(enemy, 'wolf_state') and enemy.wolf_state in ("dash", "windup"):
            enemy.wolf_state = "recovery"
            enemy.wolf_timer = 40

        angle = math.degrees(math.atan2(sp.y - enemy.y, sp.x - enemy.x))
        self.particles.sword_sparks(sp.x, sp.y, angle)
        self.particles.sword_sparks(sp.x, sp.y, angle + 30)
        self.shake.start(5, 10)
        self.freeze.start(6)
        self._camera_punch(1.05)
        sound.play("shield_block")

    def _check_room_clear(self):
        room = self.floor_graph[self.current_pos]
        if room["cleared"]:
            return
        if not self.enemies and self.boss is None:
            room["cleared"] = True
            if room["type"] == "boss":
                self.floor_portal_open = True
                sound.play("level_up")
            self.shake.start(4, 10)

    def _check_door_transition(self):
        if self.transition_timer > 0 or self._pending_room:
            return
        room = self.floor_graph[self.current_pos]
        if not room["cleared"]:
            return

        sp        = self.player
        tx        = int(sp.x // TILE)
        ty        = int(sp.y // TILE)
        neighbors = room["neighbors"]

        trigger = None
        if "W" in neighbors and tx <= 1:
            trigger = ("W", neighbors["W"])
        elif "E" in neighbors and tx >= self.map_w - 2:
            trigger = ("E", neighbors["E"])
        elif "N" in neighbors and ty <= 1:
            trigger = ("N", neighbors["N"])
        elif "S" in neighbors and ty >= self.map_h - 2:
            trigger = ("S", neighbors["S"])

        if trigger:
            self.transition_timer = 18
            self._pending_room    = trigger

        if self.floor_portal_open and room["type"] == "boss":
            cx = self.map_w // 2 * TILE + TILE // 2
            cy = self.map_h // 2 * TILE + TILE // 2
            if math.hypot(sp.x - cx, sp.y - cy) < 48:
                self.level_mgr.next_floor()
                self.save["highest_floor"] = max(
                    self.save.get("highest_floor", 0), self.level_mgr.floor_num - 1)
                save_game(self.save)
                self._generate_floor(first=False)

    def _check_fountain(self):
        if not self.fountain_pos or self.fountain_used:
            return
        sp   = self.player
        dist = math.hypot(sp.x - self.fountain_pos[0], sp.y - self.fountain_pos[1])
        if dist < 40:
            heal = min(40, sp.hp_max - sp.hp)
            if heal > 0:
                sp.hp += heal
                self.damage_numbers.add(sp.x, sp.y - 20, f"+{int(heal)}",
                                        color_override=True, override_color=(80, 255, 120))
                sound.play("fountain")
            self.fountain_used = True
            self.floor_graph[self.current_pos]["fountain_used"] = True

    def _check_item_pedestal(self):
        if not self.item_pedestal_pos or self.item_choice_active:
            return
        sp   = self.player
        dist = math.hypot(sp.x - self.item_pedestal_pos[0],
                          sp.y - self.item_pedestal_pos[1])
        if dist < 50:
            self.item_choices       = pick_items(3, self.save.get("items", []),
                                                 self.save.get("item_charges", {}))
            self.item_choice_active = True

    def _update_camera(self):
        sp       = self.player
        target_x = sp.x - SCREEN_W / 2
        target_y = sp.y - SCREEN_H / 2
        max_cx   = self.map_w * TILE - SCREEN_W
        max_cy   = self.map_h * TILE - SCREEN_H
        target_x = max(0, min(target_x, max_cx))
        target_y = max(0, min(target_y, max_cy))
        self.cam_x += (target_x - self.cam_x) * 0.12
        self.cam_y += (target_y - self.cam_y) * 0.12

    # ═════════════════════════════════════════════════════════════════════════
    #  DRAWING
    # ═════════════════════════════════════════════════════════════════════════

    def _draw(self):
        ox, oy = self.shake.update()
        zoom   = self.cam_zoom
        cam_x  = int(self.cam_x) + ox
        cam_y  = int(self.cam_y) + oy

        if zoom != 1.0:
            render_surf = pygame.Surface((SCREEN_W, SCREEN_H))
            self._draw_world(render_surf, cam_x, cam_y)
            scaled_w = int(SCREEN_W * zoom)
            scaled_h = int(SCREEN_H * zoom)
            scaled   = pygame.transform.scale(render_surf, (scaled_w, scaled_h))
            bx = (SCREEN_W - scaled_w) // 2
            by = (SCREEN_H - scaled_h) // 2
            self.screen.fill((0, 0, 0))
            self.screen.blit(scaled, (bx, by))
        else:
            self._draw_world(self.screen, cam_x, cam_y)

        self._draw_hud()
        self._draw_minimap()
        if self.equip_menu_active:
            self._draw_equip_menu()
        if self.item_choice_active:
            self._draw_item_choice()
        if self.room_intro_timer > 0:
            self._draw_room_intro()
            self.room_intro_timer -= 1
        if not self.player.alive:
            self._draw_death_screen()

    def _draw_world(self, surface, cam_x, cam_y):
        sp    = self.player
        block = (pygame.mouse.get_pressed()[2]
                 and sp._can_block()
                 and not sp.shield_broken
                 and sp.dodge_timer == 0
                 and sp.flinch_timer == 0)

        surface.fill(C_BG)
        self._draw_tiles(surface, cam_x, cam_y)
        self._draw_rest_room_objects(surface, cam_x, cam_y)
        self.particles.draw(surface, cam_x, cam_y)

        for e in self.enemies:
            e.draw(surface, cam_x, cam_y)
        if self.boss:
            self.boss.draw(surface, cam_x, cam_y)
        for arrow in self.arrows:
            arrow.draw(surface, cam_x, cam_y)
        sp.draw(surface, cam_x, cam_y, block)

        self._draw_decorations(surface, cam_x, cam_y)
        self.damage_numbers.draw(surface, cam_x, cam_y)
        self.flash.draw(surface)

    def _draw_hud(self):
        sp = self.player

        hp_w = 180
        hp_r = max(0, sp.hp / sp.hp_max)
        pygame.draw.rect(self.screen, (60, 20, 20),  (10, 10, hp_w, 18))
        pygame.draw.rect(self.screen, (220, 60, 60), (10, 10, int(hp_w * hp_r), 18))
        pygame.draw.rect(self.screen, (255, 120, 120), (10, 10, hp_w, 18), 1)
        t = self.font_s.render(f"HP  {int(sp.hp)}/{int(sp.hp_max)}", True, (255, 200, 200))
        self.screen.blit(t, (14, 12))

        st_w  = 180
        st_r  = max(0, sp.stamina / sp.stamina_max)
        st_kl = (255, 200, 50) if sp.shield_broken else (80, 200, 120)
        pygame.draw.rect(self.screen, (20, 50, 30),   (10, 32, st_w, 12))
        pygame.draw.rect(self.screen, st_kl,           (10, 32, int(st_w * st_r), 12))
        pygame.draw.rect(self.screen, (120, 220, 160), (10, 32, st_w, 12), 1)
        if sp.shield_broken:
            t = self.font_s.render("SHIELD BROKEN", True, (255, 120, 50))
            self.screen.blit(t, (14, 34))

        items   = self.save.get("items", [])
        charges = self.save.get("item_charges", {})
        active  = [k for k in items if ITEMS[k]["type"] == "active"]
        if active:
            key  = active[0]
            item = ITEMS[key]
            c    = charges.get(key, item.get("charges", 1))
            kl   = item["color"]
            t    = self.font_s.render(f"[Q] {item['name']}  x{c}", True, kl)
            self.screen.blit(t, (10, 50))

        step = sp.combo_step
        weapon = sp._weapon()
        from weapons import combo_length as _cl
        n_combo = _cl(weapon)
        if step > 0 or sp.finisher_windup > 0:
            dots = []
            for i in range(1, n_combo + 1):
                if i < step:
                    dots.append("\u25cf")
                elif i == step and sp.finisher_windup > 0:
                    dots.append("\u25ce")
                elif i == step:
                    dots.append("\u25c9")
                else:
                    dots.append("\u25cb" if sp.combo_window > 0 else "\u00b7")
            kl = (255, 220, 100) if sp.combo_window > 0 else (120, 100, 60)
            t  = self.font_m.render("  ".join(dots), True, kl)
            self.screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, SCREEN_H - 38))

        if sp.has_active_effect("invis"):
            t = self.font_s.render("\u25cf INVULNERABLE", True, (100, 200, 255))
            self.screen.blit(t, (SCREEN_W - t.get_width() - 10, 10))

        room          = self.floor_graph[self.current_pos]
        combat_rooms  = [p for p, r in self.floor_graph.items() if r["type"] == "combat"]
        visited_combat = sum(1 for p in combat_rooms if self.floor_graph[p]["visited"])
        label = self.level_mgr.description(visited_combat, len(combat_rooms))
        t = self.font_s.render(label, True, (180, 200, 180))
        self.screen.blit(t, (SCREEN_W - t.get_width() - 10, SCREEN_H - 24))

        if self.boss:
            bw    = 400
            bx    = SCREEN_W // 2 - bw // 2
            by    = SCREEN_H - 52
            ratio = max(0, self.boss.hp / self.boss.hp_max)
            kl_b  = (220, 60, 60)
            pygame.draw.rect(self.screen, (50, 20, 20), (bx, by, bw, 20))
            pygame.draw.rect(self.screen, kl_b,         (bx, by, int(bw * ratio), 20))
            pygame.draw.rect(self.screen, (200, 160, 120), (bx, by, bw, 20), 2)
            bname = self.boss.bdef["name"]
            label = f"\u2620  {bname}  \u2620"
            t = self.font_s.render(label, True, (220, 180, 120))
            self.screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, by - 18))

        items_passive = [k for k in items if ITEMS[k]["type"] == "passive"]
        for i, key in enumerate(items_passive):
            item = ITEMS[key]
            t    = self.font_s.render(f"\u25cf {item['name']}", True, item["color"])
            self.screen.blit(t, (SCREEN_W - t.get_width() - 10, 30 + i * 18))

    def _draw_minimap(self):
        room_size = 10; gap = 3; padding = 8
        positions = list(self.floor_graph.keys())
        if not positions:
            return
        min_gx = min(p[0] for p in positions); max_gx = max(p[0] for p in positions)
        min_gy = min(p[1] for p in positions); max_gy = max(p[1] for p in positions)
        cols  = max_gx - min_gx + 1; rows = max_gy - min_gy + 1
        map_w = cols * (room_size + gap) - gap + padding * 2
        map_h = rows * (room_size + gap) - gap + padding * 2
        ox    = SCREEN_W - map_w - 10
        oy    = SCREEN_H - map_h - 40

        bg = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 120))
        self.screen.blit(bg, (ox, oy))

        for pos, room in self.floor_graph.items():
            gx, gy = pos
            rx = ox + padding + (gx - min_gx) * (room_size + gap)
            ry = oy + padding + (gy - min_gy) * (room_size + gap)
            if not room["visited"]:
                pygame.draw.rect(self.screen, (50, 50, 50),
                                 (rx, ry, room_size, room_size))
                continue
            if room["type"] == "boss":       kl = (220, 60, 60)
            elif room["type"] == "rest":     kl = (60, 180, 120)
            elif room["cleared"]:            kl = (80, 120, 80)
            else:                            kl = (160, 160, 80)
            pygame.draw.rect(self.screen, kl, (rx, ry, room_size, room_size))
            if pos == self.current_pos:
                pygame.draw.rect(self.screen, (255, 255, 255),
                                 (rx, ry, room_size, room_size), 2)

    def _draw_item_choice(self):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        t = self.font_m.render("Choose an item  [1 / 2 / 3]", True, (220, 200, 120))
        self.screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 80))

        card_w, card_h = 200, 220
        total_w = len(self.item_choices) * (card_w + 20) - 20
        start_x = SCREEN_W // 2 - total_w // 2

        for i, key in enumerate(self.item_choices):
            item = ITEMS[key]
            cx   = start_x + i * (card_w + 20)
            cy   = SCREEN_H // 2 - card_h // 2

            pygame.draw.rect(self.screen, (40, 35, 30),
                             (cx, cy, card_w, card_h), border_radius=8)
            pygame.draw.rect(self.screen, item["color"],
                             (cx, cy, card_w, card_h), 2, border_radius=8)

            rarity_kl = RARITY_COLOR.get(item["rarity"], (160, 160, 160))
            rt = self.font_s.render(RARITY_NAME.get(item["rarity"], ""), True, rarity_kl)
            self.screen.blit(rt, (cx + card_w // 2 - rt.get_width() // 2, cy + 10))

            pygame.draw.circle(self.screen, item["color"],
                               (cx + card_w // 2, cy + 70), 28)
            pygame.draw.circle(self.screen, item["color_dim"],
                               (cx + card_w // 2, cy + 70), 28, 3)

            nt = self.font_m.render(item["name"], True, (240, 230, 210))
            self.screen.blit(nt, (cx + card_w // 2 - nt.get_width() // 2, cy + 108))

            for j, line in enumerate(item["description"].split("\n")):
                dt = self.font_s.render(line, True, (180, 170, 150))
                self.screen.blit(dt, (cx + card_w // 2 - dt.get_width() // 2,
                                      cy + 138 + j * 18))

            ht = self.font_m.render(f"[{i+1}]", True, (220, 200, 100))
            self.screen.blit(ht, (cx + card_w // 2 - ht.get_width() // 2,
                                  cy + card_h - 30))

    def _draw_room_intro(self):
        alpha = min(255, self.room_intro_timer * 6)
        room  = self.floor_graph[self.current_pos]
        if room["type"] == "boss":
            text = "\u2694  BOSS  \u2694"; kl = (255, 80, 40)
        elif room["type"] == "rest":
            text = "Rest Room";      kl = (80, 200, 140)
        else:
            text = self.level_mgr.description(); kl = (200, 200, 160)
        t = self.font_g.render(text, True, kl)
        t.set_alpha(alpha)
        self.screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, SCREEN_H // 2 - 40))

    def _draw_death_screen(self):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        t1 = self.font_g.render("You have fallen...", True, (220, 60, 60))
        t2 = self.font_m.render("Press R to restart",
                                True, (180, 140, 140))
        self.screen.blit(t1, (SCREEN_W // 2 - t1.get_width() // 2, SCREEN_H // 2 - 60))
        self.screen.blit(t2, (SCREEN_W // 2 - t2.get_width() // 2, SCREEN_H // 2 + 10))
        keys = pygame.key.get_pressed()
        if keys[pygame.K_r]:
            self.save["items"]          = []
            self.save["item_charges"]   = {}
            self.save["active_effects"] = {"invis": 0, "fire_potion": 0}
            save_game(self.save)
            self.level_mgr = LevelManager()
            self.player    = None
            self._generate_floor(first=True)
