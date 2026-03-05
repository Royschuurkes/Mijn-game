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

    def verwerk_events(self, events):
        w = self._wapen()
        zwaard_frames = w["zwaard_frames"] if w["zwaard_frames"] > 0 else ZWAARD_FRAMES
        zwaard_cd     = w["zwaard_cd"]     if w["zwaard_cd"]     > 0 else ZWAARD_CD
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                if (self.dodge_t<=0 and self.dodge_cd<=0
                        and self.sta>=STAMINA_DODGE and self.kan_aanvallen):
                    self.dodge_t = DODGE_FRAMES
                    self.dodge_cd = DODGE_CD
                    self.sta -= STAMINA_DODGE
                    self.sta_delay = STAMINA_DELAY
                    # Stretch bij dodge start
                    self.schaal_x = 1.4; self.schaal_y = 0.7
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                # Met schild: aanvallen met simpel_zwaard stats
                from wapens import get_wapen as _gw
                w_a = _gw("simpel_zwaard") if self._heeft_schild() else w
                zf = w_a["zwaard_frames"] if w_a["zwaard_frames"] > 0 else ZWAARD_FRAMES
                zc = w_a["zwaard_cd"]     if w_a["zwaard_cd"]     > 0 else ZWAARD_CD
                if (self.zw_t<=0 and self.zw_cd<=0
                        and self.sta>=STAMINA_ZWAARD and self.kan_aanvallen):
                    self.zw_t = zf
                    self.zw_cd = zc
                    self.sta -= STAMINA_ZWAARD
                    self.sta_delay = STAMINA_DELAY
                    self.geraakt = set()
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

    def update(self, keys, muis_pos, cam_x, cam_y, blok_check, tile_op, blok):
        self.tik += 1
        dmx = muis_pos[0]+cam_x - self.x
        dmy = muis_pos[1]+cam_y - self.y
        if math.hypot(dmx, dmy) > 5:
            self.fx, self.fy = normalize(dmx, dmy)

        mx, my = 0.0, 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    my -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  my += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  mx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: mx += 1
        mx, my = normalize(mx, my)
        self.beweeg_x = mx; self.beweeg_y = my

        huidig = tile_op(int(self.x//TILE), int(self.y//TILE))
        if self.dodge_t > 0 or (self.special_t > 0 and self.special_actief in ("stoot","dash_aanval")):
            speed = DODGE_SPEED + extra_dodge(self.save)
        elif blok:          speed = PLAYER_SPEED * 0.5
        elif huidig == PAD: speed = PLAYER_SPEED
        else:               speed = PLAYER_SPEED * 0.75

        if self.flinch_t > 0:
            dx, dy = self.flinch_vx, self.flinch_vy
            self.flinch_vx *= 0.8; self.flinch_vy *= 0.8
        elif self.special_t > 0 and self.special_actief in ("stoot","dash_aanval"):
            dx, dy = self.dash_vx, self.dash_vy
        elif self.dodge_t > 0:
            dx, dy = self.fx*speed, self.fy*speed
        else:
            dx, dy = mx*speed, my*speed

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

        in_struik = tile_op(int(self.x//TILE), int(self.y//TILE)) == STRUIK
        if in_struik and self.dodge_t == 0:
            self.hp = max(0, self.hp - THORN_DAMAGE)

        if self.sta_delay > 0 or blok:
            if not blok: self.sta_delay -= 1
        elif self.sta < self.msta:
            self.sta = min(self.msta, self.sta + (self.msta * STAMINA_REGEN_PCT / FPS))

        return in_struik

    def krijg_schade(self, schade, van_x, van_y):
        if self.dodge_t > 0 or self.flinch_cd > 0: return False
        self.hp = max(0, self.hp - schade)
        knx, kny = normalize(self.x-van_x, self.y-van_y)
        self.flinch_t = FLINCH_SPELER
        self.flinch_cd = FLINCH_CD_SPELER
        self.flinch_vx = knx * KNOCKBACK
        self.flinch_vy = kny * KNOCKBACK
        return True

    def zwaard_hits(self, vijanden):
        hits = []
        if self.zw_t <= 0: return hits
        from wapens import get_wapen as _gw
        w = _gw("simpel_zwaard") if self._heeft_schild() else self._wapen()
        bereik = w.get("bereik", ZWAARD_BEREIK)
        hoek_w = w.get("hoek", ZWAARD_HOEK)
        zwaard_frames = w["zwaard_frames"] if w["zwaard_frames"] > 0 else ZWAARD_FRAMES
        # Ease-in-out curve voor de zwaai
        t_raw = 1.0 - self.zw_t / zwaard_frames
        prog = ease_in_out(t_raw)
        fh = math.degrees(math.atan2(self.fy, self.fx))
        zh = fh - hoek_w/2 + prog*hoek_w
        schade = w.get("schade", SPELER_SCHADE) + extra_schade(self.save)
        for v in vijanden:
            if v.id in self.geraakt: continue
            dvx = v.x-self.x; dvy = v.y-self.y
            if math.hypot(dvx, dvy) < bereik:
                vh = math.degrees(math.atan2(dvy, dvx))
                if abs(hoek_diff(zh, vh)) < 38:
                    self.geraakt.add(v.id)
                    hits.append((v, schade))
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
        pygame.draw.ellipse(surface, C_SCH, (sx-rw+4, sy+rh_s-4, rw*2, rh_s))
        kl = (220,60,60) if knip else (C_SP_DOD if self.dodge_t>0 else C_SP)
        pygame.draw.ellipse(surface, kl, (sx-rw, sy-rh_s, rw*2, rh_s*2))
        pygame.draw.circle(surface, C_OOG, (int(sx+self.fx*9), int(sy+self.fy*9)), 5)

        fh = math.degrees(math.atan2(self.fy, self.fx))
        wapen_kl = w.get("kleur", C_ZWAARD)
        bereik = w.get("bereik", ZWAARD_BEREIK)
        hoek_w = w.get("hoek", ZWAARD_HOEK)
        zwaard_frames = w["zwaard_frames"] if w["zwaard_frames"] > 0 else ZWAARD_FRAMES

        if self.zw_t > 0:
            t_raw = 1.0 - self.zw_t / zwaard_frames
            prog = ease_in_out(t_raw)
            zh = fh - hoek_w/2 + prog*hoek_w
            rad = math.radians(zh)
            ex = sx+math.cos(rad)*bereik; ey = sy+math.sin(rad)*bereik
            # Staart van de zwaai
            zh_prev = fh - hoek_w/2 + ease_in_out(max(0,t_raw-0.15))*hoek_w
            rad_prev = math.radians(zh_prev)
            mx2 = sx+math.cos(rad_prev)*bereik*0.7
            my2 = sy+math.sin(rad_prev)*bereik*0.7
            pygame.draw.line(surface, tuple(max(0,c-60) for c in wapen_kl),
                             (int(mx2),int(my2)), (int(ex),int(ey)), 3)
            pygame.draw.line(surface, wapen_kl, (sx,sy), (int(ex),int(ey)), 5)
            pygame.draw.circle(surface, (240,240,255), (int(ex),int(ey)), 5)
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
        # Wolf state machine
        self.wolf_staat   = "afstand"
        self.wolf_t       = 0
        self.wolf_dash_vx = 0.0
        self.wolf_dash_vy = 0.0
        self.wolf_glow    = 0.0

    def krijg_schade(self, schade, van_x, van_y):
        self.hp -= schade
        knx, kny = normalize(self.x-van_x, self.y-van_y)
        self.flinch = FLINCH_VIJAND
        self.flinch_vx = knx*KNOCKBACK; self.flinch_vy = kny*KNOCKBACK
        # Platdrukken bij hit
        self.schaal_x = 1.6; self.schaal_y = 0.5
        return self.hp <= 0

    def krijg_schade_knockback(self, schade, van_x, van_y, knockback):
        self.hp -= schade
        knx, kny = normalize(self.x-van_x, self.y-van_y)
        self.flinch = FLINCH_VIJAND
        self.flinch_vx = knx*knockback; self.flinch_vy = kny*knockback
        self.schaal_x = 1.6; self.schaal_y = 0.5
        return self.hp <= 0

    def update(self, sp_x, sp_y, blok_check, fh_sp, speler_blok, speler_flinch_cd):
        dvx = sp_x-self.x; dvy = sp_y-self.y
        dist = math.hypot(dvx, dvy)
        self.fx, self.fy = normalize(dvx, dvy)

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
            WOLF_WINDUP_T    = 30    # frames oplichten voor dash (langer = beter te ontwijken)
            WOLF_DASH_T      = 10    # frames van de dash zelf
            WOLF_HERSTEL_T   = 100   # frames na aanval voor volgende
            WOLF_DASH_SPEED  = DODGE_SPEED * 1.1
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
                if self.acd <= 0 and dist < WOLF_AFSTAND + 50:
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
                    # Start dash
                    self.wolf_staat   = "dash"
                    self.wolf_t       = WOLF_DASH_T
                    self.wolf_dash_vx = self.fx * WOLF_DASH_SPEED
                    self.wolf_dash_vy = self.fy * WOLF_DASH_SPEED
                    self.schaal_x = 1.5; self.schaal_y = 0.6

            elif self.wolf_staat == "dash":
                self.wolf_glow = lerp(self.wolf_glow, 0.0, 0.2)
                self._beweeg(self.wolf_dash_vx, self.wolf_dash_vy, blok_check)
                # Raakt de speler tijdens de dash?
                if dist < 44 and speler_flinch_cd <= 0:
                    rvn = math.degrees(math.atan2(self.y-sp_y, self.x-sp_x))
                    geblokt = speler_blok and abs(hoek_diff(rvn, fh_sp)) < 60
                    sch = WOLF_SCHADE * 0.3 if geblokt else WOLF_SCHADE
                    aanval = ("melee", self.x, self.y, sch)
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
            gd = 230
            if dist > gd+30:
                self._beweeg(self.fx*self.snelheid*0.8, self.fy*self.snelheid*0.8, blok_check)
            elif dist < gd-30:
                self._beweeg(-self.fx*0.6, -self.fy*0.6, blok_check)
            if self.acd <= 0 and dist < 380:
                self.acd = 3*FPS
                # Kleine wind-up voor pijl
                self.windup = 4; self.windup_vx = -self.fx; self.windup_vy = -self.fy
                self.schaal_x = 0.75; self.schaal_y = 1.3
                aanval = ("pijl", self.x, self.y,
                          self.fx*PIJL_SNELHEID, self.fy*PIJL_SNELHEID, pijl_sch)
        return aanval

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
                # Wind-up animatie: wapen naar achteren
                rh2 = math.radians(fh+160)
                pygame.draw.line(surface, C_ZWAARD, (sx,sy),
                    (int(sx+math.cos(rh2)*22), int(sy+math.sin(rh2)*22)), 3)
            else:
                rh2 = math.radians(fh+35)
                pygame.draw.line(surface, C_ZWAARD, (sx,sy),
                    (int(sx+math.cos(rh2)*25), int(sy+math.sin(rh2)*25)), 3)
        else:
            bh = math.radians(fh)
            bx = int(sx+math.cos(bh)*18); by = int(sy+math.sin(bh)*18)
            pygame.draw.line(surface, (140,100,50), (sx,sy), (bx,by), 3)
            pygame.draw.circle(surface, (160,120,60), (bx,by), 5)


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
