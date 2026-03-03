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

    @property
    def levend(self): return self.hp > 0
    @property
    def kan_aanvallen(self): return self.flinch_t == 0

    def verwerk_events(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                if (self.dodge_t<=0 and self.dodge_cd<=0
                        and self.sta>=STAMINA_DODGE and self.kan_aanvallen):
                    self.dodge_t = DODGE_FRAMES
                    self.dodge_cd = DODGE_CD
                    self.sta -= STAMINA_DODGE
                    self.sta_delay = STAMINA_DELAY
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if (self.zw_t<=0 and self.zw_cd<=0
                        and self.sta>=STAMINA_ZWAARD and self.kan_aanvallen):
                    self.zw_t = ZWAARD_FRAMES
                    self.zw_cd = ZWAARD_CD
                    self.sta -= STAMINA_ZWAARD
                    self.sta_delay = STAMINA_DELAY
                    self.geraakt = set()

    def update(self, keys, muis_pos, cam_x, cam_y, blok_check, tile_op, blok):
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

        huidig = tile_op(int(self.x//TILE), int(self.y//TILE))
        if self.dodge_t > 0:   speed = DODGE_SPEED + extra_dodge(self.save)
        elif blok:             speed = PLAYER_SPEED * 0.5
        elif huidig == PAD:    speed = PLAYER_SPEED
        else:                  speed = PLAYER_SPEED * 0.75

        if self.flinch_t > 0:
            dx, dy = self.flinch_vx, self.flinch_vy
            self.flinch_vx *= 0.8; self.flinch_vy *= 0.8
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

        for attr in ("dodge_t","dodge_cd","zw_t","zw_cd","flinch_t","flinch_cd"):
            if getattr(self, attr) > 0:
                setattr(self, attr, getattr(self, attr)-1)

        in_struik = tile_op(int(self.x//TILE), int(self.y//TILE)) == STRUIK
        if in_struik and self.dodge_t == 0:
            self.hp = max(0, self.hp - THORN_DAMAGE)

        if self.sta_delay > 0 or blok:
            if not blok: self.sta_delay -= 1
        elif self.sta < self.msta:
            self.sta = min(self.msta, self.sta + STAMINA_REGEN)

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
        prog = 1.0 - self.zw_t/ZWAARD_FRAMES
        fh = math.degrees(math.atan2(self.fy, self.fx))
        zh = fh - ZWAARD_HOEK/2 + prog*ZWAARD_HOEK
        schade = SPELER_SCHADE + extra_schade(self.save)
        for v in vijanden:
            if v.id in self.geraakt: continue
            dvx = v.x-self.x; dvy = v.y-self.y
            if math.hypot(dvx, dvy) < ZWAARD_BEREIK:
                vh = math.degrees(math.atan2(dvy, dvx))
                if abs(hoek_diff(zh, vh)) < 38:
                    self.geraakt.add(v.id)
                    hits.append((v, schade))
        return hits

    def teken(self, surface, cam_x, cam_y, blok):
        sx = int(self.x-cam_x); sy = int(self.y-cam_y); r = 15
        knip = self.flinch_t>0 and (self.flinch_t//4)%2==0
        pygame.draw.ellipse(surface, C_SCH, (sx-r+4, sy+r-4, r*2, r))
        kl = (220,60,60) if knip else (C_SP_DOD if self.dodge_t>0 else C_SP)
        pygame.draw.circle(surface, kl, (sx,sy), r)
        pygame.draw.circle(surface, C_OOG, (int(sx+self.fx*9), int(sy+self.fy*9)), 5)
        fh = math.degrees(math.atan2(self.fy, self.fx))
        if self.zw_t > 0:
            prog = 1.0-self.zw_t/ZWAARD_FRAMES
            zh = fh - ZWAARD_HOEK/2 + prog*ZWAARD_HOEK
            rad = math.radians(zh)
            ex = sx+math.cos(rad)*ZWAARD_BEREIK
            ey = sy+math.sin(rad)*ZWAARD_BEREIK
            pygame.draw.line(surface, C_ZWAARD, (sx,sy), (int(ex),int(ey)), 5)
            pygame.draw.circle(surface, (240,240,255), (int(ex),int(ey)), 5)
        else:
            rh = math.radians(fh+40)
            pygame.draw.line(surface, C_ZWAARD, (sx,sy),
                (int(sx+math.cos(rh)*22), int(sy+math.sin(rh)*22)), 3)
        if blok:
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

        # Baas is groter en sterker
        if type_ == "baas":
            self.max_hp = VIJAND_HP_BASIS * hp_multiplier * 5
            self.radius = 26
            self.snelheid = VIJAND_SNELHEID * 1.3
        else:
            self.max_hp = VIJAND_HP_BASIS * hp_multiplier
            self.radius = 14
            self.snelheid = VIJAND_SNELHEID

        self.hp = self.max_hp
        self.fx = 0.0; self.fy = 1.0
        self.anim = 0; self.acd = 0
        self.flinch = 0; self.flinch_vx = 0.0; self.flinch_vy = 0.0

    def krijg_schade(self, schade, van_x, van_y):
        self.hp -= schade
        knx, kny = normalize(self.x-van_x, self.y-van_y)
        self.flinch = FLINCH_VIJAND
        self.flinch_vx = knx*KNOCKBACK
        self.flinch_vy = kny*KNOCKBACK
        return self.hp <= 0

    def update(self, sp_x, sp_y, blok_check, fh_sp, speler_blok, speler_flinch_cd):
        dvx = sp_x-self.x; dvy = sp_y-self.y
        dist = math.hypot(dvx, dvy)
        self.fx, self.fy = normalize(dvx, dvy)
        if self.anim > 0: self.anim -= 1
        if self.acd  > 0: self.acd  -= 1

        if self.flinch > 0:
            self.flinch -= 1
            self._beweeg(self.flinch_vx, self.flinch_vy, blok_check)
            self.flinch_vx *= 0.8; self.flinch_vy *= 0.8
            return None

        aanval = None
        bereik = 52 if self.type=="baas" else 48
        acd_duur = 60 if self.type=="baas" else 90
        melee_sch = VIJAND_MELEE_SCHADE * self.schade_mult
        pijl_sch  = PIJL_SCHADE         * self.schade_mult

        if self.type in ("melee","baas"):
            if dist > self.radius+10:
                self._beweeg(self.fx*self.snelheid, self.fy*self.snelheid, blok_check)
            if dist < bereik and self.acd <= 0:
                self.anim = 20; self.acd = acd_duur
                rvn = math.degrees(math.atan2(self.y-sp_y, self.x-sp_x))
                if not (speler_blok and abs(hoek_diff(rvn, fh_sp)) < 60):
                    if speler_flinch_cd <= 0:
                        aanval = ("melee", self.x, self.y, melee_sch)
        else:
            gd = 230
            if dist > gd+30:   self._beweeg(self.fx*self.snelheid*0.8, self.fy*self.snelheid*0.8, blok_check)
            elif dist < gd-30: self._beweeg(-self.fx*0.6, -self.fy*0.6, blok_check)
            if self.acd <= 0 and dist < 380:
                self.acd = 3*FPS
                aanval = ("pijl", self.x, self.y,
                          self.fx*PIJL_SNELHEID, self.fy*PIJL_SNELHEID, pijl_sch)
        return aanval

    def _beweeg(self, vx, vy, blok_check):
        r = self.radius - 2
        nx = self.x+vx; ny = self.y+vy
        if not any(blok_check(int((nx+ox)//TILE), int((self.y+oy)//TILE))
                   for ox in (-r,r) for oy in (-r,r)):
            self.x = nx
        if not any(blok_check(int((self.x+ox)//TILE), int((ny+oy)//TILE))
                   for ox in (-r,r) for oy in (-r,r)):
            self.y = ny

    def teken(self, surface, cam_x, cam_y):
        sx = int(self.x-cam_x); sy = int(self.y-cam_y)
        r  = self.radius
        knip = self.flinch>0 and (self.flinch//4)%2==0

        if self.type == "baas":
            kl = (220,60,220) if not knip else (255,255,255)
        else:
            kl = (220,60,60) if knip else (C_MELEE if self.type=="melee" else C_RANGED)

        pygame.draw.ellipse(surface, C_SCH, (sx-r+4, sy+r-4, r*2, r))
        pygame.draw.circle(surface, kl, (sx,sy), r)

        # Rand voor baas
        if self.type == "baas":
            pygame.draw.circle(surface, (255,150,255), (sx,sy), r, 3)

        pygame.draw.circle(surface, C_OOG,
            (int(sx+self.fx*int(r*0.6)), int(sy+self.fy*int(r*0.6))),
            5 if self.type!="baas" else 8)

        # HP balk
        bw = r*3; ratio = max(0, self.hp/self.max_hp)
        pygame.draw.rect(surface, (80,20,20),  (sx-bw//2, sy-r-10, bw, 6))
        pygame.draw.rect(surface, (220,60,60), (sx-bw//2, sy-r-10, int(bw*ratio), 6))

        # Zwaard/boog tekenen
        fh = math.degrees(math.atan2(self.fy, self.fx))
        if self.type in ("melee","baas"):
            if self.anim > 0:
                prog = 1.0-self.anim/20
                zh = fh-50+prog*100; rad = math.radians(zh)
                zl = 50 if self.type=="baas" else 42
                pygame.draw.line(surface, C_ZWAARD, (sx,sy),
                    (int(sx+math.cos(rad)*zl), int(sy+math.sin(rad)*zl)),
                    5 if self.type=="baas" else 4)
            else:
                rh = math.radians(fh+35)
                pygame.draw.line(surface, C_ZWAARD, (sx,sy),
                    (int(sx+math.cos(rh)*25), int(sy+math.sin(rh)*25)), 3)
        else:
            bh = math.radians(fh)
            bx = int(sx+math.cos(bh)*18); by = int(sy+math.sin(bh)*18)
            pygame.draw.line(surface, (140,100,50), (sx,sy), (bx,by), 3)
            pygame.draw.circle(surface, (160,120,60), (bx,by), 5)


class Pijl:
    def __init__(self, x, y, dx, dy, schade=None):
        self.x = float(x); self.y = float(y)
        self.dx = dx; self.dy = dy
        self.schade = schade if schade is not None else PIJL_SCHADE

    def update(self, blok_check):
        self.x += self.dx; self.y += self.dy
        return blok_check(int(self.x//TILE), int(self.y//TILE))

    def teken(self, surface, cam_x, cam_y):
        sx = int(self.x-cam_x); sy = int(self.y-cam_y)
        ex = int(self.x+self.dx*10-cam_x); ey = int(self.y+self.dy*10-cam_y)
        pygame.draw.line(surface, C_PIJL, (sx,sy), (ex,ey), 3)
        pygame.draw.circle(surface, (230,190,110), (sx,sy), 4)
