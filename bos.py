# bos.py - Bos gevecht scene met floor/kamer systeem (BoI-stijl)
import math, random, pygame
from opslaan import *
from entiteiten import Speler, Vijand, Pijl, normalize, hoek_diff
from kaart import (genereer_bos, teken_bos_tegel, teken_boom_object,
                   BOOM_PAL, KAART_B, KAART_H)
from juice import ScreenShake, FreezeFrames, PartikelSysteem, SchadeCijferSysteem, HitFlash
from level_manager import LevelManager, genereer_floor_graph, TEGENOVER
import geluid


def puls_kleur(basis, highlight, t, snelheid=0.08):
    f = (math.sin(t * snelheid) + 1) / 2
    return tuple(int(basis[i] + (highlight[i]-basis[i])*f) for i in range(3))


class BosScene:
    def __init__(self, screen, clock, save):
        self.screen = screen; self.clock = clock; self.save = save
        self.level_mgr = LevelManager()
        self.font_s = pygame.font.SysFont("monospace", 15)
        self.font_m = pygame.font.SysFont("monospace", 22)
        self.font_g = pygame.font.SysFont("monospace", 52, bold=True)
        self.tik = 0
        self.speler = None
        self._genereer_floor(eerste=True)

    def _genereer_floor(self, eerste=True):
        self.floor_graph, self.start_pos = genereer_floor_graph(self.level_mgr.floor_nr)
        self.huidige_pos = self.start_pos
        # Genereer kaart voor elke kamer met vaste seed
        for i, (pos, kamer) in enumerate(self.floor_graph.items()):
            seed = abs(hash((pos, self.level_mgr.floor_nr, i))) % 99999
            rng_state = random.getstate()
            random.seed(seed)
            kd = genereer_bos(kamer["deuren"])
            kamer["kaart_data"] = kd
            random.setstate(rng_state)
        self._laad_kamer(self.start_pos, verplaatsing=None, eerste=eerste)

    def _laad_kamer(self, grid_pos, verplaatsing=None, eerste=False):
        self.huidige_pos = grid_pos
        kamer = self.floor_graph[grid_pos]
        kamer["bezocht"] = True
        kaart, bomen, pal_map, spawn_pos, tile_op = kamer["kaart_data"]
        self.kaart = kaart; self.bomen = bomen
        self.pal_map = pal_map; self.tile_op = tile_op
        self.W = KAART_B; self.H = KAART_H
        # Speler spawnpositie: tegenover de deur waardoorheen hij binnenkomt
        if verplaatsing is None:
            entry = "W" if "W" in spawn_pos else list(spawn_pos.keys())[0]
        else:
            entry = TEGENOVER[verplaatsing]
            if entry not in spawn_pos:
                entry = list(spawn_pos.keys())[0]
        stx, sty = spawn_pos[entry]
        sp_x = stx*TILE + TILE//2
        sp_y = sty*TILE + TILE//2
        if eerste:
            self.speler = Speler(sp_x, sp_y, self.save)
            self.cam_x = float(sp_x - SCREEN_W/2)
            self.cam_y = float(sp_y - SCREEN_H/2)
        else:
            self.speler.x = float(sp_x)
            self.speler.y = float(sp_y)
            self.speler.dodge_t = self.speler.dodge_cd = 0
            self.speler.flinch_cd = 0
        self.pijlen = []
        self.shake  = ScreenShake()
        self.freeze = FreezeFrames()
        self.partikels = PartikelSysteem()
        self.cijfers   = SchadeCijferSysteem()
        self.flash     = HitFlash()
        self.dodge_trail_t = 0
        self.overgang_timer = 0
        self._pending_kamer = None
        self.kamer_intro_timer = 2 * FPS
        self.floor_portal_open = False
        # Sync level_mgr kamer type
        self.level_mgr.kamer = kamer["type"]
        # Vijanden
        self.vijanden = []
        if not kamer["gecleared"]:
            for type_, hp_mult in kamer["vijanden_config"]:
                self._spawn_vijand(type_, hp_mult, kamer["schade_mult"])
        else:
            self.floor_portal_open = (kamer["type"] == "baas")
        # Fontein
        self.fontein_pos = None
        self.fontein_gebruikt = kamer.get("fontein_gebruikt", False)
        if kamer["type"] == "rust":
            fx = KAART_B//2 * TILE + TILE//2
            fy = KAART_H//2 * TILE + TILE//2
            self.fontein_pos = (fx, fy)

    def _spawn_vijand(self, type_, hp_mult, schade_mult):
        sp = self.speler
        for _ in range(100):
            hoek = random.uniform(0, math.pi*2)
            d = random.randint(200, 420)
            wx = sp.x + math.cos(hoek)*d
            wy = sp.y + math.sin(hoek)*d
            if self.tile_op(int(wx//TILE), int(wy//TILE)) in (GRAS, PAD, STRUIK):
                self.vijanden.append(Vijand(wx, wy, type_, hp_mult, schade_mult))
                return

    def geblokkeerd(self, tx, ty): return self.tile_op(tx, ty) == BOOM

    def _check_deur_exit(self):
        sp = self.speler
        kamer = self.floor_graph[self.huidige_pos]
        my = KAART_H // 2; mx = KAART_B // 2
        speler_ty = sp.y / TILE; speler_tx = sp.x / TILE
        checks = [
            ("E", sp.x > (KAART_B-2)*TILE, abs(speler_ty - my) < 3),
            ("W", sp.x < 2*TILE,            abs(speler_ty - my) < 3),
            ("N", sp.y < 2*TILE,            abs(speler_tx - mx) < 3),
            ("S", sp.y > (KAART_H-2)*TILE,  abs(speler_tx - mx) < 3),
        ]
        for richting, pos_check, gang_check in checks:
            if richting not in kamer["deuren"]: continue
            if not (pos_check and gang_check): continue
            buur_pos = kamer["buren"][richting]
            buur = self.floor_graph[buur_pos]
            # Open als huidige kamer gecleared OF buur al bezocht (kan altijd terug)
            if kamer["gecleared"] or buur["bezocht"]:
                return richting, buur_pos
        return None

    def run(self):
        while True:
            self.clock.tick(FPS)
            self.tik += 1
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT: return "quit", self.save
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    sla_op(self.save); return "hub", self.save
            if self.freeze.update():
                self._teken(); continue
            # Overgangsanimatie
            if self.overgang_timer > 0:
                self.overgang_timer -= 1
                self._teken_overgang()
                if self.overgang_timer == 0:
                    if self._pending_kamer == "volgende_floor":
                        sla_op(self.save)
                        self.level_mgr.volgende_floor()
                        self._genereer_floor(eerste=False)
                    else:
                        pos, richting = self._pending_kamer
                        self._laad_kamer(pos, verplaatsing=richting)
                continue
            blok = pygame.mouse.get_pressed()[2] and self.speler._heeft_schild()
            self.speler.verwerk_events(events)
            # Camera smoothing
            self.cam_x += (self.speler.x - SCREEN_W/2 - self.cam_x) * 0.12
            self.cam_y += (self.speler.y - SCREEN_H/2 - self.cam_y) * 0.12
            cam_x = max(0, min(int(self.cam_x), self.W*TILE-SCREEN_W))
            cam_y = max(0, min(int(self.cam_y), self.H*TILE-SCREEN_H))
            keys = pygame.key.get_pressed()
            in_struik = self.speler.update(
                keys, pygame.mouse.get_pos(), cam_x, cam_y,
                self.geblokkeerd, self.tile_op, blok)
            if self.speler.dodge_t > 0:
                self.dodge_trail_t += 1
                if self.dodge_trail_t == 1: geluid.speel("dodge")
                if self.dodge_trail_t % 3 == 0:
                    self.partikels.dodge_spoor(self.speler.x, self.speler.y)
            else:
                self.dodge_trail_t = 0
            for (v, schade) in self.speler.zwaard_hits(self.vijanden):
                hoek = math.degrees(math.atan2(v.y-self.speler.y, v.x-self.speler.x))
                self.partikels.zwaard_vonken(v.x, v.y, hoek)
                self.freeze.start(2); self.shake.start(kracht=4, duur=8)
                self.cijfers.voeg_toe(v.x, v.y-20, schade)
                geluid.speel("zwaard_hit")
                dood = v.krijg_schade(schade, self.speler.x, self.speler.y)
                if dood:
                    kl = (220,60,220) if v.type=="baas" else (C_MELEE if v.type=="melee" else (200,130,50 if v.type=="wolf" else C_RANGED))
                    self.partikels.dood_explosie(v.x, v.y, kl)
                    self.shake.start(kracht=8 if v.type=="baas" else 6, duur=16)
                    geluid.speel("baas_dood" if v.type=="baas" else "vijand_dood")
                    goud = random.randint(GOLD_MIN, GOLD_MAX) * (5 if v.type=="baas" else 1)
                    xp   = XP_PER_VIJAND * (4 if v.type=="baas" else 1)
                    self.save["gold"] += goud
                    leveled = voeg_xp_toe(self.save, xp)
                    self.cijfers.voeg_toe(v.x, v.y-40, goud, is_goud=True)
                    self.cijfers.voeg_toe(v.x, v.y-20, xp,   is_xp=True)
                    if leveled:
                        lvl_tekst = "LEVEL UP! " + str(self.save["level"])
                        self.cijfers.voeg_toe(self.speler.x, self.speler.y-50,
                            lvl_tekst, kleur_override=True)
                        geluid.speel("level_up")
                    self.vijanden.remove(v)
            for (v, schade, kb) in self.speler.special_hits(self.vijanden):
                hoek = math.degrees(math.atan2(v.y-self.speler.y, v.x-self.speler.x))
                self.partikels.zwaard_vonken(v.x, v.y, hoek)
                self.freeze.start(3); self.shake.start(kracht=6, duur=10)
                self.cijfers.voeg_toe(v.x, v.y-20, schade)
                geluid.speel("zwaard_hit")
                dood = v.krijg_schade_knockback(schade, self.speler.x, self.speler.y, kb)
                if dood:
                    kl = (220,60,220) if v.type=="baas" else (C_MELEE if v.type=="melee" else (200,130,50 if v.type=="wolf" else C_RANGED))
                    self.partikels.dood_explosie(v.x, v.y, kl)
                    self.shake.start(kracht=8 if v.type=="baas" else 6, duur=16)
                    geluid.speel("baas_dood" if v.type=="baas" else "vijand_dood")
                    goud = random.randint(GOLD_MIN, GOLD_MAX) * (5 if v.type=="baas" else 1)
                    xp   = XP_PER_VIJAND * (4 if v.type=="baas" else 1)
                    self.save["gold"] += goud
                    leveled = voeg_xp_toe(self.save, xp)
                    self.cijfers.voeg_toe(v.x, v.y-40, goud, is_goud=True)
                    self.cijfers.voeg_toe(v.x, v.y-20, xp,   is_xp=True)
                    if leveled:
                        lvl_tekst = "LEVEL UP! " + str(self.save["level"])
                        self.cijfers.voeg_toe(self.speler.x, self.speler.y-50,
                            lvl_tekst, kleur_override=True)
                        geluid.speel("level_up")
                    self.vijanden.remove(v)
            # Kamer gecleared?
            kamer = self.floor_graph[self.huidige_pos]
            if not kamer["gecleared"] and len(self.vijanden) == 0:
                kamer["gecleared"] = True
                if kamer["type"] == "baas":
                    self.floor_portal_open = True
            # Floor portal (baas kamer)
            if self.floor_portal_open:
                px = KAART_B//2 * TILE; py = KAART_H//2 * TILE
                if math.hypot(self.speler.x-px, self.speler.y-py) < 32:
                    self._pending_kamer = "volgende_floor"
                    self.overgang_timer = 50
            # Fontein
            if self.fontein_pos and not self.fontein_gebruikt:
                fx, fy = self.fontein_pos
                if math.hypot(self.speler.x-fx, self.speler.y-fy) < 40:
                    herstel = self.speler.mhp * 0.5
                    self.speler.hp = min(self.speler.mhp, self.speler.hp + herstel)
                    self.fontein_gebruikt = True
                    kamer["fontein_gebruikt"] = True
                    self.cijfers.voeg_toe(fx, fy-30, f"+{int(herstel)} HP",
                        kleur_override=False, is_xp=True)
                    self.partikels.dood_explosie(fx, fy, (100,200,255))
                    geluid.speel("fontein")
            # Deur transitie
            if self.overgang_timer == 0:
                result = self._check_deur_exit()
                if result:
                    richting, buur_pos = result
                    self._pending_kamer = (buur_pos, richting)
                    self.overgang_timer = 35
            # Vijanden AI
            fh_sp = math.degrees(math.atan2(self.speler.fy, self.speler.fx))
            for v in self.vijanden:
                aanval = v.update(self.speler.x, self.speler.y, self.geblokkeerd,
                                  fh_sp, blok, self.speler.flinch_cd)
                if aanval:
                    if aanval[0] == "melee":
                        _, vx, vy, sch = aanval
                        geraakt = self.speler.krijg_schade(sch, vx, vy)
                        if geraakt:
                            hoek = math.degrees(math.atan2(self.speler.y-vy, self.speler.x-vx))
                            self.partikels.bloed_spat(self.speler.x, self.speler.y, hoek)
                            self.shake.start(kracht=8, duur=14)
                            self.freeze.start(3)
                            self.flash.start(kracht=60)
                            self.cijfers.voeg_toe(self.speler.x, self.speler.y-30,
                                sch, is_speler_schade=True)
                            geluid.speel("speler_geraakt")
                    elif aanval[0] == "pijl":
                        _, px, py, dx, dy, psch = aanval
                        self.pijlen.append(Pijl(px, py, dx, dy, psch))
            for p in self.pijlen[:]:
                if p.update(self.geblokkeerd):
                    self.pijlen.remove(p); continue
                dist = math.hypot(p.x-self.speler.x, p.y-self.speler.y)
                if dist < 18:
                    ph = math.degrees(math.atan2(p.dy, p.dx))
                    if blok and abs(hoek_diff(ph+180, fh_sp)) < 60:
                        self.partikels.zwaard_vonken(p.x, p.y, ph+180)
                        self.shake.start(kracht=3, duur=6)
                        geluid.speel("schild_blok")
                    else:
                        geraakt = self.speler.krijg_schade(p.schade, p.x-p.dx*5, p.y-p.dy*5)
                        if geraakt:
                            self.partikels.bloed_spat(self.speler.x, self.speler.y, ph+180)
                            self.shake.start(kracht=6, duur=10)
                            self.freeze.start(2)
                            self.flash.start(kracht=50)
                            self.cijfers.voeg_toe(self.speler.x, self.speler.y-30,
                                p.schade, is_speler_schade=True)
                            geluid.speel("speler_geraakt")
                    self.pijlen.remove(p); continue
                if dist > 700: self.pijlen.remove(p)
            # Vijanden-onderling collision — duw overlappende vijanden uit elkaar
            for i, v1 in enumerate(self.vijanden):
                for v2 in self.vijanden[i+1:]:
                    dvx2 = v1.x - v2.x; dvy2 = v1.y - v2.y
                    dist2 = math.hypot(dvx2, dvy2)
                    min_dist = v1.radius + v2.radius + 2
                    if dist2 < min_dist and dist2 > 0.1:
                        duw = (min_dist - dist2) / 2
                        nx = dvx2 / dist2; ny = dvy2 / dist2
                        v1.x += nx * duw; v1.y += ny * duw
                        v2.x -= nx * duw; v2.y -= ny * duw

            self.partikels.update()
            self.cijfers.update()
            geluid.update_geluid()
            if self.kamer_intro_timer > 0: self.kamer_intro_timer -= 1
            if in_struik and self.speler.dodge_t == 0: geluid.speel("struik")
            _keys = pygame.key.get_pressed()
            _beweegt = any([_keys[pygame.K_w], _keys[pygame.K_s],
                            _keys[pygame.K_a], _keys[pygame.K_d]])
            if _beweegt and not in_struik and self.speler.dodge_t == 0:
                geluid.speel("stap")
            if not self.speler.levend:
                sla_op(self.save)
                return self.game_over_scherm(), self.save
            self._teken()

    def _teken(self):
        blok = pygame.mouse.get_pressed()[2]
        sp   = self.speler
        cam_x = max(0, min(int(self.cam_x), self.W*TILE-SCREEN_W))
        cam_y = max(0, min(int(self.cam_y), self.H*TILE-SCREEN_H))
        ox, oy = self.shake.update()
        self.screen.fill(C_BG)
        stx2 = max(0, cam_x//TILE); sty2 = max(0, cam_y//TILE)
        etx  = min(stx2+SCREEN_W//TILE+2, self.W)
        ety  = min(sty2+SCREEN_H//TILE+2, self.H)
        for ty in range(sty2, ety):
            for tx in range(stx2, etx):
                teken_bos_tegel(self.screen, tx, ty,
                    tx*TILE-cam_x+ox, ty*TILE-cam_y+oy, self.tile_op)
        kamer = self.floor_graph[self.huidige_pos]
        for richting in kamer["deuren"]:
            buur_pos = kamer["buren"][richting]
            buur = self.floor_graph[buur_pos]
            deur_open = kamer["gecleared"] or buur["bezocht"]
            kl = (80,200,80) if deur_open else (180,60,60)
            if richting == "E": dx=(KAART_B-1)*TILE-cam_x+ox; dy=(KAART_H//2)*TILE-cam_y+oy
            elif richting == "W": dx=0-cam_x+ox+4; dy=(KAART_H//2)*TILE-cam_y+oy
            elif richting == "N": dx=(KAART_B//2)*TILE-cam_x+ox; dy=0-cam_y+oy+4
            else: dx=(KAART_B//2)*TILE-cam_x+ox; dy=(KAART_H-1)*TILE-cam_y+oy
            pygame.draw.circle(self.screen, kl, (dx, dy), 10)
            if buur["type"] == "rust":
                pygame.draw.circle(self.screen, (80,140,220), (dx,dy), 10)
            elif buur["type"] == "baas":
                pygame.draw.circle(self.screen, (220,60,220), (dx,dy), 10)
        if self.fontein_pos:
            fx = int(self.fontein_pos[0]-cam_x)+ox
            fy = int(self.fontein_pos[1]-cam_y)+oy
            kl = (80,140,220) if not self.fontein_gebruikt else (60,80,120)
            pygame.draw.circle(self.screen, kl, (fx,fy), 22)
            pygame.draw.circle(self.screen, (150,200,255), (fx,fy), 22, 3)
            ft = self.font_s.render("Fontein" if not self.fontein_gebruikt else "Leeg", True, (200,230,255))
            self.screen.blit(ft, (fx-ft.get_width()//2, fy-36))
        if self.floor_portal_open:
            px = KAART_B//2*TILE - cam_x + ox
            py = KAART_H//2*TILE - cam_y + oy
            kl_p = puls_kleur((100,60,220),(200,120,255), self.tik)
            pygame.draw.circle(self.screen, kl_p, (px, py), 28)
            pygame.draw.circle(self.screen, (220,180,255), (px, py), 28, 3)
            pt = self.font_s.render("VOLGENDE FLOOR", True, (220,180,255))
            self.screen.blit(pt, (px-pt.get_width()//2, py-42))
        for p in self.pijlen: p.teken(self.screen, cam_x-ox, cam_y-oy)
        self.partikels.teken(self.screen, cam_x-ox, cam_y-oy)
        for v in [v for v in self.vijanden if v.y <= sp.y]:
            v.teken(self.screen, cam_x-ox, cam_y-oy)
        sp.teken(self.screen, cam_x-ox, cam_y-oy, blok)
        for v in [v for v in self.vijanden if v.y > sp.y]:
            v.teken(self.screen, cam_x-ox, cam_y-oy)
        for (tx,ty,g) in sorted(self.bomen, key=lambda b:b[1]):
            wx=tx*TILE; wy=ty*TILE
            if (wx+g*TILE<cam_x or wx>cam_x+SCREEN_W or
                wy+g*TILE<cam_y or wy>cam_y+SCREEN_H+60): continue
            teken_boom_object(self.screen, tx, ty, g,
                self.pal_map.get((tx,ty), BOOM_PAL[0]), cam_x-ox, cam_y-oy)
        self.cijfers.teken(self.screen, cam_x, cam_y)
        self.flash.teken(self.screen)
        self._teken_minimap()
        self._teken_hud(blok)
        if self.kamer_intro_timer > 0:
            alpha = min(255, self.kamer_intro_timer * 6)
            kl = (255,100,100) if self.level_mgr.is_baas else (100,180,255) if self.level_mgr.is_rust else (220,220,100)
            kamer = self.floor_graph[self.huidige_pos]
            n_bezocht = sum(1 for k in self.floor_graph.values() if k["bezocht"])
            n_totaal  = len(self.floor_graph)
            t = self.font_g.render(self.level_mgr.omschrijving(n_bezocht, n_totaal), True, kl)
            t.set_alpha(alpha)
            self.screen.blit(t, (SCREEN_W//2-t.get_width()//2, SCREEN_H//2-40))
            if self.level_mgr.is_rust:
                s = self.font_m.render("Loop naar de fontein voor herstel", True, (150,200,255))
                s.set_alpha(alpha)
                self.screen.blit(s, (SCREEN_W//2-s.get_width()//2, SCREEN_H//2+20))
        pygame.display.flip()

    def _teken_minimap(self):
        if not self.floor_graph: return
        cel = 12; marge = 2
        # Bereken bounds van de graph
        xs = [p[0] for p in self.floor_graph]; ys = [p[1] for p in self.floor_graph]
        min_x=min(xs); min_y=min(ys)
        breedte=(max(xs)-min_x+1)*(cel+marge)+marge
        hoogte =(max(ys)-min_y+1)*(cel+marge)+marge
        ox = SCREEN_W - breedte - 10
        oy_m = 10
        # Achtergrond
        bg = pygame.Surface((breedte, hoogte), pygame.SRCALPHA)
        bg.fill((0,0,0,120))
        self.screen.blit(bg, (ox, oy_m))
        for (gx,gy), kamer in self.floor_graph.items():
            rx = ox + (gx-min_x)*(cel+marge)+marge
            ry = oy_m + (gy-min_y)*(cel+marge)+marge
            if not kamer["bezocht"]:
                kl = (60,60,60)
            elif kamer["type"] == "baas":
                kl = (180,40,180)
            elif kamer["type"] == "rust":
                kl = (60,100,200)
            elif kamer["gecleared"]:
                kl = (40,120,40)
            else:
                kl = (180,160,60)
            pygame.draw.rect(self.screen, kl, (rx,ry,cel,cel), border_radius=2)
            if (gx,gy) == self.huidige_pos:
                pygame.draw.rect(self.screen, (255,255,255), (rx,ry,cel,cel), 2, border_radius=2)

    def _teken_overgang(self):
        alpha = int(255 * (1 - self.overgang_timer/35))
        overlay = pygame.Surface((SCREEN_W, SCREEN_H)); overlay.fill((0,0,0))
        overlay.set_alpha(alpha)
        self.screen.blit(overlay, (0,0))
        pygame.display.flip()

    def _teken_hud(self, blok):
        sp = self.speler; s = self.save; bw = 200
        pygame.draw.rect(self.screen, (80,20,20),  (10,10,bw,18))
        pygame.draw.rect(self.screen, (220,60,60), (10,10,int(bw*sp.hp/sp.mhp),18))
        pygame.draw.rect(self.screen, (255,255,255),(10,10,bw,18),2)
        self.screen.blit(self.font_s.render(
            f"HP  {int(sp.hp)}/{int(sp.mhp)}", True,(255,255,255)),(14,11))
        pygame.draw.rect(self.screen, (20,60,20),  (10,32,bw,12))
        pygame.draw.rect(self.screen, (60,200,80), (10,32,int(bw*sp.sta/sp.msta),12))
        pygame.draw.rect(self.screen, (255,255,255),(10,32,bw,12),2)
        sta_kl = (150,150,150) if sp.sta_delay>0 else (255,255,255)
        self.screen.blit(self.font_s.render(
            f"ST  {int(sp.sta)}/{int(sp.msta)}", True, sta_kl),(14,33))
        if sp.dodge_t>0:    ds,dc="DODGE!",(100,220,255)
        elif sp.dodge_cd>0: ds,dc=f"cd({sp.dodge_cd})",(200,120,80)
        else:               ds,dc="klaar",(100,220,100)
        kamer = self.floor_graph[self.huidige_pos]
        n_bezocht = sum(1 for k in self.floor_graph.values() if k["bezocht"])
        n_totaal  = len(self.floor_graph)
        vijanden_over = len(self.vijanden)
        regels = [
            (f"Floor {self.level_mgr.floor_nr}  Kamer {n_bezocht}/{n_totaal}", (200,190,120)),
            ("Level " + str(s["level"]) + "  Gold: " + str(s["gold"]), (200,190,120)),
            (f"Dodge: {ds}", dc),
        ]
        if vijanden_over > 0 and not kamer["gecleared"]:
            regels.append((f"Vijanden: {vijanden_over}", (220,100,100)))
        if blok: regels.append(("SCHILD OMHOOG", (230,185,90)))
        for i,(t,c) in enumerate(regels):
            self.screen.blit(self.font_s.render(t,True,c),(10,50+i*20))
        et = self.font_s.render("ESC = terug naar kasteel", True,(140,140,140))
        self.screen.blit(et,(SCREEN_W-et.get_width()-130,10))

    def game_over_scherm(self):
        knop = pygame.Rect(SCREEN_W//2-130, SCREEN_H//2+60, 260, 50)
        while True:
            self.screen.fill((12,8,8))
            t = self.font_g.render("GAME OVER", True,(220,60,60))
            self.screen.blit(t,(SCREEN_W//2-t.get_width()//2, SCREEN_H//2-110))
            s = self.save
            for i,(r,kl) in enumerate([
                (f"Gevallen op floor {self.level_mgr.floor_nr}", (180,80,80)),
                ("Gold: " + str(s["gold"]) + "  |  Level: " + str(s["level"]), (160,160,160)),
                ("Je progressie is bewaard!", (200,200,120)),
            ]):
                rt = self.font_m.render(r,True,kl)
                self.screen.blit(rt,(SCREEN_W//2-rt.get_width()//2, SCREEN_H//2-30+i*30))
            mp = pygame.mouse.get_pos()
            kk = (70,130,70) if knop.collidepoint(mp) else (45,90,45)
            pygame.draw.rect(self.screen,kk,knop,border_radius=8)
            pygame.draw.rect(self.screen,(150,230,150),knop,2,border_radius=8)
            kt = self.font_m.render("Terug naar kasteel",True,(255,255,255))
            self.screen.blit(kt,(knop.centerx-kt.get_width()//2,knop.centery-kt.get_height()//2))
            pygame.display.flip()
            for e in pygame.event.get():
                if e.type==pygame.QUIT: return "quit"
                if e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE: return "quit"
                if e.type==pygame.MOUSEBUTTONDOWN and knop.collidepoint(e.pos):
                    return "hub"
