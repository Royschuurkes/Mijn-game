# entiteiten.py - Speler, Vijand, Pijl klassen
import math, random
import pygame
from opslaan import *

def normalize(x, y):
    l = math.hypot(x, y)
    return (x/l, y/l) if l else (0.0, 0.0)

def hoek_diff(a, b):
    d = (b-a) % 360
    if d > 180: d -= 360
    return d

def ease_out(t):
    """Snel begin, langzaam eind."""
    return 1 - (1-t)**2

def ease_in_out(t):
    """Langzaam begin en eind, snel midden — voor zwaai."""
    return t * t * (3 - 2*t)

def lerp(a, b, t):
    return a + (b - a) * t


class Speler:
    def __init__(self, x, y, save):
        self.x = float(x); self.y = float(y)
        self.fx, self.fy = 0.0, -1.0
        self.save = save
        self.hp   = max_hp(save)
        self.mhp  = max_hp(save)
        self.sta  = max_sta(save)
        self.msta = max_sta(save)
        self.dodge_t = self.dodge_cd = 0
        self.dodge_vx = self.dodge_vy = 0.0  # richting van de dodge
        self.zw_t = self.zw_cd = 0
        self.flinch_t = self.flinch_cd = 0
        self.flinch_vx = self.flinch_vy = 0.0
        self.sta_delay = 0
        self.geraakt = set()
        self.special_t       = 0
        self.special_cd      = 0
        self.special_actief  = None
        self.special_geraakt = set()
        self.dash_vx = self.dash_vy = 0.0
        # Combo systeem
        self.combo_stap    = 0
        self.combo_t       = 0
        self.combo_window  = 0
        self.combo_reset_t = 0
        self.combo_gebufferd = False
        self.dash_strike_window = 0
        self.is_dash_strike     = False
        self.finisher_windup    = 0
        self.swing_cd           = 0  # minimale tijd tussen swings
        self.post_combo_cd      = 0  # recovery na de finisher steek
        # Facing lock tijdens combo
        self.lock_fx = 0.0
        self.lock_fy = 1.0
        self.facing_locked = False
        # Guard break
        self.guard_break_t  = 0   # frames stun
        self.schild_geblokt = False  # schild tijdelijk uit
        # Squash & stretch
        self.schaal_x = 1.0
        self.schaal_y = 1.0
        # Bewegingsrichting voor stretch
        self.beweeg_x = 0.0
        self.beweeg_y = 0.0
        self.tik = 0

    @property
    def levend(self): return self.hp > 0
    @property
    def kan_aanvallen(self): return self.flinch_t == 0

    def _wapen(self):
        from wapens import get_wapen
        return get_wapen(self.save.get("wapen", "simpel_zwaard"))

    def _heeft_schild(self):
        return self._wapen().get("type") == "schild"

    def heeft_item(self, key):
        return key in self.save.get("items", [])

    def heeft_actief_effect(self, key):
        return self.save.get("actieve_effecten", {}).get(key, 0) > 0

    def _start_special(self, w):
        special = w.get("special")
        if special == "brede_sweep":
            self.special_t = w.get("sweep_frames", 35)
        elif special == "stoot":
            self.special_t = w.get("stoot_frames", 10)
            self.dash_vx = self.fx * w.get("stoot_afstand", 120) / max(1, self.special_t)
            self.dash_vy = self.fy * w.get("stoot_afstand", 120) / max(1, self.special_t)
        elif special == "grondstamp":
            self.special_t = w.get("stamp_frames", 20)
        elif special == "dash_aanval":
            self.special_t = w.get("dash_frames", 8)
            self.dash_vx = self.fx * w.get("dash_afstand", 160) / max(1, self.special_t)
            self.dash_vy = self.fy * w.get("dash_afstand", 160) / max(1, self.special_t)
        self.special_cd = self.special_t + 30

    def _probeer_aanval(self, blok=False):
        """Probeer een swing te starten. Gedeeld door klik en hold."""
        if blok: return
        SWING_CD = 18

        kan = (self.combo_t == 0 and self.finisher_windup == 0
               and self.swing_cd == 0 and self.post_combo_cd == 0
               and self.sta >= STAMINA_ZWAARD and self.kan_aanvallen
               and self.dodge_t == 0)
        if self.combo_window > 0 and self.combo_stap in (1, 2) and self.combo_t == 0 and self.swing_cd == 0 and self.post_combo_cd == 0:
            kan = True

        if not kan:
            # Te vroeg geklikt terwijl swing nog bezig: kleine penalty
            if self.combo_t > 0 and self.combo_stap in (1, 2):
                self.swing_cd = min(self.swing_cd + 8, SWING_CD + 8)
            return

        if self.dash_strike_window > 0:
            self.combo_stap         = 3
            self.combo_t            = 7
            self.combo_window       = 0
            self.combo_reset_t      = 0
            self.dash_strike_window = 0
            self.is_dash_strike     = True
            self.finisher_windup    = 0
        elif (self.combo_stap % 3) + 1 == 3:
            self.combo_stap      = 2
            self.combo_t         = 0
            self.combo_window    = 0
            self.finisher_windup = 10
            self.is_dash_strike  = False
            self.facing_locked   = True
            self.lock_fx = self.fx; self.lock_fy = self.fy
        else:
            self.combo_stap     = (self.combo_stap % 3) + 1
            self.combo_t        = 10
            self.combo_window   = 28
            self.combo_reset_t  = 0
            self.is_dash_strike = False
        self.sta         -= STAMINA_ZWAARD
        self.sta_delay    = STAMINA_DELAY
        self.swing_cd     = SWING_CD
        self.geraakt      = set()
        self._combo_idle_t = 0
        if not self.finisher_windup:
            self.lock_fx = self.fx; self.lock_fy = self.fy
            self.facing_locked = True

    def verwerk_events(self, events, blok=False):
        w = self._wapen()
        COMBO_TIMEOUT = 70  # ~1.2 sec zonder swing = combo reset

        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                # Dodge cancel: mag uit combo stappen als swing al >3 frames bezig
                combo_elapsed = 10 - self.combo_t
                dodge_mag = (self.dodge_t<=0 and self.dodge_cd<=0
                             and self.sta>=STAMINA_DODGE and self.dodge_t == 0)
                in_swing = self.combo_t > 0 and combo_elapsed >= 3
                if dodge_mag and (not self.combo_t > 0 or in_swing) and self.combo_reset_t == 0:
                    bx, by = self.beweeg_x, self.beweeg_y
                    if math.hypot(bx, by) < 0.1:
                        bx, by = self.fx, self.fy
                    self.dodge_vx  = bx * DODGE_SPEED
                    self.dodge_vy  = by * DODGE_SPEED
                    self.dodge_t   = DODGE_FRAMES
                    self.dodge_cd  = DODGE_CD
                    self.sta      -= STAMINA_DODGE
                    self.sta_delay = STAMINA_DELAY
                    self.schaal_x  = 1.4; self.schaal_y = 0.7
                    self.dash_strike_window = DODGE_FRAMES + 8  # window blijft open tijdens + kort na dodge
                    # Combo reset bij dodge cancel
                    self.combo_t         = 0
                    self.combo_stap      = 0
                    self.combo_window    = 0
                    self.combo_reset_t   = 0
                    self.combo_gebufferd = False
                    self.facing_locked   = False
                    self.finisher_windup = 0
                    self.swing_cd        = 0
                    self.post_combo_cd   = 0

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self._probeer_aanval(blok)

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
                special = w.get("special")
                if special and special != "blok":
                    if self.special_t<=0 and self.special_cd<=0:
                        kosten = w.get("special_stamina", 0)
                        if self.sta >= kosten and self.kan_aanvallen:
                            self.sta -= kosten
                            self.sta_delay = STAMINA_DELAY
                            self.special_actief = special
                            self.special_geraakt = set()
                            self._start_special(w)

        # Hold LMB: auto-swing als knop ingedrukt en swing_cd klaar
        if pygame.mouse.get_pressed()[0] and not blok:
            if self.combo_t == 0 and self.finisher_windup == 0 and self.swing_cd == 0:
                self._probeer_aanval(blok)

        # Combo timeout: te lang niet geslagen = combo reset
        if (self.combo_stap > 0 and self.combo_t == 0
                and self.finisher_windup == 0 and self.combo_window == 0):
            self._combo_idle_t = getattr(self, '_combo_idle_t', 0) + 1
            if self._combo_idle_t > COMBO_TIMEOUT:
                self.combo_stap    = 0
                self._combo_idle_t = 0
        else:
            self._combo_idle_t = 0

    def update(self, keys, muis_pos, cam_x, cam_y, blok_check, tile_op, blok):
        self.tik += 1
        dmx = muis_pos[0]+cam_x - self.x
        dmy = muis_pos[1]+cam_y - self.y
        if math.hypot(dmx, dmy) > 5:
            if not self.facing_locked:
                self.fx, self.fy = normalize(dmx, dmy)
            else:
                self.fx, self.fy = self.lock_fx, self.lock_fy

        mx, my = 0.0, 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    my -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  my += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  mx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: mx += 1
        mx, my = normalize(mx, my)
        self.beweeg_x = mx; self.beweeg_y = my

        huidig = tile_op(int(self.x//TILE), int(self.y//TILE))
        sprint = keys[pygame.K_LSHIFT] and math.hypot(mx, my) > 0.1 and self.dodge_t == 0 and self.sta > 0

        # Hoeveel frames zijn al gespeeld in de huidige swing
        combo_elapsed = 10 - self.combo_t  # 0 = net gestart

        if self.dodge_t > 0 or (self.special_t > 0 and self.special_actief in ("stoot","dash_aanval")):
            speed = DODGE_SPEED + extra_dodge(self.save)
        elif self.finisher_windup > 0:
            speed = 0.0                          # helemaal stil tijdens windup
        elif self.combo_t > 0:
            if combo_elapsed < 2:
                speed = 0.0                      # root: eerste 2 frames helemaal stil
            elif self.combo_stap == 3:
                speed = 0.0                      # steek: geen eigen beweging, lunge doet het
            else:
                speed = PLAYER_SPEED * 0.25      # zwaaien: 25% speed
        elif self.combo_reset_t > 0:
            speed = PLAYER_SPEED * 0.5           # recovery na steek: half
        elif blok:   speed = PLAYER_SPEED * 0.5
        elif sprint: speed = PLAYER_SPEED * SPRINT_SPEED
        else:        speed = PLAYER_SPEED

        if self.flinch_t > 0:
            dx, dy = self.flinch_vx, self.flinch_vy
            self.flinch_vx *= 0.8; self.flinch_vy *= 0.8
        elif self.special_t > 0 and self.special_actief in ("stoot","dash_aanval"):
            dx, dy = self.dash_vx, self.dash_vy
        elif self.dodge_t > 0:
            dx, dy = self.dodge_vx, self.dodge_vy
        elif self.combo_t > 0 and self.combo_stap == 3:
            # Lunge: push in kijkrichting, alleen in eerste helft van de steek
            lunge_kracht = PLAYER_SPEED * 1.8 * max(0, (6 - combo_elapsed) / 6)
            dx, dy = self.fx * lunge_kracht, self.fy * lunge_kracht
        else:
            dx, dy = mx*speed, my*speed

        # Sprint stamina kosten (niet als marathon_runner item actief)
        if sprint and not self.heeft_item("marathon_runner"):
            self.sta = max(0, self.sta - SPRINT_STAMINA)
            self.sta_delay = 8

        r = 13
        nx = self.x + dx
        if not any(blok_check(int((nx+ox)//TILE), int((self.y+oy)//TILE))
                   for ox in (-r,r) for oy in (-r,r)):
            self.x = nx
        ny = self.y + dy
        if not any(blok_check(int((self.x+ox)//TILE), int((ny+oy)//TILE))
                   for ox in (-r,r) for oy in (-r,r)):
            self.y = ny

        for attr in ("dodge_t","dodge_cd","zw_t","zw_cd","flinch_t","flinch_cd","special_t","special_cd"):
            if getattr(self, attr) > 0:
                setattr(self, attr, getattr(self, attr)-1)
        if self.special_t == 0:
            self.special_actief = None

        # Squash & stretch richting neutraal
        self.schaal_x = lerp(self.schaal_x, 1.0, 0.18)
        self.schaal_y = lerp(self.schaal_y, 1.0, 0.18)

        # Stretch in bewegingsrichting
        beweegt = math.hypot(mx, my) > 0.1
        if beweegt and self.dodge_t == 0 and self.flinch_t == 0:
            self.schaal_x = lerp(self.schaal_x, 1.15, 0.12)
            self.schaal_y = lerp(self.schaal_y, 0.88, 0.12)

        # Platdrukken bij flinch
        if self.flinch_t > 0 and self.flinch_t == FLINCH_SPELER:
            self.schaal_x = 0.6; self.schaal_y = 1.5

        # Guard break timer
        if self.guard_break_t > 0:
            self.guard_break_t -= 1
            if self.guard_break_t == 0:
                self.schild_geblokt = False

        if self.sta_delay > 0 or blok:
            if not blok: self.sta_delay -= 1
        elif self.sta < self.msta:
            self.sta = min(self.msta, self.sta + (self.msta * STAMINA_REGEN_PCT / FPS))

        # Actieve effecten aftellen
        for eff in self.save.get("actieve_effecten", {}):
            if self.save["actieve_effecten"][eff] > 0:
                self.save["actieve_effecten"][eff] -= 1

        # Finisher windup aftellen
        if self.finisher_windup > 0:
            self.finisher_windup -= 1
            if self.finisher_windup == 0:
                # Windup klaar: steek nu
                self.combo_stap     = 3
                self.combo_t        = 10
                self.combo_window   = 28
                self.is_dash_strike = False
                self.geraakt        = set()
                self.schaal_x = 0.6; self.schaal_y = 1.5  # anticipatie squeeze

        elif self.combo_t > 0:\
            pass  # combo al actief

        # Dash-strike window aftellen
        if self.dash_strike_window > 0: self.dash_strike_window -= 1

        # I-frames op swing start (eerste 3 frames van elke swing)
        combo_elapsed = 10 - self.combo_t
        if self.combo_t > 0 and combo_elapsed < 3:
            self.flinch_cd = max(self.flinch_cd, 3)

        # Combo timers
        if self.combo_t      > 0: self.combo_t      -= 1
        if self.combo_window > 0: self.combo_window -= 1
        if self.swing_cd     > 0: self.swing_cd     -= 1
        if self.post_combo_cd > 0:
            self.post_combo_cd -= 1
            if self.post_combo_cd == 0:
                self.combo_stap = 0  # reset combo na recovery
        if self.combo_reset_t > 0:
            self.combo_reset_t -= 1
            if self.combo_reset_t == 0:
                self.combo_stap = 0
                self.facing_locked = False

        # Post-finisher recovery: combo_t net op 0 gegaan na steek
        if self.combo_t == 0 and self.combo_stap == 3 and not getattr(self, '_post_combo_triggered', False):
            self._post_combo_triggered = True
            self.post_combo_cd = 22  # frames zwaard terughaaltijd
            self.swing_cd = 22
        elif self.combo_t > 0 or self.combo_stap != 3:
            self._post_combo_triggered = False

        # Facing unlock als combo klaar is
        if self.combo_t == 0 and self.combo_window == 0:
            self.facing_locked = False

        # Buffer: als er een klik gebufferd is en de swing is klaar, fire direct
        if getattr(self, 'combo_gebufferd', False) and self.combo_t == 0:
            self.combo_gebufferd = False
            if self.sta >= STAMINA_ZWAARD and self.kan_aanvallen and self.dodge_t == 0:
                self.combo_stap     = (self.combo_stap % 3) + 1
                self.combo_t        = 10
                self.combo_window   = 28
                self.combo_reset_t  = 0
                self.is_dash_strike = False
                self.sta           -= STAMINA_ZWAARD
                self.sta_delay      = STAMINA_DELAY
                self.geraakt        = set()
                self.lock_fx        = self.fx
                self.lock_fy        = self.fy
                self.facing_locked  = True

        return False  # struiken verwijderd

    def krijg_schade(self, schade, van_x, van_y):
        if self.dodge_t > 0 or self.flinch_cd > 0: return False
        if self.heeft_actief_effect("invis"): return False   # onkwetsbaar
        self.hp = max(0, self.hp - schade)
        knx, kny = normalize(self.x-van_x, self.y-van_y)
        self.flinch_t = FLINCH_SPELER
        self.flinch_cd = FLINCH_CD_SPELER
        self.flinch_vx = knx * KNOCKBACK
        self.flinch_vy = kny * KNOCKBACK
        return True

    def verwerk_blok(self, van_x, van_y, stamina_kosten=None):
        """Geblokte hit: kost stamina, guard break als stamina te laag."""
        if stamina_kosten is None:
            stamina_kosten = STAMINA_SCHILD
        if self.schild_geblokt:
            return False
        if self.sta >= stamina_kosten:
            self.sta -= stamina_kosten
            self.sta_delay = STAMINA_DELAY
            # Kleine knockback — je voelt dat je schild geraakt wordt
            knx, kny = normalize(self.x-van_x, self.y-van_y)
            self.flinch_vx = knx * 3.5
            self.flinch_vy = kny * 3.5
            self.flinch_t  = 6
            self.schaal_x  = 0.85; self.schaal_y = 1.2
            return True  # succesvol geblokt
        else:
            # Guard break
            self.sta = 0
            self.guard_break_t  = GUARD_BREAK_T
            self.schild_geblokt = True
            knx, kny = normalize(self.x-van_x, self.y-van_y)
            self.flinch_t  = GUARD_BREAK_T // 2
            self.flinch_vx = knx * KNOCKBACK * 1.8
            self.flinch_vy = kny * KNOCKBACK * 1.8
            self.schaal_x  = 1.8; self.schaal_y = 0.4
            self.flinch_cd = 0
            return False  # blok mislukt

    def zwaard_hits(self, vijanden):
        hits = []
        if self.combo_t <= 0: return hits
        fh = math.degrees(math.atan2(self.fy, self.fx))
        stap = self.combo_stap
        prog = ease_in_out(1.0 - self.combo_t / 10)

        base_schade = SPELER_SCHADE + extra_schade(self.save)

        # Item: fire_damage of fire_potion actief → +25% schade
        heeft_vuur = self.heeft_item("fire_damage") or self.heeft_actief_effect("fire_potion")
        if heeft_vuur:
            base_schade *= 1.25

        # Item: berserker → schade schaal met gemiste HP
        if self.heeft_item("berserker"):
            hp_ratio = max(0.0, 1.0 - self.hp / self.mhp)
            base_schade *= (1.0 + hp_ratio * 0.8)

        if stap == 1:   # Links naar rechts sweep
            bereik = ZWAARD_BEREIK
            zh = fh - 60 + prog * 120
            hoek_tolerantie = 42
            schade = base_schade
        elif stap == 2: # Rechts naar links sweep
            bereik = ZWAARD_BEREIK
            zh = fh + 60 - prog * 120
            hoek_tolerantie = 42
            schade = base_schade
        else:           # Steek / dash-strike
            bereik = ZWAARD_BEREIK * (1.5 if getattr(self,'is_dash_strike',False) else 1.3)
            zh = fh
            hoek_tolerantie = 28
            finisher_mult = 2.5 * (1.5 if self.heeft_item("combo_master") else 1.0)
            schade = base_schade * (1.8 if getattr(self,'is_dash_strike',False) else finisher_mult)

        for v in vijanden:
            if v.id in self.geraakt: continue
            dvx = v.x-self.x; dvy = v.y-self.y
            if math.hypot(dvx, dvy) < bereik:
                vh = math.degrees(math.atan2(dvy, dvx))
                if abs(hoek_diff(zh, vh)) < hoek_tolerantie:
                    self.geraakt.add(v.id)
                    # Knockback in richting van de swing (niet van de speler)
                    kb_rad = math.radians(zh)
                    kb_nx = math.cos(kb_rad)
                    kb_ny = math.sin(kb_rad)
                    hits.append((v, schade, kb_nx, kb_ny))
        return hits

    def special_hits(self, vijanden):
        hits = []
        if self.special_t <= 0 or not self.special_actief: return hits
        w = self._wapen()
        special = self.special_actief
        schade_bonus = extra_schade(self.save)

        if special == "brede_sweep":
            bereik = w.get("sweep_bereik", 72)
            hoek_w = w.get("sweep_hoek", 200)
            frames = w.get("sweep_frames", 35)
            t_raw = 1.0 - self.special_t / frames
            prog = ease_in_out(t_raw)
            fh = math.degrees(math.atan2(self.fy, self.fx))
            zh = fh - hoek_w/2 + prog*hoek_w
            schade = w.get("sweep_schade", 30) + schade_bonus
            for v in vijanden:
                if v.id in self.special_geraakt: continue
                dvx = v.x-self.x; dvy = v.y-self.y
                if math.hypot(dvx, dvy) < bereik:
                    vh = math.degrees(math.atan2(dvy, dvx))
                    if abs(hoek_diff(zh, vh)) < hoek_w/2:
                        self.special_geraakt.add(v.id)
                        hits.append((v, schade, KNOCKBACK*1.5))

        elif special == "stoot":
            schade = w.get("stoot_schade", 35) + schade_bonus
            kb = w.get("stoot_knockback", 10.0)
            for v in vijanden:
                if v.id in self.special_geraakt: continue
                if math.hypot(v.x-self.x, v.y-self.y) < 52:
                    self.special_geraakt.add(v.id)
                    hits.append((v, schade, kb))

        elif special == "grondstamp":
            if self.special_t == 1:
                schade = w.get("stamp_schade", 45) + schade_bonus
                kb = w.get("stamp_knockback", 14.0)
                radius = w.get("stamp_radius", 110)
                for v in vijanden:
                    if v.id in self.special_geraakt: continue
                    if math.hypot(v.x-self.x, v.y-self.y) < radius:
                        self.special_geraakt.add(v.id)
                        hits.append((v, schade, kb))

        elif special == "dash_aanval":
            schade = w.get("dash_schade", 50) + schade_bonus
            kb = w.get("dash_knockback", 8.0)
            for v in vijanden:
                if v.id in self.special_geraakt: continue
                if math.hypot(v.x-self.x, v.y-self.y) < 48:
                    self.special_geraakt.add(v.id)
                    hits.append((v, schade, kb))

        return hits

    def teken(self, surface, cam_x, cam_y, blok):
        w  = self._wapen()
        sx = int(self.x-cam_x); sy = int(self.y-cam_y); r = 15

        # Squash & stretch tekenen
        rw = max(6, int(r * self.schaal_x))
        rh_s = max(6, int(r * self.schaal_y))

        knip = self.flinch_t>0 and (self.flinch_t//4)%2==0
        guard_knip = self.guard_break_t > 0 and (self.guard_break_t//3)%2==0
        pygame.draw.ellipse(surface, C_SCH, (sx-rw+4, sy+rh_s-4, rw*2, rh_s))
        if guard_knip:
            kl = (255, 200, 50)   # oranje knipperen bij guard break
        else:
            kl = (220,60,60) if knip else (C_SP_DOD if self.dodge_t>0 else C_SP)
        pygame.draw.ellipse(surface, kl, (sx-rw, sy-rh_s, rw*2, rh_s*2))
        pygame.draw.circle(surface, C_OOG, (int(sx+self.fx*9), int(sy+self.fy*9)), 5)

        # Finisher windup glow — oplaadring rond speler
        fw = getattr(self, 'finisher_windup', 0)
        if fw > 0:
            charge = 1.0 - fw / 10
            glow_r = int(18 + charge * 14)
            glow_alpha = int(charge * 220)
            puls = abs(math.sin(fw * 0.6))
            glow_surf = pygame.Surface((glow_r*2+4, glow_r*2+4), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (255, int(180+puls*75), 50, glow_alpha),
                               (glow_r+2, glow_r+2), glow_r, max(2, int(charge*6)))
            surface.blit(glow_surf, (sx-glow_r-2, sy-glow_r-2))

        fh = math.degrees(math.atan2(self.fy, self.fx))
        wapen_kl = C_ZWAARD

        if self.combo_t > 0:
            prog = ease_in_out(1.0 - self.combo_t / 10)
            stap = self.combo_stap
            if stap == 1:
                zh_start = fh - 60
                zh_end   = fh + 60
                zh       = zh_start + prog * 120
                bereik_t = ZWAARD_BEREIK
            elif stap == 2:
                zh_start = fh + 60
                zh_end   = fh - 60
                zh       = zh_start - prog * 120
                bereik_t = ZWAARD_BEREIK
            else:
                zh_start = zh_end = zh = fh
                bereik_t = ZWAARD_BEREIK * (1.5 if getattr(self,'is_dash_strike',False) else 1.3)

            # Zwaard lijn
            rad = math.radians(zh)
            ex = sx + math.cos(rad)*bereik_t
            ey = sy + math.sin(rad)*bereik_t
            lijn_kl = (255,220,50) if getattr(self,'is_dash_strike',False) else wapen_kl
            pygame.draw.line(surface, lijn_kl, (sx,sy), (int(ex),int(ey)), 6 if self.is_dash_strike else 5)
            tip_kl = (255,255,100) if getattr(self,'is_dash_strike',False) else (240,240,255)
            pygame.draw.circle(surface, tip_kl, (int(ex),int(ey)), 7 if self.is_dash_strike else 5)

            # Swoosh arc — boog van beginhoek naar huidige hoek
            if stap != 3 and prog > 0.05:
                arc_hoek_start = zh_start
                arc_hoek_end   = zh
                n_punten = 14
                swoosh_punten = []
                for i in range(n_punten+1):
                    t = i / n_punten
                    ah = arc_hoek_start + (arc_hoek_end - arc_hoek_start) * t
                    dist_r = bereik_t * (0.45 + 0.55 * t)
                    ar = math.radians(ah)
                    swoosh_punten.append((
                        sx + math.cos(ar)*dist_r,
                        sy + math.sin(ar)*dist_r
                    ))
                # Teken als dikke lijn met fade
                for i in range(len(swoosh_punten)-1):
                    t = i / (len(swoosh_punten)-1)
                    alpha = int(180 * t * prog)
                    breedte = max(1, int(14 * t * prog))
                    kl_swoosh = (
                        int(200 + 55*t),
                        int(220 + 35*t),
                        255
                    )
                    seg_surf = pygame.Surface((breedte*2+4, breedte*2+4), pygame.SRCALPHA)
                    p1 = swoosh_punten[i]; p2 = swoosh_punten[i+1]
                    # Teken segment als cirkel op elk punt
                    pygame.draw.circle(seg_surf, (*kl_swoosh, alpha),
                                       (breedte+2, breedte+2), breedte)
                    surface.blit(seg_surf, (int(p1[0])-breedte-2, int(p1[1])-breedte-2))
            elif stap == 3:
                # Steek / dash-strike: lichtflits recht vooruit
                flits_kl = (255,220,50) if getattr(self,'is_dash_strike',False) else (255,255,200)
                for dist_l in range(0, int(bereik_t), 7):
                    alpha = int(200 * (1 - dist_l/bereik_t) * prog)
                    r_l = max(1, int((9 if self.is_dash_strike else 7) * (1 - dist_l/bereik_t) * prog))
                    px2 = sx + math.cos(rad)*dist_l
                    py2 = sy + math.sin(rad)*dist_l
                    seg_surf = pygame.Surface((r_l*2+2, r_l*2+2), pygame.SRCALPHA)
                    pygame.draw.circle(seg_surf, (*flits_kl, alpha), (r_l+1,r_l+1), r_l)
                    surface.blit(seg_surf, (int(px2)-r_l-1, int(py2)-r_l-1))
        elif self.special_t > 0:
            special = self.special_actief
            if special == "brede_sweep":
                sweep_hoek = w.get("sweep_hoek", 200)
                sweep_frames = w.get("sweep_frames", 35)
                t_raw = 1.0 - self.special_t/sweep_frames
                prog = ease_in_out(t_raw)
                zh = fh - sweep_hoek/2 + prog*sweep_hoek
                rad = math.radians(zh)
                ex = sx+math.cos(rad)*w.get("sweep_bereik",72)
                ey = sy+math.sin(rad)*w.get("sweep_bereik",72)
                pygame.draw.line(surface, wapen_kl, (sx,sy), (int(ex),int(ey)), 7)
                pygame.draw.circle(surface, (255,200,100), (int(ex),int(ey)), 7)
            elif special in ("stoot","dash_aanval"):
                rad = math.radians(fh)
                ex = sx+math.cos(rad)*bereik*1.2
                ey = sy+math.sin(rad)*bereik*1.2
                pygame.draw.line(surface, wapen_kl, (sx,sy), (int(ex),int(ey)), 5)
                pygame.draw.circle(surface, (255,255,200), (int(ex),int(ey)), 6)
            elif special == "grondstamp":
                stamp_r = w.get("stamp_radius", 110)
                frames  = w.get("stamp_frames", 20)
                prog = ease_out(1.0 - self.special_t/frames)
                r_nu = int(stamp_r * prog)
                if r_nu > 0:
                    # Vullende cirkel die uitdijt
                    alpha_r = max(0, 200 - int(200*prog))
                    pygame.draw.circle(surface, (200,150,50), (sx,sy), r_nu, 3)
                    if r_nu > 10:
                        pygame.draw.circle(surface, (255,200,80), (sx,sy), r_nu//2, 2)
        else:
            rh2 = math.radians(fh+40)
            pygame.draw.line(surface, wapen_kl, (sx,sy),
                (int(sx+math.cos(rh2)*22), int(sy+math.sin(rh2)*22)), 3)

        if self._heeft_schild() and blok:
            sh = math.radians(fh-35)
            bsx = int(sx+math.cos(sh)*22); bsy = int(sy+math.sin(sh)*22)
            pygame.draw.circle(surface, C_SCHILD, (bsx,bsy), 13)
            pygame.draw.circle(surface, (230,185,90), (bsx,bsy), 13, 2)


class Vijand:
    _uid = 0
    @classmethod
    def nieuw_id(cls):
        cls._uid += 1; return cls._uid

    def __init__(self, x, y, type_, hp_multiplier=1.0, schade_multiplier=1.0):
        self.x = float(x); self.y = float(y)
        self.type = type_; self.id = Vijand.nieuw_id()
        self.schade_mult = schade_multiplier
        if type_ == "baas":
            self.max_hp   = VIJAND_HP_BASIS * hp_multiplier * 5
            self.radius   = 26
            self.snelheid = VIJAND_SNELHEID * 1.3
        elif type_ == "wolf":
            self.max_hp   = VIJAND_HP_BASIS * hp_multiplier * 0.8
            self.radius   = 13
            self.snelheid = VIJAND_SNELHEID * 1.1
        else:
            self.max_hp   = VIJAND_HP_BASIS * hp_multiplier
            self.radius   = 14
            self.snelheid = VIJAND_SNELHEID
        self.hp = self.max_hp
        self.fx = 0.0; self.fy = 1.0
        self.anim = 0; self.acd = 0
        self.flinch = 0; self.flinch_vx = 0.0; self.flinch_vy = 0.0
        # Wind-up: korte achteruitbeweging voor aanval
        self.windup = 0
        self.windup_vx = self.windup_vy = 0.0
        # Squash & stretch
        self.schaal_x = 1.0; self.schaal_y = 1.0
        self.hit_stop = 0  # individuele freeze bij hit
        # Wolf state machine
        self.wolf_staat   = "afstand"
        self.wolf_t       = 0
        self.wolf_dash_vx = 0.0
        self.wolf_dash_vy = 0.0
        self.wolf_glow    = 0.0
        # Aggro systeem
        self.aggro        = False
        self.aggro_bereik = 200 if type_ == "wolf" else 260
        self.groep_id     = 0    # wordt gezet bij spawn
        self.patrol_hoek  = random.uniform(0, math.pi*2)
        self.patrol_t     = random.randint(0, 120)
        # Burning conditie
        self.burning_t    = 0    # totale frames resterend
        self.burning_tick = 0    # frames tot volgende tick

    def krijg_schade(self, schade, van_x, van_y):
        self.hp -= schade
        knx, kny = normalize(self.x-van_x, self.y-van_y)
        self.flinch = FLINCH_VIJAND
        self.flinch_vx = knx*KNOCKBACK; self.flinch_vy = kny*KNOCKBACK
        self.schaal_x = 1.6; self.schaal_y = 0.5
        self.hit_stop = 4
        return self.hp <= 0

    def krijg_schade_swing(self, schade, kb_nx, kb_ny):
        """Schade met swing-gebaseerde knockback richting en hit stop."""
        self.hp -= schade
        self.flinch = FLINCH_VIJAND
        self.flinch_vx = kb_nx * KNOCKBACK
        self.flinch_vy = kb_ny * KNOCKBACK
        self.schaal_x = 1.6; self.schaal_y = 0.5
        self.hit_stop = 5  # iets langer voor meer impact gevoel
        return self.hp <= 0

    def krijg_schade_knockback(self, schade, van_x, van_y, knockback):
        self.hp -= schade
        knx, kny = normalize(self.x-van_x, self.y-van_y)
        self.flinch = FLINCH_VIJAND
        self.flinch_vx = knx*knockback; self.flinch_vy = kny*knockback
        self.schaal_x = 1.6; self.schaal_y = 0.5
        self.hit_stop = 4
        return self.hp <= 0

    def update(self, sp_x, sp_y, blok_check, fh_sp, speler_blok, speler_flinch_cd):
        dvx = sp_x-self.x; dvy = sp_y-self.y
        dist = math.hypot(dvx, dvy)
        self.fx, self.fy = normalize(dvx, dvy)

        # Hit stop: vijand bevriest kort bij treffer
        if self.hit_stop > 0:
            self.hit_stop -= 1
            self.schaal_x = lerp(self.schaal_x, 1.0, 0.15)
            self.schaal_y = lerp(self.schaal_y, 1.0, 0.15)
            return None

        # Aggro check — wordt wakker als speler dichtbij komt of geraakt wordt
        if not self.aggro:
            if dist < self.aggro_bereik or self.flinch > 0:
                self.aggro = True
            else:
                # Patrol gedrag: langzaam rondslenteren
                self._update_patrol(blok_check)
                if self.anim > 0: self.anim -= 1
                if self.acd  > 0: self.acd  -= 1
                self.schaal_x = lerp(self.schaal_x, 1.0, 0.1)
                self.schaal_y = lerp(self.schaal_y, 1.0, 0.1)
                return None

        if self.anim > 0: self.anim -= 1
        if self.acd  > 0: self.acd  -= 1

        # Squash & stretch richting neutraal
        self.schaal_x = lerp(self.schaal_x, 1.0, 0.15)
        self.schaal_y = lerp(self.schaal_y, 1.0, 0.15)

        if self.flinch > 0:
            self.flinch -= 1
            self._beweeg(self.flinch_vx, self.flinch_vy, blok_check)
            self.flinch_vx *= 0.8; self.flinch_vy *= 0.8
            return None

        # Wind-up beweging
        if self.windup > 0:
            self.windup -= 1
            self._beweeg(self.windup_vx, self.windup_vy, blok_check)
            return None

        aanval = None
        bereik   = 52 if self.type=="baas" else 48
        acd_duur = 60 if self.type=="baas" else 90
        melee_sch = VIJAND_MELEE_SCHADE * self.schade_mult
        pijl_sch  = PIJL_SCHADE         * self.schade_mult

        if self.type == "wolf":
            WOLF_AFSTAND     = 180   # gewenste afstand tijdens cirkelen
            WOLF_WINDUP_T    = 30    # frames oplichten voor dash
            WOLF_DASH_T      = 28    # frames van de dash — lang = ver
            WOLF_HERSTEL_T   = 100
            WOLF_DASH_SPEED  = DODGE_SPEED * 1.9   # veel sneller dan speler dodge
            WOLF_SCHADE      = VIJAND_MELEE_SCHADE * 1.2 * self.schade_mult

            if self.wolf_t > 0: self.wolf_t -= 1

            if self.wolf_staat == "afstand":
                self.wolf_glow = max(0.0, self.wolf_glow - 0.05)
                if dist > WOLF_AFSTAND + 30:
                    # Beweeg richting speler
                    self.schaal_x = lerp(self.schaal_x, 1.2, 0.1)
                    self.schaal_y = lerp(self.schaal_y, 0.85, 0.1)
                    self._beweeg(self.fx * self.snelheid, self.fy * self.snelheid, blok_check)
                elif dist < WOLF_AFSTAND - 30:
                    # Te dichtbij: stap achteruit
                    self._beweeg(-self.fx * self.snelheid * 0.7, -self.fy * self.snelheid * 0.7, blok_check)
                # Klaar om aan te vallen?
                if self.acd <= 0 and dist < WOLF_AFSTAND + 120:
                    self.wolf_staat = "windup"
                    self.wolf_t     = WOLF_WINDUP_T

            elif self.wolf_staat == "windup":
                # Stap achteruit en licht op
                self.wolf_glow = min(1.0, self.wolf_t / WOLF_WINDUP_T * 1.2)
                self._beweeg(-self.fx * 0.8, -self.fy * 0.8, blok_check)
                self.schaal_x = lerp(self.schaal_x, 0.65, 0.15)
                self.schaal_y = lerp(self.schaal_y, 1.5, 0.15)
                # Update richting naar speler tijdens windup
                if math.hypot(dvx, dvy) > 5:
                    self.fx, self.fy = normalize(dvx, dvy)
                if self.wolf_t == 0:
                    # Start dash — sla aanvalsrichting op voor betrouwbare blok check
                    self.wolf_staat    = "dash"
                    self.wolf_t        = WOLF_DASH_T
                    self.wolf_dash_vx  = self.fx * WOLF_DASH_SPEED
                    self.wolf_dash_vy  = self.fy * WOLF_DASH_SPEED
                    self.wolf_dash_fx  = self.fx   # richting opslaan voor blok hoek
                    self.wolf_dash_fy  = self.fy
                    self.wolf_heeft_geraakt = False
                    self.schaal_x = 1.5; self.schaal_y = 0.6

            elif self.wolf_staat == "dash":
                self.wolf_glow = lerp(self.wolf_glow, 0.0, 0.2)
                self._beweeg(self.wolf_dash_vx, self.wolf_dash_vy, blok_check)
                # Raakt de speler — maar slechts één keer per dash
                if dist < 44 and speler_flinch_cd <= 0 and not self.wolf_heeft_geraakt:
                    self.wolf_heeft_geraakt = True
                    # Geef aanvalsrichting mee zodat blok hoek klopt
                    aanval = ("melee", self.x - self.wolf_dash_fx * 40,
                              self.y - self.wolf_dash_fy * 40, WOLF_SCHADE)
                if self.wolf_t == 0:
                    self.wolf_staat = "herstel"
                    self.wolf_t     = WOLF_HERSTEL_T
                    self.acd        = WOLF_HERSTEL_T
                    self.schaal_x = 1.4; self.schaal_y = 0.7

            elif self.wolf_staat == "herstel":
                self.wolf_glow = 0.0
                # Loop weg van de speler na aanval
                if dist < WOLF_AFSTAND:
                    self._beweeg(-self.fx * self.snelheid, -self.fy * self.snelheid, blok_check)
                if self.wolf_t == 0:
                    self.wolf_staat = "afstand"

        elif self.type in ("melee","baas"):
            if dist > self.radius+10:
                # Stretch in looprichting
                self.schaal_x = lerp(self.schaal_x, 1.2, 0.1)
                self.schaal_y = lerp(self.schaal_y, 0.85, 0.1)
                self._beweeg(self.fx*self.snelheid, self.fy*self.snelheid, blok_check)
            if dist < bereik and self.acd <= 0:
                self.anim = 20; self.acd = acd_duur
                # Wind-up: stap achteruit voor aanval
                self.windup = 6
                self.windup_vx = -self.fx * 1.5
                self.windup_vy = -self.fy * 1.5
                self.schaal_x = 0.7; self.schaal_y = 1.4  # anticipatie squeeze
                rvn = math.degrees(math.atan2(self.y-sp_y, self.x-sp_x))
                if speler_flinch_cd <= 0:
                    geblokt = speler_blok and abs(hoek_diff(rvn, fh_sp)) < 60
                    sch = melee_sch * 0.3 if geblokt else melee_sch
                    aanval = ("melee", self.x, self.y, sch)
        else:
            # Boogschutter persoonlijkheid
            VLUCHTEN_AFSTAND = 130   # te dichtbij: wegrennen
            GEWENSTE_AFSTAND = 240
            AIM_FRAMES       = 35    # korter aim = meer druk
            SALVO_GROOTTE    = 3     # pijlen per salvo als speler ver weg is
            SALVO_INTERVAL   = 8    # frames tussen salvo-pijlen

            if not hasattr(self, 'aim_t'):    self.aim_t = 0
            if not hasattr(self, 'aim_fx'):   self.aim_fx = self.fx; self.aim_fy = self.fy
            if not hasattr(self, 'salvo_n'):  self.salvo_n = 0
            if not hasattr(self, 'salvo_t'):  self.salvo_t = 0

            # Paniek: vluchten als speler te dichtbij
            if dist < VLUCHTEN_AFSTAND and self.aim_t == 0:
                # Ren loodrecht weg van speler + beetje zijwaarts
                vlucht_x = -self.fx * 1.4 + self.fy * 0.5
                vlucht_y = -self.fy * 1.4 - self.fx * 0.5
                vl = math.hypot(vlucht_x, vlucht_y)
                if vl > 0: vlucht_x, vlucht_y = vlucht_x/vl, vlucht_y/vl
                self._beweeg(vlucht_x * self.snelheid * 1.3, vlucht_y * self.snelheid * 1.3, blok_check)
                self.schaal_x = lerp(self.schaal_x, 1.3, 0.12)
                self.schaal_y = lerp(self.schaal_y, 0.75, 0.12)
            elif self.aim_t == 0 and self.salvo_t == 0:
                # Normale repositionering
                if dist > GEWENSTE_AFSTAND + 30:
                    self._beweeg(self.fx*self.snelheid*0.8, self.fy*self.snelheid*0.8, blok_check)
                elif dist < GEWENSTE_AFSTAND - 30:
                    self._beweeg(-self.fx*0.5, -self.fy*0.5, blok_check)

            # Salvo aftellen
            if self.salvo_t > 0:
                self.salvo_t -= 1
                if self.salvo_t == 0 and self.salvo_n > 0:
                    # Volgende pijl in salvo
                    aanval = ("pijl", self.x, self.y,
                              self.aim_fx*PIJL_SNELHEID, self.aim_fy*PIJL_SNELHEID, pijl_sch)
                    self.salvo_n -= 1
                    if self.salvo_n > 0:
                        self.salvo_t = SALVO_INTERVAL

            # Aim fase
            elif self.aim_t > 0:
                self.aim_t -= 1
                self.fx, self.fy = self.aim_fx, self.aim_fy
                if self.aim_t == 0:
                    self.schaal_x = 1.4; self.schaal_y = 0.6
                    if dist > VLUCHTEN_AFSTAND * 1.5:
                        # Ver weg: salvo
                        aanval = ("pijl", self.x, self.y,
                                  self.aim_fx*PIJL_SNELHEID, self.aim_fy*PIJL_SNELHEID, pijl_sch)
                        self.salvo_n = SALVO_GROOTTE - 1
                        self.salvo_t = SALVO_INTERVAL
                    else:
                        # Dichtbij: enkelen pijl
                        aanval = ("pijl", self.x, self.y,
                                  self.aim_fx*PIJL_SNELHEID, self.aim_fy*PIJL_SNELHEID, pijl_sch)

            # Start aim als cooldown klaar
            elif self.acd <= 0 and dist < 400 and dist > VLUCHTEN_AFSTAND:
                cd = int(2.0*FPS) if dist < GEWENSTE_AFSTAND else int(3.0*FPS)
                self.acd = cd
                self.aim_t  = AIM_FRAMES
                self.aim_fx = self.fx
                self.aim_fy = self.fy
                self.schaal_x = 0.8; self.schaal_y = 1.2
        # Burning DoT
        if self.burning_t > 0:
            self.burning_t    -= 1
            self.burning_tick -= 1
            if self.burning_tick <= 0:
                self.burning_tick = 120   # elke 2 sec (120 frames) een tick
                self.hp = max(0, self.hp - 8)
                self.schaal_x = 1.3; self.schaal_y = 0.75  # kleine flash

        return aanval

    def _update_patrol(self, blok_check):
        """Rustig rondslenteren zolang niet aggro."""
        self.patrol_t -= 1
        if self.patrol_t <= 0:
            self.patrol_hoek += random.uniform(-1.2, 1.2)
            self.patrol_t = random.randint(60, 180)
        px = math.cos(self.patrol_hoek) * self.snelheid * 0.3
        py = math.sin(self.patrol_hoek) * self.snelheid * 0.3
        self._beweeg(px, py, blok_check)
        self.schaal_x = lerp(self.schaal_x, 1.1, 0.06)
        self.schaal_y = lerp(self.schaal_y, 0.92, 0.06)

    def _beweeg(self, vx, vy, blok_check):
        r = self.radius - 2
        nx = self.x+vx; ny = self.y+vy
        if not any(blok_check(int((nx+ox)//TILE), int((self.y+oy)//TILE))
                   for ox in (-r,0,r) for oy in (-r,0,r)):
            self.x = nx
        if not any(blok_check(int((self.x+ox)//TILE), int((ny+oy)//TILE))
                   for ox in (-r,0,r) for oy in (-r,0,r)):
            self.y = ny

    def teken(self, surface, cam_x, cam_y):
        sx = int(self.x-cam_x); sy = int(self.y-cam_y); r = self.radius
        knip = self.flinch>0 and (self.flinch//4)%2==0

        # Squash & stretch
        rw  = max(4, int(r * self.schaal_x))
        rh_s = max(4, int(r * self.schaal_y))

        if self.type == "baas":
            kl = (220,60,220) if not knip else (255,255,255)
        elif self.type == "wolf":
            if knip:
                kl = (255,255,255)
            else:
                # Glow effect: mix naar lichtgeel/wit naarmate wolf_glow hoger is
                g = getattr(self, "wolf_glow", 0.0)
                kl = (int(160+g*95), int(130+g*100), int(60+g*80))
        else:
            kl = (220,60,60) if knip else (C_MELEE if self.type=="melee" else C_RANGED)

        pygame.draw.ellipse(surface, C_SCH, (sx-rw+4, sy+rh_s-4, rw*2, rh_s))
        pygame.draw.ellipse(surface, kl, (sx-rw, sy-rh_s, rw*2, rh_s*2))

        if self.type == "baas":
            pygame.draw.ellipse(surface, (255,150,255), (sx-rw, sy-rh_s, rw*2, rh_s*2), 3)
        elif self.type == "wolf":
            g = getattr(self, "wolf_glow", 0.0)
            if g > 0.1:
                # Oplichtende ring rond de wolf tijdens windup
                glow_r = int(r * 1.6 + g * 12)
                glow_alpha = int(g * 180)
                glow_surf = pygame.Surface((glow_r*2+4, glow_r*2+4), pygame.SRCALPHA)
                pygame.draw.circle(glow_surf, (255, 220, 80, glow_alpha),
                                   (glow_r+2, glow_r+2), glow_r)
                surface.blit(glow_surf, (sx-glow_r-2, sy-glow_r-2))

        oog_r = 5 if self.type != "baas" else 8
        pygame.draw.circle(surface, C_OOG,
            (int(sx+self.fx*int(r*0.6)), int(sy+self.fy*int(r*0.6))), oog_r)

        # Slapend indicator — "z z" boven vijand als niet aggro
        if not self.aggro:
            bob = int(math.sin(pygame.time.get_ticks() * 0.003) * 3)
            zs = pygame.font.Font(None, 16).render("z z", True, (160, 185, 255))
            surface.blit(zs, (sx - zs.get_width()//2, sy - rh_s - 16 + bob))

        # Burning visueel — oranje gloed
        if self.burning_t > 0:
            puls = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.015)
            burn_r = int(r * 1.4 + puls * 6)
            burn_alpha = int(120 + puls * 80)
            bs = pygame.Surface((burn_r*2+4, burn_r*2+4), pygame.SRCALPHA)
            pygame.draw.circle(bs, (255, int(80 + puls*60), 0, burn_alpha),
                               (burn_r+2, burn_r+2), burn_r)
            surface.blit(bs, (sx-burn_r-2, sy-burn_r-2))

        bw = r*3; ratio = max(0, self.hp/self.max_hp)
        pygame.draw.rect(surface, (80,20,20),  (sx-bw//2, sy-r-10, bw, 6))
        pygame.draw.rect(surface, (220,60,60), (sx-bw//2, sy-r-10, int(bw*ratio), 6))

        fh = math.degrees(math.atan2(self.fy, self.fx))
        if self.type in ("melee","baas"):
            if self.anim > 0:
                t_raw = 1.0 - self.anim/20
                prog = ease_in_out(t_raw)
                zh = fh-50+prog*100; rad = math.radians(zh)
                zl = 50 if self.type=="baas" else 42
                pygame.draw.line(surface, C_ZWAARD, (sx,sy),
                    (int(sx+math.cos(rad)*zl), int(sy+math.sin(rad)*zl)),
                    5 if self.type=="baas" else 4)
            elif self.windup > 0:
                rh2 = math.radians(fh+160)
                pygame.draw.line(surface, C_ZWAARD, (sx,sy),
                    (int(sx+math.cos(rh2)*22), int(sy+math.sin(rh2)*22)), 3)
            else:
                rh2 = math.radians(fh+35)
                pygame.draw.line(surface, C_ZWAARD, (sx,sy),
                    (int(sx+math.cos(rh2)*25), int(sy+math.sin(rh2)*25)), 3)
        elif self.type == "ranged":
            bh = math.radians(fh)
            bx = int(sx+math.cos(bh)*18); by = int(sy+math.sin(bh)*18)
            pygame.draw.line(surface, (140,100,50), (sx,sy), (bx,by), 3)
            pygame.draw.circle(surface, (160,120,60), (bx,by), 5)
            # Aim line tijdens aim fase — rood, pulserend, wordt feller naarmate shot dichterbij
            aim_t = getattr(self, 'aim_t', 0)
            if aim_t > 0:
                AIM_FRAMES = 45
                charge = 1.0 - aim_t / AIM_FRAMES  # 0.0 = net begonnen, 1.0 = klaar
                puls = abs(math.sin(aim_t * 0.25))
                aim_kl = (255, int(80 - charge*60), int(80 - charge*60))
                aim_len = int(80 + charge * 80)
                # Teken aim lijn als reeks stippen met fade
                aim_rad = math.atan2(self.aim_fy if hasattr(self,'aim_fy') else self.fy,
                                     self.aim_fx if hasattr(self,'aim_fx') else self.fx)
                for seg in range(0, aim_len, 6):
                    t_seg = seg / aim_len
                    alpha = int((0.3 + 0.7*charge) * (1 - t_seg*0.7) * 220 * puls)
                    r_dot = max(1, int((1 - t_seg) * (3 + charge*4)))
                    px3 = int(sx + math.cos(aim_rad) * (20 + seg))
                    py3 = int(sy + math.sin(aim_rad) * (20 + seg))
                    dot_surf = pygame.Surface((r_dot*2+2, r_dot*2+2), pygame.SRCALPHA)
                    pygame.draw.circle(dot_surf, (*aim_kl, alpha), (r_dot+1, r_dot+1), r_dot)
                    surface.blit(dot_surf, (px3-r_dot-1, py3-r_dot-1))


class Pijl:
    def __init__(self, x, y, dx, dy, schade=None):
        self.x=float(x); self.y=float(y); self.dx=dx; self.dy=dy
        self.schade = schade if schade is not None else PIJL_SCHADE

    def update(self, blok_check):
        self.x+=self.dx; self.y+=self.dy
        return blok_check(int(self.x//TILE), int(self.y//TILE))

    def teken(self, surface, cam_x, cam_y):
        sx=int(self.x-cam_x); sy=int(self.y-cam_y)
        ex=int(self.x+self.dx*10-cam_x); ey=int(self.y+self.dy*10-cam_y)
        pygame.draw.line(surface, C_PIJL, (sx,sy), (ex,ey), 3)
        pygame.draw.circle(surface, (230,190,110), (sx,sy), 4)
