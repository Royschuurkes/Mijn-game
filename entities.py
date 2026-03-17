# entities.py - Player, Enemy, Boss, Arrow
import math, random
import pygame
from constants import *
from weapons import get_weapon, get_shield, combo_step_data, combo_length, is_finisher
from enemy_defs import get_enemy
from boss_defs import get_boss


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

        # Shield / guard break / parry
        self.guard_break_timer = 0
        self.shield_broken     = False
        self.parry_timer       = 0

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

    # ── Equipment helpers ────────────────────────────────────────────────────
    def _weapon(self):
        return get_weapon(self.save.get("main_hand", "sword"))

    def _shield(self):
        return get_shield(self.save.get("off_hand"))

    def _has_shield(self):
        return self._shield() is not None

    def _can_block(self):
        """Can the player block? True if shield equipped OR weapon has can_block."""
        if self._shield() is not None:
            return True
        return self._weapon().get("can_block", False)

    def _block_stats(self):
        """Return (stamina_cost, block_reduction, parry_window, parry_stagger) from shield or weapon."""
        shield = self._shield()
        if shield:
            return (shield["stamina_cost"], shield.get("block_reduction", 0.7),
                    shield["parry_window"], shield["parry_stagger"])
        weapon = self._weapon()
        if weapon.get("can_block"):
            return (weapon["block_stamina"], weapon["block_reduction"],
                    weapon["parry_window"], weapon["parry_stagger"])
        return None

    def has_item(self, key):
        return key in self.save.get("items", [])

    def has_active_effect(self, key):
        return self.save.get("active_effects", {}).get(key, 0) > 0

    # ── Attack input ──────────────────────────────────────────────────────────
    def _try_attack(self, block=False):
        weapon    = self._weapon()
        stam_cost = weapon["stamina_cost"]
        n_combo   = combo_length(weapon)

        if block: return
        if self.stamina < stam_cost: return

        # ── Charge attack: tijdens dodge of sprint ────────────────────────────
        can_charge = (
            (self.dodge_timer > 0 or self._sprint_active)
            and self.charge_timer == 0
            and self.can_attack
            and self.finisher_windup == 0
        )
        if can_charge:
            self.stamina       -= stam_cost
            self.stamina_delay  = STAMINA_DELAY
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

        next_step = (self.combo_step % n_combo) + 1
        cur_data  = combo_step_data(weapon, max(1, self.combo_step)) if self.combo_step > 0 else None
        next_data = combo_step_data(weapon, next_step)
        cur_cd    = cur_data["cooldown"] if cur_data else 0

        can = (self.combo_timer == 0 and self.finisher_windup == 0
               and self.swing_cooldown == 0 and self.post_combo_cooldown == 0
               and self.can_attack and self.dodge_timer == 0)
        if (self.combo_window > 0 and self.combo_step > 0
                and not is_finisher(weapon, self.combo_step)
                and self.combo_timer == 0 and self.swing_cooldown == 0
                and self.post_combo_cooldown == 0):
            can = True

        if not can:
            if (self.combo_timer > 0 and self.combo_step > 0
                    and not is_finisher(weapon, self.combo_step)):
                self.swing_cooldown = min(self.swing_cooldown + 8, cur_cd + 8)
            return

        if is_finisher(weapon, next_step):
            # About to do finisher — enter windup
            self.combo_step      = next_step - 1  # stay on pre-finisher step
            self.combo_timer     = 0
            self.combo_window    = 0
            self.finisher_windup = next_data.get("windup", 16)
            self.is_dash_strike  = False
            self.facing_locked   = True
            self.lock_fx = self.fx; self.lock_fy = self.fy
            import sound as _snd; _snd.play("finisher_charge")
        else:
            self.combo_step        = next_step
            self.combo_timer       = next_data["swing_frames"]
            self.combo_window      = next_data["window"]
            self.combo_reset_timer = 0
            self.is_dash_strike    = False
            import sound as _snd
            _snd.play("sword_swing_1" if self.combo_step == 1 else "sword_swing_2")

        self.stamina          -= stam_cost
        self.stamina_delay     = STAMINA_DELAY
        self.swing_cooldown    = next_data["cooldown"]
        self.hit_ids           = set()
        self._combo_idle_timer = 0

        if not self.finisher_windup:
            self.lock_fx = self.fx; self.lock_fy = self.fy
            self.facing_locked = True
            sq = next_data.get("swing_squash", (1.3, 0.75))
            self.scale_x = sq[0]; self.scale_y = sq[1]

    # ── Event handling ────────────────────────────────────────────────────────
    def handle_events(self, events, block=False):
        COMBO_TIMEOUT = 22
        weapon = self._weapon()
        cur_swing = combo_step_data(weapon, max(1, self.combo_step))["swing_frames"] if self.combo_step > 0 else 10

        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                combo_elapsed = cur_swing - self.combo_timer
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
                    self.stamina            -= STAMINA_DODGE
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

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self._try_attack(block)

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
                stats = self._block_stats()
                if stats and not self.shield_broken:
                    self.parry_timer = stats[2]  # parry_window

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
                  and math.hypot(mx, my) > 0.1
                  and self.stamina > 0)
        self._sprint_active = sprint
        if sprint:
            self.stamina = max(0, self.stamina - SPRINT_STAMINA)

        weapon     = self._weapon()
        n_combo    = combo_length(weapon)
        cur_data   = combo_step_data(weapon, max(1, self.combo_step)) if self.combo_step > 0 else None
        cur_swing  = cur_data["swing_frames"] if cur_data else 10
        combo_elapsed = cur_swing - self.combo_timer

        # Speed
        if self.dodge_timer > 0:
            speed = DODGE_SPEED + get_bonus_dodge(self.save)
        elif self.finisher_windup > 0:
            speed = 0.0
        elif self.combo_timer > 0:
            if combo_elapsed < 2:                           speed = 0.0
            elif is_finisher(weapon, self.combo_step):      speed = 0.0
            else:                                           speed = PLAYER_SPEED * 0.25
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
        elif self.combo_timer > 0 and is_finisher(weapon, self.combo_step):
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
                step1 = combo_step_data(weapon, 1)
                self.is_charging         = False
                self.combo_step          = 1
                self.combo_timer         = step1["swing_frames"]
                self.combo_window        = step1["window"]
                self.dash_strike_window  = 0
                self.is_dash_strike      = False
                self.hit_ids             = set()
                self.lock_fx = self.fx; self.lock_fy = self.fy
                self.facing_locked       = True
                self.swing_cooldown      = step1["cooldown"]
                sq = step1.get("swing_squash", (1.3, 0.75))
                self.scale_x = sq[0]; self.scale_y = sq[1]
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

        # Parry window countdown
        if self.parry_timer > 0:
            self.parry_timer -= 1

        # Stamina regen
        if self.stamina_delay > 0:
            self.stamina_delay -= 1
        elif not block and not sprint and self.stamina < self.stamina_max:
            self.stamina = min(self.stamina_max,
                               self.stamina + (self.stamina_max * STAMINA_REGEN_PCT / FPS))

        # Active effects countdown
        for eff in self.save.get("active_effects", {}):
            if self.save["active_effects"][eff] > 0:
                self.save["active_effects"][eff] -= 1

        # Finisher windup
        if self.finisher_windup > 0:
            self.finisher_windup -= 1
            if self.finisher_windup == 0:
                fin_step = n_combo  # finisher is always last step
                fin_data = combo_step_data(weapon, fin_step)
                self.combo_step     = fin_step
                self.combo_timer    = fin_data["swing_frames"]
                self.combo_window   = fin_data["window"]
                self.is_dash_strike = False
                self.hit_ids        = set()
                sq = fin_data.get("swing_squash", (0.6, 1.5))
                self.scale_x = sq[0]; self.scale_y = sq[1]

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
        if (self.combo_timer == 0 and is_finisher(weapon, self.combo_step)
                and not self._post_combo_triggered):
            self._post_combo_triggered = True
            fin_data = combo_step_data(weapon, self.combo_step)
            recovery = fin_data["cooldown"]
            self.post_combo_cooldown   = recovery
            self.swing_cooldown        = recovery
        elif self.combo_timer > 0 or not is_finisher(weapon, self.combo_step):
            self._post_combo_triggered = False

        # Unlock facing when done
        if self.combo_timer == 0 and self.combo_window == 0:
            self.facing_locked = False

        # Buffered input
        if self.combo_buffered and self.combo_timer == 0:
            self.combo_buffered = False
            stam_cost = weapon["stamina_cost"]
            if (self.stamina >= stam_cost and self.can_attack
                    and self.dodge_timer == 0):
                next_s    = (self.combo_step % n_combo) + 1
                next_d    = combo_step_data(weapon, next_s)
                self.combo_step        = next_s
                self.combo_timer       = next_d["swing_frames"]
                self.combo_window      = next_d["window"]
                self.combo_reset_timer = 0
                self.is_dash_strike    = False
                self.stamina          -= stam_cost
                self.stamina_delay     = STAMINA_DELAY
                self.hit_ids           = set()
                self.lock_fx           = self.fx
                self.lock_fy           = self.fy
                self.facing_locked     = True

    # ── Damage / block ────────────────────────────────────────────────────────
    def take_damage(self, damage, from_x, from_y):
        if self.dodge_timer > 0 or self.flinch_cooldown > 0: return False
        if self.has_active_effect("invis"): return False
        if getattr(self, "god_mode", False): return False
        self.hp = max(0, self.hp - damage)
        knx, kny = normalize(self.x - from_x, self.y - from_y)
        self.flinch_timer    = FLINCH_PLAYER
        self.flinch_cooldown = FLINCH_CD_PLAYER
        self.flinch_dx       = knx * KNOCKBACK
        self.flinch_dy       = kny * KNOCKBACK
        self.hit_flash_timer = 8
        return True

    def handle_block(self, from_x, from_y, stamina_cost=None, can_parry=True):
        stats = self._block_stats()
        if not stats:
            return False
        if stamina_cost is None:
            stamina_cost = stats[0]  # block stamina cost
        if self.shield_broken:
            return False

        # Parry: block pressed within the parry window → no stamina cost, stagger enemy
        if can_parry and self.parry_timer > 0:
            self.parry_timer = 0
            self.stamina_delay = STAMINA_DELAY
            self.scale_x = 1.3; self.scale_y = 0.7
            return "parry"

        # Normal block
        if self.stamina >= stamina_cost:
            self.stamina      -= stamina_cost
            self.stamina_delay = STAMINA_DELAY
            knx, kny = normalize(self.x - from_x, self.y - from_y)
            self.flinch_dx    = knx * 3.5
            self.flinch_dy    = kny * 3.5
            self.flinch_timer = 6
            self.scale_x = 0.85; self.scale_y = 1.2
            return "block"
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

        weapon = self._weapon()
        step   = self.combo_step
        sdata  = combo_step_data(weapon, step)
        fh     = math.degrees(math.atan2(self.fy, self.fx))
        prog   = ease_in_out(1.0 - self.combo_timer / sdata["swing_frames"])

        base_damage = weapon["damage"] + get_bonus_damage(self.save)
        if self.has_item("fire_damage") or self.has_active_effect("fire_potion"):
            base_damage *= 1.25
        if self.has_item("berserker"):
            hp_ratio = max(0.0, 1.0 - self.hp / self.hp_max)
            base_damage *= (1.0 + hp_ratio * 0.8)

        reach     = weapon["reach"] * sdata.get("reach_mult", 1.0)
        if self.is_dash_strike and is_finisher(weapon, step):
            reach *= 1.15  # extra reach on dash-strike finisher
        tolerance = sdata["tolerance"]
        arc       = sdata["arc"]
        anim      = sdata["anim"]

        # Calculate swing heading based on animation type
        swing_h = self._calc_swing_heading(fh, anim, arc, prog)

        # Damage
        damage = base_damage * sdata["damage_mult"]
        if is_finisher(weapon, step) and self.has_item("combo_master"):
            damage *= 1.5
        if self.is_dash_strike and is_finisher(weapon, step):
            damage = base_damage * 1.8  # dash-strike finisher override

        kb = weapon["knockback"] * sdata.get("knockback_mult", 1.0)

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

    def _calc_swing_heading(self, fh, anim, arc, prog):
        """Calculate the current swing angle based on animation type."""
        half = arc / 2
        if anim == "sweep_right":
            return fh - half + prog * arc
        elif anim == "sweep_left":
            return fh + half - prog * arc
        elif anim == "wide_sweep":
            return fh - half + prog * arc
        elif anim in ("thrust", "stab", "overhead"):
            return fh
        return fh
    
    def charge_hits(self, targets):
        """Hit detection during the charge dash itself."""
        if self.charge_timer <= 0:
            return []
        hits = []
        weapon = self._weapon()
        base_damage = (weapon["damage"] + get_bonus_damage(self.save)) * weapon["charge_damage_mult"]
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

        weapon = self._weapon()
        shield = self._shield()

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
            fin_data   = combo_step_data(weapon, combo_length(weapon))
            windup_max = fin_data.get("windup", 16)
            charge     = max(0.0, 1.0 - fw / windup_max)
            glow_r     = max(4, int(18 + charge * 14))
            glow_alpha = int(max(0, min(255, charge * 220)))
            puls       = abs(math.sin(fw * 0.6))
            g_kl       = (255, max(0, min(255, int(180 + puls * 75))), 50, glow_alpha)
            gs = pygame.Surface((glow_r * 2 + 4, glow_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(gs, g_kl, (glow_r + 2, glow_r + 2),
                               glow_r, max(2, int(charge * 6)))
            surface.blit(gs, (sx - glow_r - 2, sy - glow_r - 2))

        fh  = math.degrees(math.atan2(self.fy, self.fx))
        w_color     = weapon["color"]
        w_color_tip = weapon["color_tip"]

        # Charge visual — weapon thrust forward
        if self.charge_timer > 0:
            reach_c = 55 + (CHARGE_FRAMES - self.charge_timer) * 3
            ex = sx + int(self.fx * reach_c)
            ey = sy + int(self.fy * reach_c)
            pygame.draw.line(surface, (255, 240, 120), (sx, sy), (ex, ey), 6)
            pygame.draw.circle(surface, (255, 255, 180), (ex, ey), 8)

        elif self.combo_timer > 0:
            step  = self.combo_step
            sdata = combo_step_data(weapon, step)
            prog  = ease_in_out(1.0 - self.combo_timer / sdata["swing_frames"])
            arc   = sdata["arc"]
            anim  = sdata["anim"]
            reach_t = weapon["reach"] * sdata.get("reach_mult", 1.0)
            if self.is_dash_strike and is_finisher(weapon, step):
                reach_t *= 1.15

            half    = arc / 2
            zh      = self._calc_swing_heading(fh, anim, arc, prog)
            rad     = math.radians(zh)

            # Weapon line
            ex  = sx + math.cos(rad) * reach_t
            ey  = sy + math.sin(rad) * reach_t
            lkl = (255, 220, 50) if self.is_dash_strike else w_color
            pygame.draw.line(surface, lkl, (sx, sy), (int(ex), int(ey)),
                             6 if self.is_dash_strike else 5)
            tkl = (255, 255, 100) if self.is_dash_strike else w_color_tip
            pygame.draw.circle(surface, tkl, (int(ex), int(ey)),
                               7 if self.is_dash_strike else 5)

            # Trail effects based on animation type
            if anim in ("sweep_right", "sweep_left", "wide_sweep") and prog > 0.05:
                zh_start = self._calc_swing_heading(fh, anim, arc, 0.0)
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

            elif anim in ("thrust", "stab"):
                # Forward thrust trail
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

            elif anim == "overhead":
                # Overhead smash — impact ring effect
                impact_r = int(reach_t * 0.6 * prog)
                if impact_r > 4:
                    impact_alpha = int(180 * (1 - prog * 0.5))
                    gs = pygame.Surface((impact_r * 2 + 4, impact_r * 2 + 4), pygame.SRCALPHA)
                    pygame.draw.circle(gs, (255, 200, 100, impact_alpha),
                                       (impact_r + 2, impact_r + 2), impact_r, 3)
                    surface.blit(gs, (int(ex) - impact_r - 2, int(ey) - impact_r - 2))

        else:
            # Idle weapon position
            rh2 = math.radians(fh + 40)
            idle_reach = min(22, weapon["reach"] * 0.25)
            pygame.draw.line(surface, w_color, (sx, sy),
                (int(sx + math.cos(rh2) * idle_reach), int(sy + math.sin(rh2) * idle_reach)), 3)

        # Block visual
        if block and self._can_block():
            if shield:
                sh  = math.radians(fh - 35)
                bsx = int(sx + math.cos(sh) * 22)
                bsy = int(sy + math.sin(sh) * 22)
                s_color = shield["color"]
                s_rim   = shield["color_rim"]
                pygame.draw.circle(surface, s_color, (bsx, bsy), 13)
                pygame.draw.circle(surface, s_rim, (bsx, bsy), 13, 2)
            else:
                # Weapon block: draw weapon held across body
                bh = math.radians(fh - 50)
                b_len = min(28, weapon["reach"] * 0.32)
                bx1 = int(sx + math.cos(bh) * 10)
                by1 = int(sy + math.sin(bh) * 10)
                bx2 = int(sx + math.cos(bh) * (10 + b_len))
                by2 = int(sy + math.sin(bh) * (10 + b_len))
                pygame.draw.line(surface, w_color_tip, (bx1, by1), (bx2, by2), 4)
                pygame.draw.line(surface, w_color, (bx1, by1), (bx2, by2), 2)


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
        self.edef = get_enemy(enemy_type)

        self.hp_max    = ENEMY_BASE_HP * hp_multiplier * self.edef["hp_mult"]
        self.exp_value = int(self.edef.get("exp", 10) * hp_multiplier)
        self.radius = self.edef["radius"]
        self.speed  = ENEMY_SPEED * self.edef["speed_mult"]

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

        # Ranged state
        self.aim_timer   = 0
        self.aim_dx      = 0.0; self.aim_dy = 0.0
        self.salvo_count = 0
        self.salvo_timer = 0

        # Aggro
        self.aggro        = False
        self.aggro_range  = self.edef["aggro_range"]
        self.group_id     = 0
        self.patrol_angle = random.uniform(0, math.pi * 2)
        self.patrol_timer = random.randint(0, 120)
        # Wolves sleep until aggroed; other enemies patrol
        self.sleeping     = (self.edef["ai"] == "wolf")

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

    def take_damage_swing(self, damage, kb_nx, kb_ny, hitstop=5, hit_squash=None):
        self.hp -= damage
        kb = KNOCKBACK * self.edef["kb_mult"]
        self.flinch_timer = FLINCH_ENEMY
        self.flinch_dx    = kb_nx * kb
        self.flinch_dy    = kb_ny * kb
        sq = hit_squash or (1.6, 0.5)
        self.scale_x = sq[0]; self.scale_y = sq[1]
        self.hit_stop = hitstop
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
                self.aggro    = True
                self.sleeping = False
            else:
                self._update_patrol(is_blocked)
                if self.anim_timer      > 0: self.anim_timer      -= 1
                if self.attack_cooldown > 0: self.attack_cooldown -= 1
                if not self.sleeping:
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
        if self.edef["ai"] == "wolf":
            ed = self.edef
            WOLF_DISTANCE = ed["standoff_dist"]
            WOLF_WINDUP_T = ed["windup_frames"]
            WOLF_DASH_T   = ed["dash_frames"]
            WOLF_REST_T   = ed["recovery_frames"]
            WOLF_SPEED    = DODGE_SPEED * ed["dash_speed_mult"]
            WOLF_DAMAGE   = ENEMY_MELEE_DAMAGE * ed["damage_mult"] * self.damage_mult

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
                    self.wolf_state      = "recovery"
                    self.wolf_timer      = WOLF_REST_T
                    self.attack_cooldown = WOLF_REST_T
                    self.scale_x = 1.4; self.scale_y = 0.7

            elif self.wolf_state == "recovery":
                self.wolf_glow = 0.0
                if dist < WOLF_DISTANCE:
                    self._move(-self.fx * self.speed, -self.fy * self.speed, is_blocked)
                if self.wolf_timer == 0:
                    self.wolf_state = "afstand"

        # ── Melee AI ──────────────────────────────────────────────────────────
        elif self.edef["ai"] == "melee":
            ed = self.edef
            if dist > self.radius + 10:
                self.scale_x = lerp(self.scale_x, 1.2, 0.1)
                self.scale_y = lerp(self.scale_y, 0.85, 0.1)
                self._move(self.fx * self.speed, self.fy * self.speed, is_blocked)
            if dist < ed["reach"] and self.attack_cooldown <= 0:
                self.anim_timer      = ed["anim_frames"]
                self.attack_cooldown = ed["attack_cooldown"]
                self.windup_timer    = ed["windup_frames"]
                self.windup_dx = -self.fx * 1.5
                self.windup_dy = -self.fy * 1.5
                self.scale_x = 0.7; self.scale_y = 1.4
                if player_flinch_cd <= 0:
                    attack = ("melee", self.x, self.y, melee_dmg)

        # ── Ranged AI ─────────────────────────────────────────────────────────
        elif self.edef["ai"] == "ranged":
            ed = self.edef
            FLEE_DIST      = ed["flee_dist"]
            TARGET_DIST    = ed["target_dist"]
            AIM_FRAMES     = ed["aim_frames"]
            SALVO_SIZE     = ed["salvo_size"]
            SALVO_INTERVAL = ed["salvo_interval"]

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
        if self.sleeping:
            # Sleeping wolves stay still and flat
            self.scale_x = lerp(self.scale_x, 1.4, 0.05)
            self.scale_y = lerp(self.scale_y, 0.6, 0.05)
            return
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

    def apply_separation(self, all_enemies):
        """Push away from nearby enemies so they don't stack."""
        if not self.aggro or self.flinch_timer > 0:
            return
        SEP_RADIUS = 48
        SEP_FORCE  = 0.5
        sx = sy = 0.0
        for other in all_enemies:
            if other is self:
                continue
            dx = self.x - other.x
            dy = self.y - other.y
            d  = math.hypot(dx, dy)
            if 0 < d < SEP_RADIUS:
                strength = (SEP_RADIUS - d) / SEP_RADIUS
                sx += (dx / d) * strength
                sy += (dy / d) * strength
        if sx or sy:
            self.x += sx * SEP_FORCE
            self.y += sy * SEP_FORCE

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

        if self.sleeping:
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
            aim_t = self.aim_timer
            if aim_t > 0:
                AIM_FRAMES = self.edef.get("aim_frames", 35)
                charge   = 1.0 - aim_t / AIM_FRAMES
                puls     = abs(math.sin(aim_t * 0.25))
                aim_kl   = (255, int(80 - charge * 60), int(80 - charge * 60))
                aim_len  = int(80 + charge * 80)
                aim_rad  = math.atan2(self.aim_dy, self.aim_dx)
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
    def __init__(self, x, y, damage_mult=1.0, boss_type="forest_warrior"):
        self.x = float(x); self.y = float(y)
        self.type        = "boss"
        self.boss_type   = boss_type
        self.bdef        = get_boss(boss_type)
        self.id          = Enemy.new_id()
        self.hp_max      = self.bdef["hp"] * damage_mult
        self.hp          = self.hp_max
        self.radius      = self.bdef["radius"]
        self.damage_mult = damage_mult
        self.exp_value   = int(self.bdef.get("exp", 150) * damage_mult)

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

        # Jump attack state
        self.jump_target_x = 0.0; self.jump_target_y = 0.0
        self.jump_origin_x = 0.0; self.jump_origin_y = 0.0
        self.jump_height   = 0.0   # visual height (0 = ground)
        self.jump_landed   = False

        self.glow           = 0.0

        self.aggro     = True
        self.group_id  = 0
        self.burning_timer = 0; self.burning_tick = 0

        # Cache attack data for quick access
        self._atk = self.bdef["attacks"]

    def take_damage(self, damage, from_x, from_y):
        if self.state == "jump_air":
            return False  # invulnerable while airborne
        self.hp -= damage
        # Boss is unstoppable — no flinch, no knockback, only visual feedback
        self.flinch_timer = 0
        self.flinch_dx    = 0.0
        self.flinch_dy    = 0.0
        self.scale_x = 1.15; self.scale_y = 0.88  # subtle squash (visual only)
        self.hit_stop = 3
        return self.hp <= 0

    def take_damage_swing(self, damage, kb_nx, kb_ny, hitstop=5, hit_squash=None):
        self.hit_stop = hitstop
        result = self.take_damage(damage, self.x - kb_nx * 50, self.y - kb_ny * 50)
        if hit_squash:
            self.scale_x = hit_squash[0]; self.scale_y = hit_squash[1]
        return result

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

        self.scale_x = lerp(self.scale_x, 1.0, 0.1)
        self.scale_y = lerp(self.scale_y, 1.0, 0.1)
        self.glow    = lerp(self.glow, 0.0, 0.05)

        bd     = self.bdef
        spd    = bd["speed"]
        attack = None

        if self.state == "volgen":
            if dist > self._atk["melee"]["reach"] + 15:
                self.scale_x = lerp(self.scale_x, 1.15, 0.08)
                self.scale_y = lerp(self.scale_y, 0.88, 0.08)
                self._move(self.fx * spd, self.fy * spd, is_blocked)
            if self.attack_cooldown <= 0:
                self._choose_attack(dist)

        elif self.state == "melee_windup":
            ma = self._atk["melee"]
            self._move(-self.fx * 0.6, -self.fy * 0.6, is_blocked)
            self.scale_x = lerp(self.scale_x, 0.7,  0.12)
            self.scale_y = lerp(self.scale_y, 1.45, 0.12)
            if self.state_timer == 0:
                self.state        = "melee_attack"
                self.state_timer  = ma["frames"]
                self.anim_timer   = ma["frames"]
                self.scale_x      = 1.6; self.scale_y = 0.5
                self.lunge_dx     = self.fx * 6.5
                self.lunge_dy     = self.fy * 6.5
                self.lunge_frames = 10
                if player_flinch_cd <= 0 and dist < ma["reach"] + 50:
                    attack = ("melee", self.x, self.y,
                              ma["damage"] * self.damage_mult)

        elif self.state == "melee_attack":
            ma = self._atk["melee"]
            if getattr(self, "lunge_frames", 0) > 0:
                self._move(self.lunge_dx, self.lunge_dy, is_blocked)
                self.lunge_dx    *= 0.75
                self.lunge_dy    *= 0.75
                self.lunge_frames -= 1
            if self.state_timer == 0:
                cd_mult = 1.0
                self.state       = "recovery"
                self.state_timer = ma["recovery"]
                self.attack_cooldown = int(ma["cooldown"] * cd_mult)

        elif self.state == "charge_windup":
            ca = self._atk["charge"]
            windup_total = self._charge_windup_frames()
            self._move(-self.fx * 0.5, -self.fy * 0.5, is_blocked)
            self.scale_x = lerp(self.scale_x, 0.6, 0.12)
            self.scale_y = lerp(self.scale_y, 1.6, 0.12)
            if self.state_timer == windup_total // 2:
                self.charge_dx         = self.fx * ca["speed"]
                self.charge_dy         = self.fy * ca["speed"]
                self.charge_hit_player = False
            if self.state_timer == 0:
                if self.charge_dx == 0 and self.charge_dy == 0:
                    self.charge_dx         = self.fx * ca["speed"]
                    self.charge_dy         = self.fy * ca["speed"]
                    self.charge_hit_player = False
                self.state       = "charge"
                self.state_timer = ca["duration"]
                self.scale_x = 1.7; self.scale_y = 0.45

        elif self.state == "charge":
            ca = self._atk["charge"]
            self._move(self.charge_dx, self.charge_dy, is_blocked)
            if (dist < self.radius + 30 and not self.charge_hit_player
                    and player_flinch_cd <= 0):
                self.charge_hit_player = True
                attack = ("charge", self.x, self.y,
                          ca["damage"] * self.damage_mult)
            if self.state_timer == 0:
                cd_mult = 1.0
                self.state       = "recovery"
                self.state_timer = ca["recovery"]
                self.attack_cooldown = int(ca["cooldown"] * cd_mult)

        elif self.state == "stamp_windup":
            sa = self._atk["stamp"]
            windup_t = sa["windup"]
            prog = 1.0 - self.state_timer / max(1, windup_t)
            # Boss raises up (stretches tall)
            self.scale_x = lerp(self.scale_x, 0.65, 0.12)
            self.scale_y = lerp(self.scale_y, 1.6,  0.12)
            # Store stamp warning progress for draw
            self._stamp_warn_prog = prog
            if self.state_timer == 0:
                self.state       = "stamp_active"
                self.state_timer = sa["active"]
                self.scale_x = 2.0; self.scale_y = 0.3
                self._stamp_warn_prog = 0.0
                self.shockwave_rings = [{"x": self.x, "y": self.y, "r": 0,
                                         "max_r": sa["max_radius"], "alpha": 220}]

        elif self.state == "stamp_active":
            sa = self._atk["stamp"]
            if self.state_timer == 0:
                self.state       = "recovery"
                self.state_timer = sa["recovery"]
                self.attack_cooldown = sa["cooldown"]

        elif self.state == "jump_windup":
            # Crouching before jump — squash down
            self.scale_x = lerp(self.scale_x, 1.4, 0.12)
            self.scale_y = lerp(self.scale_y, 0.5, 0.12)
            if self.state_timer == 0:
                ja = self._atk["jump"]
                self.state       = "jump_air"
                self.state_timer = ja["airtime"]
                self.scale_x = 0.6; self.scale_y = 1.5
                self.jump_landed = False

        elif self.state == "jump_air":
            # Boss is in the air — parabolic height curve
            ja       = self._atk["jump"]
            progress = 1.0 - self.state_timer / max(1, ja["airtime"])
            self.jump_height = math.sin(progress * math.pi) * 120  # peak at midpoint
            # Lerp position toward target
            t = progress
            self.x = lerp(self.jump_origin_x, self.jump_target_x, t)
            self.y = lerp(self.jump_origin_y, self.jump_target_y, t)
            if self.state_timer == 0:
                # Land!
                self.jump_height = 0.0
                self.jump_landed = True
                self.state       = "jump_land"
                self.state_timer = ja["stun_duration"]
                self.scale_x = 2.0; self.scale_y = 0.3
                attack = ("jump_land", self.x, self.y,
                          ja["land_damage"] * self.damage_mult)

        elif self.state == "jump_land":
            # Boss is stunned after landing — punish window
            ja = self._atk["jump"]
            self.jump_height = 0.0
            if self.state_timer == 0:
                cd_mult = 1.0
                self.state       = "recovery"
                self.state_timer = 20
                self.attack_cooldown = int(ja["cooldown"] * cd_mult)

        elif self.state == "recovery":
            if dist < 120:
                self._move(-self.fx * spd * 0.6, -self.fy * spd * 0.6, is_blocked)
            if self.state_timer == 0:
                self.state = "volgen"

        for ring in self.shockwave_rings:
            ring["r"]    += self._atk["stamp"]["ring_speed"]
            ring["alpha"] = max(0, int(ring["alpha"] * (1 - ring["r"] / ring["max_r"])))
        self.shockwave_rings = [rg for rg in self.shockwave_rings if rg["r"] < rg["max_r"]]

        if self.burning_timer > 0:
            self.burning_timer -= 1
            self.burning_tick  -= 1
            if self.burning_tick <= 0:
                self.burning_tick = 120
                self.hp = max(0, self.hp - 8)
                self.scale_x = 1.3; self.scale_y = 0.75

        return attack, False

    def _windup_mult(self):
        return 1.0

    def _choose_attack(self, dist):
        for rule in self.bdef["attack_priority"]:
            if rule.get("phase2_only", False):
                continue  # phase2 removed — skip phase2-only attacks
            if dist < rule.get("min_range", 0):
                continue
            if "max_range" in rule and dist > rule["max_range"]:
                continue
            if random.random() < rule["weight"]:
                getattr(self, f"_start_{rule['attack']}")()
                return
        self._start_melee()

    def _start_melee(self):
        self.state       = "melee_windup"
        self.state_timer = int(self._atk["melee"]["windup"] * self._windup_mult())

    def _start_charge(self):
        self.state       = "charge_windup"
        self.state_timer = self._charge_windup_frames()
        self.charge_dx   = 0.0; self.charge_dy = 0.0

    def _charge_windup_frames(self):
        return int(self._atk["charge"]["windup"] * self._windup_mult())

    def _start_stamp(self):
        self.state       = "stamp_windup"
        self.state_timer = self._atk["stamp"]["windup"]

    def _start_jump(self):
        ja = self._atk["jump"]
        self.state       = "jump_windup"
        self.state_timer = int(ja["windup"] * self._windup_mult())
        # Lock target at player's current position
        self.jump_target_x = self.x + self.fx * 200  # will be overridden in update_boss
        self.jump_target_y = self.y + self.fy * 200
        self.jump_origin_x = self.x
        self.jump_origin_y = self.y
        self.jump_height   = 0.0
        self.jump_landed   = False

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

        # ── Jump shadow at target ──────────────────────────────────
        if self.state in ("jump_windup", "jump_air"):
            ja  = self._atk["jump"]
            tsx = int(self.jump_target_x - cam_x)
            tsy = int(self.jump_target_y - cam_y)
            if self.state == "jump_windup":
                # Small pulsing indicator during windup
                prog = 1.0 - self.state_timer / max(1, int(ja["windup"] * self._windup_mult()))
                sr   = int(ja["land_radius"] * 0.3 * prog)
                alpha = int(60 + prog * 80)
            else:
                # Growing shadow during airtime
                prog  = 1.0 - self.state_timer / max(1, ja["airtime"])
                sr    = int(ja["land_radius"] * (0.3 + 0.7 * prog))
                alpha = int(80 + prog * 140)
            if sr > 2:
                ss = pygame.Surface((sr * 2 + 4, sr * 2 + 4), pygame.SRCALPHA)
                pygame.draw.ellipse(ss, (200, 50, 30, alpha),
                                    (2, sr // 2 + 2, sr * 2, sr))
                # Danger ring
                pygame.draw.ellipse(ss, (255, 80, 40, min(255, alpha + 40)),
                                    (2, sr // 2 + 2, sr * 2, sr), 3)
                surface.blit(ss, (tsx - sr - 2, tsy - sr // 2 - 2))

        # ── Stunned stars during jump_land ─────────────────────────
        if self.state == "jump_land":
            ja = self._atk["jump"]
            stun_prog = self.state_timer / max(1, ja["stun_duration"])
            for i in range(3):
                angle = pygame.time.get_ticks() * 0.005 + i * (math.pi * 2 / 3)
                star_x = int(sx + math.cos(angle) * (r + 10))
                star_y = int(sy - rh_s - 8 + math.sin(angle * 1.5) * 6)
                star_a = int(200 * stun_prog)
                if star_a > 10:
                    pygame.draw.circle(surface, (255, 255, 100), (star_x, star_y), 4)
                    pygame.draw.circle(surface, (255, 200, 50), (star_x, star_y), 2)

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
            windup_total = self._charge_windup_frames()
            prog     = 1.0 - self.state_timer / max(1, windup_total)
            line_len = int(180 * prog + 40)
            alpha    = int(60 + prog * 195)
            ex    = int(sx + self.fx * line_len)
            ey    = int(sy + self.fy * line_len)
            cs    = pygame.Surface((surface.get_width(), surface.get_height()),
                                   pygame.SRCALPHA)
            # Wide danger zone stripe
            perp_x = -self.fy; perp_y = self.fx
            stripe_w = int(18 + prog * 14)  # grows wider
            pts = [
                (int(sx + perp_x * stripe_w), int(sy + perp_y * stripe_w)),
                (int(sx - perp_x * stripe_w), int(sy - perp_y * stripe_w)),
                (int(ex - perp_x * stripe_w), int(ey - perp_y * stripe_w)),
                (int(ex + perp_x * stripe_w), int(ey + perp_y * stripe_w)),
            ]
            pygame.draw.polygon(cs, (255, 40, 10, int(alpha * 0.3)), pts)
            # Center line
            pygame.draw.line(cs, (255, 60, 20, alpha), (sx, sy), (ex, ey), 5)
            # Arrow tip
            ap = -self.fy * 10; bp = self.fx * 10
            tip = (ex, ey)
            left  = (int(ex - self.fx * 22 + ap), int(ey - self.fy * 22 + bp))
            right = (int(ex - self.fx * 22 - ap), int(ey - self.fy * 22 - bp))
            pygame.draw.polygon(cs, (255, 80, 20, alpha), [tip, left, right])
            surface.blit(cs, (0, 0))

        if self.state == "stamp_windup":
            sa   = self._atk["stamp"]
            prog = getattr(self, '_stamp_warn_prog', 0.0)
            # Growing warning circle on ground
            warn_r = int(sa["max_radius"] * prog)
            if warn_r > 4:
                alpha_w = int(40 + prog * 100)
                ws = pygame.Surface((warn_r * 2 + 4, warn_r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(ws, (255, 180, 30, alpha_w),
                                   (warn_r + 2, warn_r + 2), warn_r)
                pygame.draw.circle(ws, (255, 80, 20, min(255, alpha_w + 60)),
                                   (warn_r + 2, warn_r + 2), warn_r, 3)
                surface.blit(ws, (sx - warn_r - 2, sy - warn_r - 2))

        # Apply jump height offset for airborne boss
        body_sy = sy - int(self.jump_height)

        if self.glow > 0.05:
            glow_r = int(r * 1.8 + self.glow * 20)
            ga     = int(self.glow * 140)
            gs     = pygame.Surface((glow_r * 2 + 4, glow_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(gs, (200, 40, 20, ga), (glow_r + 2, glow_r + 2), glow_r)
            surface.blit(gs, (sx - glow_r - 2, body_sy - glow_r - 2))

        # Shadow stays on ground, body goes up
        shadow_scale = max(0.3, 1.0 - self.jump_height / 150.0)
        shadow_rw = int(rw * shadow_scale)
        pygame.draw.ellipse(surface, C_SHADOW,
                            (sx - shadow_rw + 4, sy + rh_s - 4, shadow_rw * 2, rh_s))

        kl = self.bdef["color_p1"]
        if self.flinch_timer > 0 and (self.flinch_timer // 4) % 2 == 0:
            kl = (220, 220, 220)
        # Bear body — slightly wider than tall for bulk
        pygame.draw.ellipse(surface, kl, (sx - rw, body_sy - rh_s, rw * 2, rh_s * 2))
        pygame.draw.ellipse(surface, (200, 180, 150),
                            (sx - rw, body_sy - rh_s, rw * 2, rh_s * 2), 3)
        # Bear ears
        ear_kl  = kl
        ear_off = int(rw * 0.65)
        for ex_off in (-ear_off, ear_off):
            pygame.draw.circle(surface, ear_kl,  (sx + ex_off, body_sy - rh_s + 2), 7)
            pygame.draw.circle(surface, (60, 30, 10), (sx + ex_off, body_sy - rh_s + 2), 4)

        if self.burning_timer > 0:
            puls = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.015)
            br   = int(r * 1.4 + puls * 8)
            ba   = int(120 + puls * 80)
            bs   = pygame.Surface((br * 2 + 4, br * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(bs, (255, int(80 + puls * 60), 0, ba), (br + 2, br + 2), br)
            surface.blit(bs, (sx - br - 2, body_sy - br - 2))

        # Don't draw eye/sword while airborne (boss is a blur in the sky)
        if self.state != "jump_air":
            pygame.draw.circle(surface, self.bdef["color_eye"],
                (int(sx + self.fx * int(r * 0.55)),
                 int(body_sy + self.fy * int(r * 0.55))), 7)

            fh = math.degrees(math.atan2(self.fy, self.fx))
            if self.state == "melee_windup":
                # Paw pulled back — windup tell with red glow
                ma = self._atk["melee"]
                windup_t = int(ma["windup"] * self._windup_mult())
                prog = 1.0 - self.state_timer / max(1, windup_t)
                # Paw retracts behind body
                zh  = fh + 180 - prog * 40
                rad = math.radians(zh)
                plen = int(28 + prog * 12)
                px = int(sx + math.cos(rad) * plen)
                py = int(body_sy + math.sin(rad) * plen)
                pygame.draw.circle(surface, kl, (px, py), 9)
                pygame.draw.circle(surface, (60, 30, 10), (px, py), 9, 2)
                # Claw tips
                for ci in range(3):
                    ca  = math.radians(zh - 25 + ci * 25)
                    clx = int(px + math.cos(ca) * 10)
                    cly = int(py + math.sin(ca) * 10)
                    pygame.draw.circle(surface, (200, 180, 150), (clx, cly), 3)
                # Red warning glow
                gw_r = int(18 + prog * 22)
                gw_a = int(40 + prog * 120)
                gws  = pygame.Surface((gw_r * 2 + 4, gw_r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(gws, (255, 50, 20, gw_a),
                                   (gw_r + 2, gw_r + 2), gw_r)
                surface.blit(gws, (sx - gw_r - 2, body_sy - gw_r - 2))
            elif self.state == "melee_attack" and self.anim_timer > 0:
                # Wide claw swipe with arc trail
                ma    = self._atk["melee"]
                t_raw = 1.0 - self.anim_timer / ma["frames"]
                prog  = ease_in_out(t_raw)
                zh    = fh - 80 + prog * 160
                rad   = math.radians(zh)
                plen  = 75
                px    = int(sx + math.cos(rad) * plen)
                py    = int(body_sy + math.sin(rad) * plen)
                # Swoosh trail
                trail_steps = 5
                for ti in range(trail_steps):
                    tp   = max(0.0, prog - (ti + 1) * 0.07)
                    tzh  = fh - 80 + tp * 160
                    trad = math.radians(tzh)
                    ta   = int(130 - ti * 26)
                    tlen = plen - ti * 5
                    if ta > 0:
                        ttx = int(sx + math.cos(trad) * tlen)
                        tty = int(body_sy + math.sin(trad) * tlen)
                        ts  = pygame.Surface((surface.get_width(), surface.get_height()),
                                             pygame.SRCALPHA)
                        pygame.draw.line(ts, (200, 150, 80, ta),
                                         (sx, body_sy), (ttx, tty), max(2, 7 - ti))
                        surface.blit(ts, (0, 0))
                # Paw at tip of swipe
                pygame.draw.circle(surface, kl, (px, py), 9)
                for ci in range(3):
                    ca  = math.radians(zh - 25 + ci * 25)
                    clx = int(px + math.cos(ca) * 11)
                    cly = int(py + math.sin(ca) * 11)
                    pygame.draw.circle(surface, (220, 200, 170), (clx, cly), 3)
            else:
                # Idle paw resting forward
                rh2 = math.radians(fh + 25)
                px  = int(sx + math.cos(rh2) * 32)
                py  = int(body_sy + math.sin(rh2) * 32)
                pygame.draw.circle(surface, kl, (px, py), 8)
                pygame.draw.circle(surface, (60, 30, 10), (px, py), 8, 2)

        bw    = r * 4
        ratio = max(0, self.hp / self.hp_max)
        pygame.draw.rect(surface, (80, 20, 20),  (sx - bw//2, body_sy - r - 14, bw, 8))
        kl_hp = (220, 60, 60)
        pygame.draw.rect(surface, kl_hp, (sx - bw//2, body_sy - r - 14, int(bw * ratio), 8))
        pygame.draw.rect(surface, (200, 180, 150), (sx - bw//2, body_sy - r - 14, bw, 8), 1)


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