# entities.py - Player, Enemy, Boss, Arrow
import math, random
import pygame
from constants import *

SWORD_REACH = 88  # px — tweak here to adjust melee range


def normalize(x, y):
    l = math.hypot(x, y)
    return (x / l, y / l) if l else (0.0, 0.0)


def angle_diff(a, b):
    d = (b - a) % 360
    if d > 180: d -= 360
    return d


def ease_out(t):
    return 1 - (1 - t) ** 2


def ease_in_out(t):
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


# ══════════════════════════════════════════════════════════════════════════════
#  PLAYER
# ══════════════════════════════════════════════════════════════════════════════

class Player:
    def __init__(self, x, y, save):
        self.x = float(x); self.y = float(y)
        self.fx = 0.0; self.fy = -1.0
        self.save        = save
        self.hp          = get_max_hp(save)
        self.hp_max      = get_max_hp(save)
        self.stamina     = get_max_stamina(save)
        self.stamina_max = get_max_stamina(save)

        # Movement / dodge
        self.dodge_timer         = 0
        self.dodge_cooldown      = 0
        self.dodge_dx            = 0.0
        self.dodge_dy            = 0.0
        self.dodge_burst_pending = False
        
        # Charge dash (gap-closer from dodge or sprint)
        self.charge_timer  = 0
        self.charge_dx     = 0.0
        self.charge_dy     = 0.0
        self.is_charging   = False
        self._sprint_active = False

        # Damage / flinch
        self.flinch_timer    = 0
        self.flinch_cooldown = 0
        self.flinch_dx       = 0.0
        self.flinch_dy       = 0.0
        self.hit_flash_timer = 0
        self.stamina_delay   = 0

        # Hit tracking
        self.hit_ids = set()

        # Combo system
        self.combo_step          = 0
        self.combo_timer         = 0
        self.combo_window        = 0
        self.combo_reset_timer   = 0
        self.combo_buffered      = False
        self.dash_strike_window  = 0
        self.is_dash_strike      = False
        self.finisher_windup     = 0
        self.swing_cooldown      = 0
        self.post_combo_cooldown = 0
        self._combo_idle_timer   = 0
        self._post_combo_triggered = False

        # Facing lock
        self.lock_fx       = 0.0
        self.lock_fy       = 1.0
        self.facing_locked = False

        # Shield / guard break
        self.guard_break_timer = 0
        self.shield_broken     = False

        # Squash & stretch
        self.scale_x = 1.0
        self.scale_y = 1.0

        # Movement direction
        self.move_dx = 0.0
        self.move_dy = 0.0

        self.tick = 0

    # ── Properties ────────────────────────────────────────────────────────────
    @property
    def alive(self): return self.hp > 0

    @property
    def can_attack(self): return self.flinch_timer == 0

    # ── Save helpers ──────────────────────────────────────────────────────────
    def _weapon(self):
        from weapons import get_weapon
        return get_weapon(self.save.get("weapon", "shield"))

    def _has_shield(self):
        return self._weapon().get("type") == "shield"

    def has_item(self, key):
        return key in self.save.get("items", [])

    def has_active_effect(self, key):
        return self.save.get("active_effects", {}).get(key, 0) > 0

    # ── Attack input ──────────────────────────────────────────────────────────
    def _try_attack(self, block=False):
        if block: return
        SWING_CD = 18

        # ── Charge attack: tijdens dodge of sprint ────────────────────────────
        can_charge = (
            (self.dodge_timer > 0 or self._sprint_active)
            and self.charge_timer == 0
            and self.can_attack
            and self.finisher_windup == 0
        )
        if can_charge:
            self.charge_timer        = CHARGE_FRAMES
            self.charge_dx           = self.fx * CHARGE_SPEED
            self.charge_dy           = self.fy * CHARGE_SPEED
            self.is_charging         = True
            self.dodge_timer         = 0          # cancel dodge
            self._sprint_active      = False
            self.combo_timer         = 0
            self.combo_step          = 0
            self.combo_window        = 0
            self.combo_reset_timer   = 0
            self.finisher_windup     = 0
            self.swing_cooldown      = 0
            self.post_combo_cooldown = 0
            self.facing_locked       = True
            self.lock_fx = self.fx; self.lock_fy = self.fy
            self.scale_x = 0.45; self.scale_y = 1.7
            import sound as _snd; _snd.play("dodge")
            return

        # ── Normale combo ─────────────────────────────────────────────────────
        if self.charge_timer > 0: return   # nog aan het chargen

        can = (self.combo_timer == 0 and self.finisher_windup == 0
               and self.swing_cooldown == 0 and self.post_combo_cooldown == 0
               and self.can_attack and self.dodge_timer == 0)
        if (self.combo_window > 0 and self.combo_step in (1, 2)
                and self.combo_timer == 0 and self.swing_cooldown == 0
                and self.post_combo_cooldown == 0):
            can = True

        if not can:
            if self.combo_timer > 0 and self.combo_step in (1, 2):
                self.swing_cooldown = min(self.swing_cooldown + 8, SWING_CD + 8)
            return

        if (self.combo_step % 3) + 1 == 3:
            self.combo_step      = 2
            self.combo_timer     = 0
            self.combo_window    = 0
            self.finisher_windup = 16
            self.is_dash_strike  = False
            self.facing_locked   = True
            self.lock_fx = self.fx; self.lock_fy = self.fy
            import sound as _snd; _snd.play("finisher_charge")
        else:
            self.combo_step        = (self.combo_step % 3) + 1
            self.combo_timer       = 10
            self.combo_window      = 28
            self.combo_reset_timer = 0
            self.is_dash_strike    = False
            import sound as _snd
            _snd.play("sword_swing_1" if self.combo_step == 1 else "sword_swing_2")

        self.stamina_delay     = STAMINA_DELAY
        self.swing_cooldown    = SWING_CD
        self.hit_ids           = set()
        self._combo_idle_timer = 0

        if not self.finisher_windup:
            self.lock_fx = self.fx; self.lock_fy = self.fy
            self.facing_locked = True

    # ── Event handling ────────────────────────────────────────────────────────
    def handle_events(self, events, block=False):
        COMBO_TIMEOUT = 22

        for e in events:                                         # ← loop start
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                combo_elapsed = 10 - self.combo_timer
                dodge_ok = (self.dodge_timer <= 0 and self.dodge_cooldown <= 0
                            and self.stamina >= STAMINA_DODGE
                            and self.dodge_timer == 0)
                in_swing = self.combo_timer > 0 and combo_elapsed >= 3
                if (dodge_ok and (not self.combo_timer > 0 or in_swing)
                        and self.combo_reset_timer == 0):
                    bx, by = self.move_dx, self.move_dy
                    if math.hypot(bx, by) < 0.1:
                        bx, by = self.fx, self.fy
                    self.dodge_dx            = bx * DODGE_SPEED
                    self.dodge_dy            = by * DODGE_SPEED
                    self.dodge_timer         = DODGE_FRAMES
                    self.dodge_cooldown      = DODGE_CD
                    self.stamina_delay       = STAMINA_DELAY
                    self.scale_x = 1.4; self.scale_y = 0.7
                    self.dash_strike_window  = DODGE_FRAMES + 8
                    self.dodge_burst_pending = True
                    import sound as _snd; _snd.play("dodge")
                    self.combo_timer         = 0
                    self.combo_step          = 0
                    self.combo_window        = 0
                    self.combo_reset_timer   = 0
                    self.combo_buffered      = False
                    self.facing_locked       = False
                    self.finisher_windup     = 0
                    self.swing_cooldown      = 0
                    self.post_combo_cooldown = 0

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:   # ← zelfde inspringing als K_SPACE
                self._try_attack(block)

        # Hold LMB: auto-swing when button held and cooldown ready
        if pygame.mouse.get_pressed()[0] and not block:
            if (self.combo_timer == 0 and self.finisher_windup == 0
                    and self.swing_cooldown == 0):
                self._try_attack(block)

        # Combo timeout
        if (self.combo_step > 0 and self.combo_timer == 0
                and self.finisher_windup == 0 and self.combo_window == 0):
            self._combo_idle_timer += 1
            if self._combo_idle_timer > COMBO_TIMEOUT:
                self.combo_step        = 0
                self._combo_idle_timer = 0
        else:
            self._combo_idle_timer = 0

        # Hold LMB: auto-swing when button held and cooldown ready
        if pygame.mouse.get_pressed()[0] and not block:
            if (self.combo_timer == 0 and self.finisher_windup == 0
                    and self.swing_cooldown == 0):
                self._try_attack(block)

        # Combo timeout
        if (self.combo_step > 0 and self.combo_timer == 0
                and self.finisher_windup == 0 and self.combo_window == 0):
            self._combo_idle_timer += 1
            if self._combo_idle_timer > COMBO_TIMEOUT:
                self.combo_step        = 0
                self._combo_idle_timer = 0
        else:
            self._combo_idle_timer = 0

    # ── Per-frame update ──────────────────────────────────────────────────────
    def update(self, keys, mouse_pos, cam_x, cam_y, is_blocked, tile_op, block):
        self.tick += 1

        # Facing follows mouse
        dmx = mouse_pos[0] + cam_x - self.x
        dmy = mouse_pos[1] + cam_y - self.y
        if math.hypot(dmx, dmy) > 5:
            if not self.facing_locked:
                self.fx, self.fy = normalize(dmx, dmy)
            else:
                self.fx, self.fy = self.lock_fx, self.lock_fy

        # WASD input
        mx, my = 0.0, 0.0
        if keys[pygame.K_w]: my -= 1
        if keys[pygame.K_s]: my += 1
        if keys[pygame.K_a]: mx -= 1
        if keys[pygame.K_d]: mx += 1
        mx, my = normalize(mx, my)
        self.move_dx = mx; self.move_dy = my

        sprint = (keys[pygame.K_SPACE] and self.dodge_timer == 0
                  and self.charge_timer == 0
                  and math.hypot(mx, my) > 0.1)
        self._sprint_active = sprint

        combo_elapsed = 10 - self.combo_timer

        # Speed
        if self.dodge_timer > 0:
            speed = DODGE_SPEED + get_bonus_dodge(self.save)
        elif self.finisher_windup > 0:
            speed = 0.0
        elif self.combo_timer > 0:
            if combo_elapsed < 2:      speed = 0.0
            elif self.combo_step == 3: speed = 0.0
            else:                      speed = PLAYER_SPEED * 0.25
        elif self.combo_reset_timer > 0:
            speed = PLAYER_SPEED * 0.5
        elif block:   speed = PLAYER_SPEED * 0.5
        elif sprint:  speed = PLAYER_SPEED * SPRINT_SPEED
        else:         speed = PLAYER_SPEED

        # Movement vector
        if self.charge_timer > 0:
            dx, dy = 0.0, 0.0   # charge heeft eigen beweging hierboven
        elif self.flinch_timer > 0:
            dx, dy = self.flinch_dx, self.flinch_dy
            self.flinch_dx *= 0.8; self.flinch_dy *= 0.8
        elif self.dodge_timer > 0:
            dx, dy = self.dodge_dx, self.dodge_dy
        elif self.combo_timer > 0 and self.combo_step == 3:
            lunge  = PLAYER_SPEED * 1.8 * max(0, (6 - combo_elapsed) / 6)
            dx, dy = self.fx * lunge, self.fy * lunge
        else:
            dx, dy = mx * speed, my * speed

        # Collision
        r = 13
        nx = self.x + dx
        if not any(is_blocked(int((nx + ox) // TILE), int((self.y + oy) // TILE))
                   for ox in (-r, r) for oy in (-r, r)):
            self.x = nx
        ny = self.y + dy
        if not any(is_blocked(int((self.x + ox) // TILE), int((ny + oy) // TILE))
                   for ox in (-r, r) for oy in (-r, r)):
            self.y = ny

        # Charge dash movement
        if self.charge_timer > 0:
            self.charge_timer -= 1
            r2 = 13
            cx_new = self.x + self.charge_dx
            if not any(is_blocked(int((cx_new + ox2) // TILE),
                                  int((self.y + oy2) // TILE))
                       for ox2 in (-r2, r2) for oy2 in (-r2, r2)):
                self.x = cx_new
            cy_new = self.y + self.charge_dy
            if not any(is_blocked(int((self.x + ox2) // TILE),
                                  int((cy_new + oy2) // TILE))
                       for ox2 in (-r2, r2) for oy2 in (-r2, r2)):
                self.y = cy_new
            self.charge_dx *= 0.82
            self.charge_dy *= 0.82

            if self.charge_timer == 0:
                # Land — auto-start combo stap 1
                self.is_charging         = False
                self.combo_step          = 1
                self.combo_timer         = 10
                self.combo_window        = 28
                self.dash_strike_window  = 0
                self.is_dash_strike      = False
                self.hit_ids             = set()
                self.lock_fx = self.fx; self.lock_fy = self.fy
                self.facing_locked       = True
                self.swing_cooldown      = 18
                self.scale_x = 1.5; self.scale_y = 0.6
                import sound as _snd; _snd.play("sword_swing_1")

        # Tick timers
        for attr in ("dodge_timer", "dodge_cooldown", "flinch_timer",
                     "flinch_cooldown", "hit_flash_timer"):
            if getattr(self, attr) > 0:
                setattr(self, attr, getattr(self, attr) - 1)

        # Squash/stretch
        self.scale_x = lerp(self.scale_x, 1.0, 0.18)
        self.scale_y = lerp(self.scale_y, 1.0, 0.18)
        if math.hypot(mx, my) > 0.1 and self.dodge_timer == 0 and self.flinch_timer == 0:
            self.scale_x = lerp(self.scale_x, 1.15, 0.12)
            self.scale_y = lerp(self.scale_y, 0.88, 0.12)
        if self.flinch_timer > 0 and self.flinch_timer == FLINCH_PLAYER:
            self.scale_x = 0.6; self.scale_y = 1.5

        # Guard break
        if self.guard_break_timer > 0:
            self.guard_break_timer -= 1
            if self.guard_break_timer == 0:
                self.shield_broken = False

        # Stamina regen
        if block:
            pass  # geen regen tijdens blokkeren
        elif self.stamina < self.stamina_max:
            self.stamina = min(self.stamina_max,
                               self.stamina + (self.stamina_max * STAMINA_REGEN_PCT / FPS))
        if self.stamina_delay > 0:
            self.stamina_delay -= 1

        # Active effects countdown
        for eff in self.save.get("active_effects", {}):
            if self.save["active_effects"][eff] > 0:
                self.save["active_effects"][eff] -= 1

        # Finisher windup
        if self.finisher_windup > 0:
            self.finisher_windup -= 1
            if self.finisher_windup == 0:
                self.combo_step     = 3
                self.combo_timer    = 10
                self.combo_window   = 28
                self.is_dash_strike = False
                self.hit_ids        = set()
                self.scale_x = 0.6; self.scale_y = 1.5

        # I-frames on swing start
        if self.combo_timer > 0 and combo_elapsed < 3:
            self.flinch_cooldown = max(self.flinch_cooldown, 3)

        # Combo timers
        if self.combo_timer        > 0: self.combo_timer        -= 1
        if self.combo_window       > 0: self.combo_window       -= 1
        if self.swing_cooldown     > 0: self.swing_cooldown     -= 1
        if self.dash_strike_window > 0: self.dash_strike_window -= 1
        if self.combo_reset_timer  > 0:
            self.combo_reset_timer -= 1
            if self.combo_reset_timer == 0:
                self.combo_step    = 0
                self.facing_locked = False
        if self.post_combo_cooldown > 0:
            self.post_combo_cooldown -= 1
            if self.post_combo_cooldown == 0:
                self.combo_step = 0

        # Post-finisher recovery
        if (self.combo_timer == 0 and self.combo_step == 3
                and not self._post_combo_triggered):
            self._post_combo_triggered = True
            self.post_combo_cooldown   = 22
            self.swing_cooldown        = 22
        elif self.combo_timer > 0 or self.combo_step != 3:
            self._post_combo_triggered = False

        # Unlock facing when done
        if self.combo_timer == 0 and self.combo_window == 0:
            self.facing_locked = False

        # Buffered input
        if self.combo_buffered and self.combo_timer == 0:
            self.combo_buffered = False
            if (self.stamina >= STAMINA_SWORD and self.can_attack
                    and self.dodge_timer == 0):
                self.combo_step        = (self.combo_step % 3) + 1
                self.combo_timer       = 10
                self.combo_window      = 28
                self.combo_reset_timer = 0
                self.is_dash_strike    = False
                self.stamina          -= STAMINA_SWORD
                self.stamina_delay     = STAMINA_DELAY
                self.hit_ids           = set()
                self.lock_fx           = self.fx
                self.lock_fy           = self.fy
                self.facing_locked     = True

    # ── Damage / block ────────────────────────────────────────────────────────
    def take_damage(self, damage, from_x, from_y):
        if self.dodge_timer > 0 or self.flinch_cooldown > 0: return False
        if self.has_active_effect("invis"): return False
        self.hp = max(0, self.hp - damage)
        knx, kny = normalize(self.x - from_x, self.y - from_y)
        self.flinch_timer    = FLINCH_PLAYER
        self.flinch_cooldown = FLINCH_CD_PLAYER
        self.flinch_dx       = knx * KNOCKBACK
        self.flinch_dy       = kny * KNOCKBACK
        self.hit_flash_timer = 8
        return True

    def handle_block(self, from_x, from_y, stamina_cost=None):
        if stamina_cost is None:
            stamina_cost = STAMINA_SHIELD
        if self.shield_broken:
            return False
        if self.stamina >= stamina_cost:
            self.stamina      -= stamina_cost
            self.stamina_delay = STAMINA_DELAY
            knx, kny = normalize(self.x - from_x, self.y - from_y)
            self.flinch_dx    = knx * 3.5
            self.flinch_dy    = kny * 3.5
            self.flinch_timer = 6
            self.scale_x = 0.85; self.scale_y = 1.2
            return True
        else:
            self.stamina           = 0
            self.guard_break_timer = GUARD_BREAK_TIMER
            self.shield_broken     = True
            knx, kny = normalize(self.x - from_x, self.y - from_y)
            self.flinch_timer    = GUARD_BREAK_TIMER // 2
            self.flinch_dx       = knx * KNOCKBACK * 1.8
            self.flinch_dy       = kny * KNOCKBACK * 1.8
            self.scale_x = 1.8; self.scale_y = 0.4
            self.flinch_cooldown = 0
            return False

    # ── Hit detection ─────────────────────────────────────────────────────────
    def sword_hits(self, targets):
        hits = []
        if self.combo_timer <= 0: return hits

        fh   = math.degrees(math.atan2(self.fy, self.fx))
        step = self.combo_step
        prog = ease_in_out(1.0 - self.combo_timer / 10)

        base_damage = PLAYER_DAMAGE + get_bonus_damage(self.save)
        if self.has_item("fire_damage") or self.has_active_effect("fire_potion"):
            base_damage *= 1.25
        if self.has_item("berserker"):
            hp_ratio = max(0.0, 1.0 - self.hp / self.hp_max)
            base_damage *= (1.0 + hp_ratio * 0.8)

        if step == 1:
            reach     = SWORD_REACH
            swing_h   = fh - 60 + prog * 120
            tolerance = 42
            damage    = base_damage
        elif step == 2:
            reach     = SWORD_REACH
            swing_h   = fh + 60 - prog * 120
            tolerance = 42
            damage    = base_damage
        else:
            reach     = SWORD_REACH * (1.5 if self.is_dash_strike else 1.3)
            swing_h   = fh
            tolerance = 28
            finisher_mult = 2.5 * (1.5 if self.has_item("combo_master") else 1.0)
            damage = base_damage * (1.8 if self.is_dash_strike else finisher_mult)

        for v in targets:
            if v.id in self.hit_ids: continue
            dvx = v.x - self.x; dvy = v.y - self.y
            if math.hypot(dvx, dvy) < reach:
                vh = math.degrees(math.atan2(dvy, dvx))
                if abs(angle_diff(swing_h, vh)) < tolerance:
                    self.hit_ids.add(v.id)
                    kb_rad = math.radians(swing_h)
                    hits.append((v, damage, math.cos(kb_rad), math.sin(kb_rad)))
        return hits
    
    def charge_hits(self, targets):
        """Hit detection during the charge dash itself."""
        if self.charge_timer <= 0:
            return []
        hits = []
        base_damage = (PLAYER_DAMAGE + get_bonus_damage(self.save)) * 1.4
        reach = 52
        for v in targets:
            if v.id in self.hit_ids:
                continue
            dist = math.hypot(v.x - self.x, v.y - self.y)
            if dist < reach:
                # Check if enemy is roughly in front of us
                dvx, dvy = normalize(v.x - self.x, v.y - self.y)
                dot = dvx * self.fx + dvy * self.fy
                if dot > 0.0:   # enemy is in front
                    self.hit_ids.add(v.id)
                    hits.append((v, base_damage, self.fx, self.fy))
        return hits

    # ── Drawing ───────────────────────────────────────────────────────────────
    def draw(self, surface, cam_x, cam_y, block):
        sx = int(self.x - cam_x); sy = int(self.y - cam_y); r = 15
        rw   = max(6, int(r * self.scale_x))
        rh_s = max(6, int(r * self.scale_y))

        knip       = self.flinch_timer > 0 and (self.flinch_timer // 4) % 2 == 0
        guard_knip = self.guard_break_timer > 0 and (self.guard_break_timer // 3) % 2 == 0

        pygame.draw.ellipse(surface, C_SHADOW, (sx - rw + 4, sy + rh_s - 4, rw * 2, rh_s))

        if self.hit_flash_timer > 0 and (self.hit_flash_timer // 2) % 2 == 0:
            kl = (255, 255, 255)
        elif guard_knip:
            kl = (255, 200, 50)
        else:
            kl = (220, 60, 60) if knip else (C_PLAYER_DODGE if self.dodge_timer > 0 else C_PLAYER)

        pygame.draw.ellipse(surface, kl, (sx - rw, sy - rh_s, rw * 2, rh_s * 2))
        pygame.draw.circle(surface, C_EYE,
            (int(sx + self.fx * 9), int(sy + self.fy * 9)), 5)

        # Finisher charge glow
        fw = self.finisher_windup
        if fw > 0:
            WINDUP     = 16
            charge     = max(0.0, 1.0 - fw / WINDUP)
            glow_r     = max(4, int(18 + charge * 14))
            glow_alpha = int(max(0, min(255, charge * 220)))
            puls       = abs(math.sin(fw * 0.6))
            g_kl       = (255, max(0, min(255, int(180 + puls * 75))), 50, glow_alpha)
            gs = pygame.Surface((glow_r * 2 + 4, glow_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(gs, g_kl, (glow_r + 2, glow_r + 2),
                               glow_r, max(2, int(charge * 6)))
            surface.blit(gs, (sx - glow_r - 2, sy - glow_r - 2))

        fh = math.degrees(math.atan2(self.fy, self.fx))

        if self.combo_timer > 0:
            prog = ease_in_out(1.0 - self.combo_timer / 10)
            step = self.combo_step
            if step == 1:
                zh_start = fh - 60; zh_end = fh + 60
                zh       = zh_start + prog * 120
                reach_t  = SWORD_REACH
            elif step == 2:
                zh_start = fh + 60; zh_end = fh - 60
                zh       = zh_start - prog * 120
                reach_t  = SWORD_REACH
            else:
                zh_start = zh_end = zh = fh
                reach_t  = SWORD_REACH * (1.5 if self.is_dash_strike else 1.3)

            rad = math.radians(zh)
            ex  = sx + math.cos(rad) * reach_t
            ey  = sy + math.sin(rad) * reach_t
            lkl = (255, 220, 50) if self.is_dash_strike else C_SWORD
            pygame.draw.line(surface, lkl, (sx, sy), (int(ex), int(ey)),
                             6 if self.is_dash_strike else 5)
            tkl = (255, 255, 100) if self.is_dash_strike else (240, 240, 255)
            pygame.draw.circle(surface, tkl, (int(ex), int(ey)),
                               7 if self.is_dash_strike else 5)

            if step != 3 and prog > 0.05:
                n_pts  = 14
                swoosh = []
                for i in range(n_pts + 1):
                    t  = i / n_pts
                    ah = zh_start + (zh - zh_start) * t
                    d  = reach_t * (0.45 + 0.55 * t)
                    ar = math.radians(ah)
                    swoosh.append((sx + math.cos(ar) * d, sy + math.sin(ar) * d))
                for i in range(len(swoosh) - 1):
                    t     = i / (len(swoosh) - 1)
                    alpha = int(180 * t * prog)
                    width = max(1, int(14 * t * prog))
                    kl_sw = (int(200 + 55 * t), int(220 + 35 * t), 255)
                    seg   = pygame.Surface((width * 2 + 4, width * 2 + 4), pygame.SRCALPHA)
                    pygame.draw.circle(seg, (*kl_sw, alpha), (width + 2, width + 2), width)
                    surface.blit(seg, (int(swoosh[i][0]) - width - 2,
                                       int(swoosh[i][1]) - width - 2))
            elif step == 3:
                flits_kl = (255, 220, 50) if self.is_dash_strike else (255, 255, 200)
                for dist_l in range(0, int(reach_t), 7):
                    alpha = int(200 * (1 - dist_l / reach_t) * prog)
                    r_l   = max(1, int((9 if self.is_dash_strike else 7)
                                      * (1 - dist_l / reach_t) * prog))
                    px2   = sx + math.cos(rad) * dist_l
                    py2   = sy + math.sin(rad) * dist_l
                    seg   = pygame.Surface((r_l * 2 + 2, r_l * 2 + 2), pygame.SRCALPHA)
                    pygame.draw.circle(seg, (*flits_kl, alpha), (r_l + 1, r_l + 1), r_l)
                    surface.blit(seg, (int(px2) - r_l - 1, int(py2) - r_l - 1))
         # Charge visual — sword thrust forward
        if self.charge_timer > 0:
            reach_c = 55 + (CHARGE_FRAMES - self.charge_timer) * 3
            ex = sx + int(self.fx * reach_c)
            ey = sy + int(self.fy * reach_c)
            pygame.draw.line(surface, (255, 240, 120), (sx, sy), (ex, ey), 6)
            pygame.draw.circle(surface, (255, 255, 180), (ex, ey), 8)
        elif self.combo_timer > 0:
            prog = ease_in_out(1.0 - self.combo_timer / 10)
            step = self.combo_step
            if step == 1:
                zh_start = fh - 60; zh_end = fh + 60
                zh       = zh_start + prog * 120
                reach_t  = SWORD_REACH
            elif step == 2:
                zh_start = fh + 60; zh_end = fh - 60
                zh       = zh_start - prog * 120
                reach_t  = SWORD_REACH
            else:
                zh_start = zh_end = zh = fh
                reach_t  = SWORD_REACH * (1.5 if self.is_dash_strike else 1.3)
            # ... rest van de combo tekencode die al in jouw bestand staat
        else:
            rh2 = math.radians(fh + 40)
            pygame.draw.line(surface, C_SWORD, (sx, sy),
                (int(sx + math.cos(rh2) * 22), int(sy + math.sin(rh2) * 22)), 3)

        if self._has_shield() and block:
            sh  = math.radians(fh - 35)
            bsx = int(sx + math.cos(sh) * 22)
            bsy = int(sy + math.sin(sh) * 22)
            pygame.draw.circle(surface, C_SHIELD, (bsx, bsy), 13)
            pygame.draw.circle(surface, (230, 185, 90), (bsx, bsy), 13, 2)


# ══════════════════════════════════════════════════════════════════════════════
#  ENEMY
# ══════════════════════════════════════════════════════════════════════════════

class Enemy:
    _uid = 0

    @classmethod
    def new_id(cls):
        cls._uid += 1
        return cls._uid

    def __init__(self, x, y, enemy_type, hp_multiplier=1.0, damage_multiplier=1.0):
        self.x    = float(x); self.y = float(y)
        self.type = enemy_type
        self.id   = Enemy.new_id()
        self.damage_mult = damage_multiplier

        if enemy_type == "wolf":
            self.hp_max = ENEMY_BASE_HP * hp_multiplier * 0.8
            self.radius = 13
            self.speed  = ENEMY_SPEED * 1.1
        else:
            self.hp_max = ENEMY_BASE_HP * hp_multiplier
            self.radius = 14
            self.speed  = ENEMY_SPEED

        self.hp = self.hp_max
        self.fx = 0.0; self.fy = 1.0
        self.anim_timer      = 0
        self.attack_cooldown = 0
        self.flinch_timer    = 0
        self.flinch_dx       = 0.0; self.flinch_dy = 0.0
        self.windup_timer    = 0
        self.windup_dx       = 0.0; self.windup_dy = 0.0
        self.scale_x         = 1.0; self.scale_y   = 1.0
        self.hit_stop        = 0

        # Wolf state machine
        self.wolf_state      = "afstand"
        self.wolf_timer      = 0
        self.wolf_dash_dx    = 0.0; self.wolf_dash_dy   = 0.0
        self.wolf_dash_dir_x = 0.0; self.wolf_dash_dir_y = 0.0
        self.wolf_glow       = 0.0
        self.wolf_hit_player = False

        # Aggro
        self.aggro        = False
        self.aggro_range  = 200 if enemy_type == "wolf" else 260
        self.group_id     = 0
        self.patrol_angle = random.uniform(0, math.pi * 2)
        self.patrol_timer = random.randint(0, 120)

        # Burning DoT
        self.burning_timer = 0
        self.burning_tick  = 0

    # ── Damage ────────────────────────────────────────────────────────────────
    def take_damage(self, damage, from_x, from_y):
        self.hp -= damage
        knx, kny = normalize(self.x - from_x, self.y - from_y)
        self.flinch_timer = FLINCH_ENEMY
        self.flinch_dx    = knx * KNOCKBACK
        self.flinch_dy    = kny * KNOCKBACK
        self.scale_x = 1.6; self.scale_y = 0.5
        self.hit_stop = 4
        return self.hp <= 0

    def take_damage_swing(self, damage, kb_nx, kb_ny):
        self.hp -= damage
        kb = KNOCKBACK * (0.4 if self.type == "wolf" else 1.0)
        self.flinch_timer = FLINCH_ENEMY
        self.flinch_dx    = kb_nx * kb
        self.flinch_dy    = kb_ny * kb
        self.scale_x = 1.6; self.scale_y = 0.5
        self.hit_stop = 5
        return self.hp <= 0

    def take_damage_knockback(self, damage, from_x, from_y, knockback):
        self.hp -= damage
        knx, kny = normalize(self.x - from_x, self.y - from_y)
        self.flinch_timer = FLINCH_ENEMY
        self.flinch_dx    = knx * knockback
        self.flinch_dy    = kny * knockback
        self.scale_x = 1.6; self.scale_y = 0.5
        self.hit_stop = 4
        return self.hp <= 0

    # ── AI update ─────────────────────────────────────────────────────────────
    def update(self, sp_x, sp_y, is_blocked, player_facing_angle,
               player_blocking, player_flinch_cd):
        dvx  = sp_x - self.x; dvy = sp_y - self.y
        dist = math.hypot(dvx, dvy)
        self.fx, self.fy = normalize(dvx, dvy)

        if self.hit_stop > 0:
            self.hit_stop -= 1
            self.scale_x = lerp(self.scale_x, 1.0, 0.15)
            self.scale_y = lerp(self.scale_y, 1.0, 0.15)
            return None

        if not self.aggro:
            if dist < self.aggro_range or self.flinch_timer > 0:
                self.aggro = True
            else:
                self._update_patrol(is_blocked)
                if self.anim_timer      > 0: self.anim_timer      -= 1
                if self.attack_cooldown > 0: self.attack_cooldown -= 1
                self.scale_x = lerp(self.scale_x, 1.0, 0.1)
                self.scale_y = lerp(self.scale_y, 1.0, 0.1)
                return None

        if self.anim_timer      > 0: self.anim_timer      -= 1
        if self.attack_cooldown > 0: self.attack_cooldown -= 1

        self.scale_x = lerp(self.scale_x, 1.0, 0.15)
        self.scale_y = lerp(self.scale_y, 1.0, 0.15)

        if self.flinch_timer > 0:
            self.flinch_timer -= 1
            self._move(self.flinch_dx, self.flinch_dy, is_blocked)
            self.flinch_dx *= 0.8; self.flinch_dy *= 0.8
            return None

        if self.windup_timer > 0:
            self.windup_timer -= 1
            self._move(self.windup_dx, self.windup_dy, is_blocked)
            return None

        attack     = None
        reach      = 48
        acd_dur    = 90
        melee_dmg  = ENEMY_MELEE_DAMAGE * self.damage_mult
        arrow_dmg  = ARROW_DAMAGE       * self.damage_mult

        # ── Wolf AI ───────────────────────────────────────────────────────────
        if self.type == "wolf":
            WOLF_DISTANCE = 180
            WOLF_WINDUP_T = 30
            WOLF_DASH_T   = 28
            WOLF_REST_T   = 100
            WOLF_SPEED    = DODGE_SPEED * 1.9
            WOLF_DAMAGE   = ENEMY_MELEE_DAMAGE * 1.2 * self.damage_mult

            if self.wolf_timer > 0: self.wolf_timer -= 1

            if self.wolf_state == "afstand":
                self.wolf_glow = max(0.0, self.wolf_glow - 0.05)
                if dist > WOLF_DISTANCE + 30:
                    self.scale_x = lerp(self.scale_x, 1.2, 0.1)
                    self.scale_y = lerp(self.scale_y, 0.85, 0.1)
                    self._move(self.fx * self.speed, self.fy * self.speed, is_blocked)
                elif dist < WOLF_DISTANCE - 30:
                    self._move(-self.fx * self.speed * 0.7,
                               -self.fy * self.speed * 0.7, is_blocked)
                if self.attack_cooldown <= 0 and 60 < dist < WOLF_DISTANCE + 120:
                    self.wolf_state = "windup"
                    self.wolf_timer = WOLF_WINDUP_T

            elif self.wolf_state == "windup":
                self.wolf_glow = min(1.0, self.wolf_timer / WOLF_WINDUP_T * 1.2)
                self._move(-self.fx * 0.8, -self.fy * 0.8, is_blocked)
                self.scale_x = lerp(self.scale_x, 0.65, 0.15)
                self.scale_y = lerp(self.scale_y, 1.5,  0.15)
                if math.hypot(dvx, dvy) > 5:
                    self.fx, self.fy = normalize(dvx, dvy)
                if self.wolf_timer == 0:
                    self.wolf_state       = "dash"
                    self.wolf_timer       = WOLF_DASH_T
                    self.wolf_dash_dx     = self.fx * WOLF_SPEED
                    self.wolf_dash_dy     = self.fy * WOLF_SPEED
                    self.wolf_dash_dir_x  = self.fx
                    self.wolf_dash_dir_y  = self.fy
                    self.wolf_hit_player  = False
                    self.scale_x = 1.5; self.scale_y = 0.6

            elif self.wolf_state == "dash":
                self.wolf_glow = lerp(self.wolf_glow, 0.0, 0.2)
                self._move(self.wolf_dash_dx, self.wolf_dash_dy, is_blocked)
                if dist < 44 and player_flinch_cd <= 0 and not self.wolf_hit_player:
                    self.wolf_hit_player = True
                    attack = ("melee",
                              self.x - self.wolf_dash_dir_x * 40,
                              self.y - self.wolf_dash_dir_y * 40,
                              WOLF_DAMAGE)
                if self.wolf_timer == 0:
                    self.wolf_state      = "herstel"
                    self.wolf_timer      = WOLF_REST_T
                    self.attack_cooldown = WOLF_REST_T
                    self.scale_x = 1.4; self.scale_y = 0.7

            elif self.wolf_state == "herstel":
                self.wolf_glow = 0.0
                if dist < WOLF_DISTANCE:
                    self._move(-self.fx * self.speed, -self.fy * self.speed, is_blocked)
                if self.wolf_timer == 0:
                    self.wolf_state = "afstand"

        # ── Melee AI ──────────────────────────────────────────────────────────
        elif self.type == "melee":
            if dist > self.radius + 10:
                self.scale_x = lerp(self.scale_x, 1.2, 0.1)
                self.scale_y = lerp(self.scale_y, 0.85, 0.1)
                self._move(self.fx * self.speed, self.fy * self.speed, is_blocked)
            if dist < reach and self.attack_cooldown <= 0:
                self.anim_timer      = 20
                self.attack_cooldown = acd_dur
                self.windup_timer    = 6
                self.windup_dx = -self.fx * 1.5
                self.windup_dy = -self.fy * 1.5
                self.scale_x = 0.7; self.scale_y = 1.4
                if player_flinch_cd <= 0:
                    attack = ("melee", self.x, self.y, melee_dmg)

        # ── Ranged AI ─────────────────────────────────────────────────────────
        else:
            FLEE_DIST      = 130
            TARGET_DIST    = 240
            AIM_FRAMES     = 35
            SALVO_SIZE     = 3
            SALVO_INTERVAL = 8

            if not hasattr(self, 'aim_timer'):   self.aim_timer = 0
            if not hasattr(self, 'aim_dx'):
                self.aim_dx = self.fx; self.aim_dy = self.fy
            if not hasattr(self, 'salvo_count'): self.salvo_count = 0
            if not hasattr(self, 'salvo_timer'): self.salvo_timer = 0

            if dist < FLEE_DIST and self.aim_timer == 0:
                vx = -self.fx * 1.4 + self.fy * 0.5
                vy = -self.fy * 1.4 - self.fx * 0.5
                vl = math.hypot(vx, vy)
                if vl > 0: vx, vy = vx / vl, vy / vl
                self._move(vx * self.speed * 1.3, vy * self.speed * 1.3, is_blocked)
                self.scale_x = lerp(self.scale_x, 1.3, 0.12)
                self.scale_y = lerp(self.scale_y, 0.75, 0.12)
            elif self.aim_timer == 0 and self.salvo_timer == 0:
                if dist > TARGET_DIST + 30:
                    self._move(self.fx * self.speed * 0.8,
                               self.fy * self.speed * 0.8, is_blocked)
                elif dist < TARGET_DIST - 30:
                    self._move(-self.fx * 0.5, -self.fy * 0.5, is_blocked)

            if self.salvo_timer > 0:
                self.salvo_timer -= 1
                if self.salvo_timer == 0 and self.salvo_count > 0:
                    attack = ("arrow", self.x, self.y,
                              self.aim_dx * ARROW_SPEED, self.aim_dy * ARROW_SPEED,
                              arrow_dmg)
                    self.salvo_count -= 1
                    if self.salvo_count > 0:
                        self.salvo_timer = SALVO_INTERVAL

            elif self.aim_timer > 0:
                self.aim_timer -= 1
                self.fx, self.fy = self.aim_dx, self.aim_dy
                if self.aim_timer == 0:
                    self.scale_x = 1.4; self.scale_y = 0.6
                    attack = ("arrow", self.x, self.y,
                              self.aim_dx * ARROW_SPEED, self.aim_dy * ARROW_SPEED,
                              arrow_dmg)
                    if dist > FLEE_DIST * 1.5:
                        self.salvo_count = SALVO_SIZE - 1
                        self.salvo_timer = SALVO_INTERVAL

            elif self.attack_cooldown <= 0 and FLEE_DIST < dist < 400:
                cd = int(2.0 * FPS) if dist < TARGET_DIST else int(3.0 * FPS)
                self.attack_cooldown = cd + random.randint(-20, 40)
                self.aim_timer = AIM_FRAMES
                self.aim_dx    = self.fx; self.aim_dy = self.fy
                self.scale_x   = 0.8;    self.scale_y = 1.2

        # Burning DoT
        if self.burning_timer > 0:
            self.burning_timer -= 1
            self.burning_tick  -= 1
            if self.burning_tick <= 0:
                self.burning_tick = 120
                self.hp = max(0, self.hp - 8)
                self.scale_x = 1.3; self.scale_y = 0.75

        return attack

    def _update_patrol(self, is_blocked):
        self.patrol_timer -= 1
        if self.patrol_timer <= 0:
            self.patrol_angle += random.uniform(-1.2, 1.2)
            self.patrol_timer  = random.randint(60, 180)
        px = math.cos(self.patrol_angle) * self.speed * 0.3
        py = math.sin(self.patrol_angle) * self.speed * 0.3
        self._move(px, py, is_blocked)
        self.scale_x = lerp(self.scale_x, 1.1, 0.06)
        self.scale_y = lerp(self.scale_y, 0.92, 0.06)

    def _move(self, vx, vy, is_blocked):
        r  = self.radius - 2
        nx = self.x + vx; ny = self.y + vy
        if not any(is_blocked(int((nx + ox) // TILE), int((self.y + oy) // TILE))
                   for ox in (-r, 0, r) for oy in (-r, 0, r)):
            self.x = nx
        if not any(is_blocked(int((self.x + ox) // TILE), int((ny + oy) // TILE))
                   for ox in (-r, 0, r) for oy in (-r, 0, r)):
            self.y = ny

    # ── Drawing ───────────────────────────────────────────────────────────────
    def draw(self, surface, cam_x, cam_y):
        sx   = int(self.x - cam_x); sy = int(self.y - cam_y)
        r    = self.radius
        rw   = max(4, int(r * self.scale_x))
        rh_s = max(4, int(r * self.scale_y))
        knip = self.flinch_timer > 0 and (self.flinch_timer // 4) % 2 == 0

        if self.type == "wolf":
            if knip:
                kl = (255, 255, 255)
            else:
                g  = self.wolf_glow
                kl = (int(160 + g * 95), int(130 + g * 100), int(60 + g * 80))
        elif knip:
            kl = (255, 255, 255)
        elif self.type == "melee":
            kl = C_MELEE
        else:
            kl = C_RANGED

        pygame.draw.ellipse(surface, C_SHADOW, (sx - rw + 4, sy + rh_s - 4, rw * 2, rh_s))
        pygame.draw.ellipse(surface, kl, (sx - rw, sy - rh_s, rw * 2, rh_s * 2))

        if self.type == "wolf":
            g = self.wolf_glow
            if g > 0.1:
                glow_r = int(r * 1.6 + g * 12)
                ga     = int(g * 180)
                gs     = pygame.Surface((glow_r * 2 + 4, glow_r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(gs, (255, 220, 80, ga),
                                   (glow_r + 2, glow_r + 2), glow_r)
                surface.blit(gs, (sx - glow_r - 2, sy - glow_r - 2))

        pygame.draw.circle(surface, C_EYE,
            (int(sx + self.fx * int(r * 0.6)), int(sy + self.fy * int(r * 0.6))), 5)

        if not self.aggro:
            bob = int(math.sin(pygame.time.get_ticks() * 0.0015) * 5)
            zs  = pygame.font.Font(None, 22).render("z z z", True, (160, 185, 255))
            surface.blit(zs, (sx - zs.get_width() // 2, sy - rh_s - 20 + bob))

        if self.burning_timer > 0:
            puls   = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.015)
            burn_r = int(r * 1.4 + puls * 6)
            burn_a = int(120 + puls * 80)
            bs     = pygame.Surface((burn_r * 2 + 4, burn_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(bs, (255, int(80 + puls * 60), 0, burn_a),
                               (burn_r + 2, burn_r + 2), burn_r)
            surface.blit(bs, (sx - burn_r - 2, sy - burn_r - 2))

        bw    = r * 3
        ratio = max(0, self.hp / self.hp_max)
        pygame.draw.rect(surface, (80, 20, 20),  (sx - bw//2, sy - r - 10, bw, 6))
        pygame.draw.rect(surface, (220, 60, 60), (sx - bw//2, sy - r - 10, int(bw * ratio), 6))

        fh = math.degrees(math.atan2(self.fy, self.fx))
        if self.type == "melee":
            if self.anim_timer > 0:
                t_raw = 1.0 - self.anim_timer / 20
                prog  = ease_in_out(t_raw)
                zh    = fh - 50 + prog * 100
                rad   = math.radians(zh)
                pygame.draw.line(surface, C_SWORD, (sx, sy),
                    (int(sx + math.cos(rad) * 42), int(sy + math.sin(rad) * 42)), 4)
            elif self.windup_timer > 0:
                rh2 = math.radians(fh + 160)
                pygame.draw.line(surface, C_SWORD, (sx, sy),
                    (int(sx + math.cos(rh2) * 22), int(sy + math.sin(rh2) * 22)), 3)
            else:
                rh2 = math.radians(fh + 35)
                pygame.draw.line(surface, C_SWORD, (sx, sy),
                    (int(sx + math.cos(rh2) * 25), int(sy + math.sin(rh2) * 25)), 3)
        elif self.type == "ranged":
            bh = math.radians(fh)
            bx = int(sx + math.cos(bh) * 18); by = int(sy + math.sin(bh) * 18)
            pygame.draw.line(surface, (140, 100, 50), (sx, sy), (bx, by), 3)
            pygame.draw.circle(surface, (160, 120, 60), (bx, by), 5)
            aim_t = getattr(self, 'aim_timer', 0)
            if aim_t > 0:
                AIM_FRAMES = 35
                charge   = 1.0 - aim_t / AIM_FRAMES
                puls     = abs(math.sin(aim_t * 0.25))
                aim_kl   = (255, int(80 - charge * 60), int(80 - charge * 60))
                aim_len  = int(80 + charge * 80)
                aim_rad  = math.atan2(
                    self.aim_dy if hasattr(self, 'aim_dy') else self.fy,
                    self.aim_dx if hasattr(self, 'aim_dx') else self.fx)
                for seg in range(0, aim_len, 6):
                    t_seg = seg / aim_len
                    alpha = int((0.3 + 0.7 * charge) * (1 - t_seg * 0.7) * 220 * puls)
                    r_dot = max(1, int((1 - t_seg) * (3 + charge * 4)))
                    px3   = int(sx + math.cos(aim_rad) * (20 + seg))
                    py3   = int(sy + math.sin(aim_rad) * (20 + seg))
                    dot_s = pygame.Surface((r_dot * 2 + 2, r_dot * 2 + 2), pygame.SRCALPHA)
                    pygame.draw.circle(dot_s, (*aim_kl, alpha), (r_dot + 1, r_dot + 1), r_dot)
                    surface.blit(dot_s, (px3 - r_dot - 1, py3 - r_dot - 1))


# ══════════════════════════════════════════════════════════════════════════════
#  BOSS  —  The Forest Knight
# ══════════════════════════════════════════════════════════════════════════════

class Boss:
    MAX_HP    = 400.0
    RADIUS    = 32
    SPEED     = 1.6
    COLOR_P1  = (55,  90,  45)
    COLOR_P2  = (110, 30,  20)
    COLOR_EYE = (200, 80, 255)

    MELEE_WINDUP  = 22
    MELEE_FRAMES  = 16
    MELEE_ACD     = 90
    MELEE_DAMAGE  = 35.0
    MELEE_RANGE   = 68

    CHARGE_WINDUP = 38
    CHARGE_T      = 22
    CHARGE_SPEED  = DODGE_SPEED * 2.2
    CHARGE_DAMAGE = 28.0
    CHARGE_ACD    = 150

    STAMP_WINDUP  = 30
    STAMP_DAMAGE  = 30.0
    STAMP_MAX_R   = 180
    STAMP_SPEED   = 4.5
    STAMP_ACD     = 200

    def __init__(self, x, y, damage_mult=1.0):
        self.x = float(x); self.y = float(y)
        self.type        = "boss"
        self.id          = Enemy.new_id()
        self.hp_max      = self.MAX_HP * damage_mult
        self.hp          = self.hp_max
        self.radius      = self.RADIUS
        self.damage_mult = damage_mult

        self.fx = 0.0; self.fy = 1.0
        self.scale_x = 1.0; self.scale_y = 1.0
        self.flinch_timer = 0
        self.flinch_dx    = 0.0; self.flinch_dy = 0.0
        self.hit_stop   = 0
        self.anim_timer = 0

        self.state        = "volgen"
        self.state_timer  = 0
        self.attack_cooldown = 60

        self.charge_dx         = 0.0; self.charge_dy = 0.0
        self.charge_hit_player = False

        self.shockwave_rings = []

        self.phase2         = False
        self.phase2_trigger = False
        self.glow           = 0.0

        self.aggro     = True
        self.group_id  = 0
        self.burning_timer = 0; self.burning_tick = 0

    def take_damage(self, damage, from_x, from_y):
        self.hp -= damage
        knx, kny = normalize(self.x - from_x, self.y - from_y)
        self.flinch_timer = FLINCH_ENEMY
        self.flinch_dx    = knx * KNOCKBACK * 0.5
        self.flinch_dy    = kny * KNOCKBACK * 0.5
        self.scale_x = 1.5; self.scale_y = 0.6
        self.hit_stop = 5
        if not self.phase2 and self.hp <= self.hp_max * 0.5:
            self.phase2         = True
            self.phase2_trigger = True
        return self.hp <= 0

    def take_damage_swing(self, damage, kb_nx, kb_ny):
        return self.take_damage(damage, self.x - kb_nx * 50, self.y - kb_ny * 50)

    def take_damage_knockback(self, damage, from_x, from_y, knockback):
        return self.take_damage(damage, from_x, from_y)

    def update(self, sp_x, sp_y, is_blocked, player_facing_angle,
               player_blocking, player_flinch_cd):
        dvx  = sp_x - self.x; dvy = sp_y - self.y
        dist = math.hypot(dvx, dvy)
        self.fx, self.fy = normalize(dvx, dvy)

        if self.hit_stop > 0:
            self.hit_stop -= 1
            self.scale_x = lerp(self.scale_x, 1.0, 0.12)
            self.scale_y = lerp(self.scale_y, 1.0, 0.12)
            return None, False

        if self.anim_timer      > 0: self.anim_timer      -= 1
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        if self.state_timer     > 0: self.state_timer     -= 1

        if self.flinch_timer > 0:
            self.flinch_timer -= 1
            self._move(self.flinch_dx * (self.flinch_timer / FLINCH_ENEMY),
                       self.flinch_dy * (self.flinch_timer / FLINCH_ENEMY), is_blocked)

        phase2_trigger = self.phase2_trigger
        if self.phase2_trigger:
            self.phase2_trigger = False
            self.state       = "fase2_intro"
            self.state_timer = 50
            self.scale_x = 1.8; self.scale_y = 0.3

        self.scale_x = lerp(self.scale_x, 1.0, 0.1)
        self.scale_y = lerp(self.scale_y, 1.0, 0.1)
        self.glow    = lerp(self.glow, 0.7 if self.phase2 else 0.0,
                            0.03 if self.phase2 else 0.05)

        spd    = self.SPEED * (1.3 if self.phase2 else 1.0)
        attack = None

        if self.state == "fase2_intro":
            if self.state_timer == 0:
                self.state = "volgen"
            return attack, phase2_trigger

        elif self.state == "volgen":
            if dist > self.MELEE_RANGE + 15:
                self.scale_x = lerp(self.scale_x, 1.15, 0.08)
                self.scale_y = lerp(self.scale_y, 0.88, 0.08)
                self._move(self.fx * spd, self.fy * spd, is_blocked)
            if self.attack_cooldown <= 0:
                if dist > 180 and self.phase2 and random.random() < 0.4:
                    self._start_stamp()
                elif dist > 130 and random.random() < 0.45:
                    self._start_charge()
                else:
                    self._start_melee()

        elif self.state == "melee_windup":
            self._move(-self.fx * 0.6, -self.fy * 0.6, is_blocked)
            self.scale_x = lerp(self.scale_x, 0.7,  0.12)
            self.scale_y = lerp(self.scale_y, 1.45, 0.12)
            if self.state_timer == 0:
                self.state       = "melee_aanval"
                self.state_timer = self.MELEE_FRAMES
                self.anim_timer  = self.MELEE_FRAMES
                self.scale_x = 1.6; self.scale_y = 0.5
                if player_flinch_cd <= 0 and dist < self.MELEE_RANGE + 25:
                    attack = ("melee", self.x, self.y,
                              self.MELEE_DAMAGE * self.damage_mult)

        elif self.state == "melee_aanval":
            if self.state_timer == 0:
                self.state       = "herstel"
                self.state_timer = 35
                self.attack_cooldown = int(self.MELEE_ACD * (0.75 if self.phase2 else 1.0))

        elif self.state == "charge_windup":
            self._move(-self.fx * 0.5, -self.fy * 0.5, is_blocked)
            self.scale_x = lerp(self.scale_x, 0.6, 0.12)
            self.scale_y = lerp(self.scale_y, 1.6, 0.12)
            if self.state_timer == self.CHARGE_WINDUP // 2:
                self.charge_dx         = self.fx * self.CHARGE_SPEED
                self.charge_dy         = self.fy * self.CHARGE_SPEED
                self.charge_hit_player = False
            if self.state_timer == 0:
                if self.charge_dx == 0 and self.charge_dy == 0:
                    self.charge_dx         = self.fx * self.CHARGE_SPEED
                    self.charge_dy         = self.fy * self.CHARGE_SPEED
                    self.charge_hit_player = False
                self.state       = "charge"
                self.state_timer = self.CHARGE_T
                self.scale_x = 1.7; self.scale_y = 0.45

        elif self.state == "charge":
            self._move(self.charge_dx, self.charge_dy, is_blocked)
            if (dist < self.RADIUS + 30 and not self.charge_hit_player
                    and player_flinch_cd <= 0):
                self.charge_hit_player = True
                attack = ("charge", self.x, self.y,
                          self.CHARGE_DAMAGE * self.damage_mult)
            if self.state_timer == 0:
                self.state       = "herstel"
                self.state_timer = 50
                self.attack_cooldown = int(self.CHARGE_ACD * (0.75 if self.phase2 else 1.0))

        elif self.state == "stamp_windup":
            self.scale_x = lerp(self.scale_x, 0.75, 0.1)
            self.scale_y = lerp(self.scale_y, 1.5,  0.1)
            if self.state_timer == 0:
                self.state       = "stamp_actief"
                self.state_timer = 10
                self.scale_x = 2.0; self.scale_y = 0.3
                self.shockwave_rings = [{"x": self.x, "y": self.y, "r": 0,
                                         "max_r": self.STAMP_MAX_R, "alpha": 220}]

        elif self.state == "stamp_actief":
            if self.state_timer == 0:
                self.state       = "herstel"
                self.state_timer = 45
                self.attack_cooldown = self.STAMP_ACD

        elif self.state == "herstel":
            if dist < 120:
                self._move(-self.fx * spd * 0.6, -self.fy * spd * 0.6, is_blocked)
            if self.state_timer == 0:
                self.state = "volgen"

        for ring in self.shockwave_rings:
            ring["r"]    += self.STAMP_SPEED
            ring["alpha"] = max(0, int(ring["alpha"] * (1 - ring["r"] / ring["max_r"])))
        self.shockwave_rings = [rg for rg in self.shockwave_rings if rg["r"] < rg["max_r"]]

        if self.burning_timer > 0:
            self.burning_timer -= 1
            self.burning_tick  -= 1
            if self.burning_tick <= 0:
                self.burning_tick = 120
                self.hp = max(0, self.hp - 8)
                self.scale_x = 1.3; self.scale_y = 0.75

        return attack, phase2_trigger

    def _start_melee(self):
        self.state       = "melee_windup"
        self.state_timer = int(self.MELEE_WINDUP * (0.8 if self.phase2 else 1.0))

    def _start_charge(self):
        self.state       = "charge_windup"
        self.state_timer = int(self.CHARGE_WINDUP * (0.8 if self.phase2 else 1.0))
        self.charge_dx   = 0.0; self.charge_dy = 0.0

    def _start_stamp(self):
        self.state       = "stamp_windup"
        self.state_timer = self.STAMP_WINDUP

    def _move(self, vx, vy, is_blocked):
        r  = self.radius - 2
        nx = self.x + vx; ny = self.y + vy
        if not any(is_blocked(int((nx + ox) // TILE), int((self.y + oy) // TILE))
                   for ox in (-r, 0, r) for oy in (-r, 0, r)):
            self.x = nx
        if not any(is_blocked(int((self.x + ox) // TILE), int((ny + oy) // TILE))
                   for ox in (-r, 0, r) for oy in (-r, 0, r)):
            self.y = ny

    def draw(self, surface, cam_x, cam_y):
        sx   = int(self.x - cam_x); sy = int(self.y - cam_y)
        r    = self.radius
        rw   = int(r * self.scale_x); rh = int(r * self.scale_y)
        rh_s = max(1, rh)

        for ring in self.shockwave_rings:
            rx = int(ring["x"] - cam_x); ry = int(ring["y"] - cam_y)
            if ring["alpha"] > 5:
                rs = pygame.Surface((int(ring["r"]) * 2 + 4, int(ring["r"]) * 2 + 4),
                                    pygame.SRCALPHA)
                pygame.draw.circle(rs, (255, 200, 50, ring["alpha"]),
                                   (int(ring["r"]) + 2, int(ring["r"]) + 2),
                                   int(ring["r"]), 4)
                surface.blit(rs, (rx - int(ring["r"]) - 2, ry - int(ring["r"]) - 2))

        if self.state == "charge_windup":
            windup_total = int(self.CHARGE_WINDUP * (0.8 if self.phase2 else 1.0))
            prog     = 1.0 - self.state_timer / max(1, windup_total)
            line_len = int(120 * prog + 30)   # lijn zichtbaar vanaf frame 1
            alpha    = int(60 + prog * 195)   # begint al zichtbaar
            ex    = int(sx + self.fx * line_len)
            ey    = int(sy + self.fy * line_len)
            cs    = pygame.Surface((surface.get_width(), surface.get_height()),
                                   pygame.SRCALPHA)
            pygame.draw.line(cs, (255, 60, 20, alpha), (sx, sy), (ex, ey), 5)
            # Driehoek aan het einde als pijl
            perp_x = -self.fy * 8; perp_y = self.fx * 8
            tip = (ex, ey)
            left  = (int(ex - self.fx * 18 + perp_x), int(ey - self.fy * 18 + perp_y))
            right = (int(ex - self.fx * 18 - perp_x), int(ey - self.fy * 18 - perp_y))
            pygame.draw.polygon(cs, (255, 80, 20, alpha), [tip, left, right])
            surface.blit(cs, (0, 0))

        if self.glow > 0.05:
            glow_r = int(r * 1.8 + self.glow * 20)
            ga     = int(self.glow * 140)
            gs     = pygame.Surface((glow_r * 2 + 4, glow_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(gs, (200, 40, 20, ga), (glow_r + 2, glow_r + 2), glow_r)
            surface.blit(gs, (sx - glow_r - 2, sy - glow_r - 2))

        pygame.draw.ellipse(surface, C_SHADOW, (sx - rw + 4, sy + rh_s - 4, rw * 2, rh_s))

        kl = self.COLOR_P2 if self.phase2 else self.COLOR_P1
        if self.flinch_timer > 0 and (self.flinch_timer // 4) % 2 == 0:
            kl = (220, 220, 220)
        pygame.draw.ellipse(surface, kl, (sx - rw, sy - rh_s, rw * 2, rh_s * 2))
        pygame.draw.ellipse(surface, (200, 180, 150),
                            (sx - rw, sy - rh_s, rw * 2, rh_s * 2), 3)

        if self.burning_timer > 0:
            puls = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.015)
            br   = int(r * 1.4 + puls * 8)
            ba   = int(120 + puls * 80)
            bs   = pygame.Surface((br * 2 + 4, br * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(bs, (255, int(80 + puls * 60), 0, ba), (br + 2, br + 2), br)
            surface.blit(bs, (sx - br - 2, sy - br - 2))

        pygame.draw.circle(surface, self.COLOR_EYE,
            (int(sx + self.fx * int(r * 0.55)), int(sy + self.fy * int(r * 0.55))), 7)

        fh = math.degrees(math.atan2(self.fy, self.fx))
        if self.state in ("melee_windup", "melee_aanval") and self.anim_timer > 0:
            t_raw = 1.0 - self.anim_timer / self.MELEE_FRAMES
            prog  = ease_in_out(t_raw)
            zh    = fh - 70 + prog * 140
            rad   = math.radians(zh)
            pygame.draw.line(surface, (200, 200, 230), (sx, sy),
                (int(sx + math.cos(rad) * 58), int(sy + math.sin(rad) * 58)), 6)
        else:
            rh2 = math.radians(fh + 30)
            pygame.draw.line(surface, C_SWORD, (sx, sy),
                (int(sx + math.cos(rh2) * 40), int(sy + math.sin(rh2) * 40)), 5)

        bw    = r * 4
        ratio = max(0, self.hp / self.hp_max)
        pygame.draw.rect(surface, (80, 20, 20),  (sx - bw//2, sy - r - 14, bw, 8))
        kl_hp = (255, 100, 20) if self.phase2 else (220, 60, 60)
        pygame.draw.rect(surface, kl_hp, (sx - bw//2, sy - r - 14, int(bw * ratio), 8))
        pygame.draw.rect(surface, (200, 180, 150), (sx - bw//2, sy - r - 14, bw, 8), 1)


# ══════════════════════════════════════════════════════════════════════════════
#  ARROW
# ══════════════════════════════════════════════════════════════════════════════

class Arrow:
    def __init__(self, x, y, dx, dy, damage=None):
        self.x = float(x); self.y = float(y)
        self.dx     = dx; self.dy = dy
        self.damage = damage if damage is not None else ARROW_DAMAGE

    def update(self, is_blocked):
        self.x += self.dx; self.y += self.dy
        return is_blocked(int(self.x // TILE), int(self.y // TILE))

    def draw(self, surface, cam_x, cam_y):
        sx = int(self.x - cam_x); sy = int(self.y - cam_y)
        ex = int(self.x + self.dx * 10 - cam_x)
        ey = int(self.y + self.dy * 10 - cam_y)
        pygame.draw.line(surface, C_ARROW, (sx, sy), (ex, ey), 3)
        pygame.draw.circle(surface, (230, 190, 110), (sx, sy), 4)