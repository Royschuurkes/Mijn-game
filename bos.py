# bos.py - Bos gevecht scene met level progressie
import math, random, pygame
from opslaan import *
from entiteiten import Speler, Vijand, Pijl, normalize, hoek_diff
from kaart import genereer_bos, teken_bos_tegel, teken_boom_object, BOOM_PAL
from juice import ScreenShake, FreezeFrames, PartikelSysteem, SchadeCijferSysteem, HitFlash
from level_manager import LevelManager
import geluid


# Pulserende kleur helper
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
        self.tik = 0  # globale teller voor animaties

        # Speler behoudt HP tussen kamers NIET — vers begin bij elke run
        self.speler = None
        self._laad_kamer(eerste=True)

    def _laad_kamer(self, eerste=False):
        """Genereer een nieuwe kamer en spawn vijanden."""
        random.seed()
        self.kaart, self.bomen, self.pal_map, stx, sty, self.tile_op = genereer_bos()
        self.W = 40; self.H = 40

        if eerste:
            self.speler = Speler(stx*TILE+TILE//2, sty*TILE+TILE//2, self.save)
        else:
            # Zet speler op spawnpunt, behoud HP/stats
            self.speler.x = float(stx*TILE+TILE//2)
            self.speler.y = float(sty*TILE+TILE//2)
            self.speler.dodge_t = self.speler.dodge_cd = 0
            self.speler.flinch_t = self.speler.flinch_cd = 0

        self.pijlen = []
        self.shake  = ScreenShake()
        self.freeze = FreezeFrames()
        self.partikels = PartikelSysteem()
        self.cijfers   = SchadeCijferSysteem()
        self.flash     = HitFlash()
        self.dodge_trail_t = 0
        self.exit_open = False
        self.overgang_timer = 0  # aftellen na exit betreden
        self.kamer_intro_timer = 3 * FPS  # intro tekst

        # Spawn vijanden op basis van level config
        self.vijanden = []
        cfg = self.level_mgr.vijanden_config
        for (type_, hp_mult) in cfg:
            self._spawn_vijand(type_, hp_mult, self.level_mgr.schade_mult)

        # Rustfontein positie (midden-links van kaart)
        def vind_vrije_plek(start_x, start_y, max_pogingen=50):
            """Zoek een vrije (niet-boom) tegel in de buurt van een startpunt."""
            for straal in range(1, max_pogingen):
                for dx in range(-straal, straal+1):
                    for dy in range(-straal, straal+1):
                        tx = int(start_x//TILE) + dx
                        ty = int(start_y//TILE) + dy
                        if self.tile_op(tx, ty) in (GRAS, PAD):
                            return tx*TILE+TILE//2, ty*TILE+TILE//2
            return start_x, start_y  # fallback

        # Rustfontein positie
        self.fontein_pos = None
        if self.level_mgr.is_rust:
            fx, fy = vind_vrije_plek((stx-6)*TILE+TILE//2, sty*TILE+TILE//2)
            self.fontein_pos = (fx, fy)
            self.fontein_gebruikt = False
            self.exit_open = True

        # Exit positie
        self.exit_x, self.exit_y = vind_vrije_plek((stx+8)*TILE+TILE//2, sty*TILE+TILE//2)

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

            # Overgangsanimatie naar volgende kamer
            if self.overgang_timer > 0:
                self.overgang_timer -= 1
                self._teken_overgang()
                if self.overgang_timer == 0:
                    self.level_mgr.volgende_level()
                    self._laad_kamer()
                continue

            blok = pygame.mouse.get_pressed()[2]
            self.speler.verwerk_events(events)

            cam_x = max(0, min(int(self.speler.x-SCREEN_W/2), self.W*TILE-SCREEN_W))
            cam_y = max(0, min(int(self.speler.y-SCREEN_H/2), self.H*TILE-SCREEN_H))

            keys = pygame.key.get_pressed()
            in_struik = self.speler.update(
                keys, pygame.mouse.get_pos(), cam_x, cam_y,
                self.geblokkeerd, self.tile_op, blok)

            # Dodge trail
            if self.speler.dodge_t > 0:
                self.dodge_trail_t += 1
                if self.dodge_trail_t == 1:
                    geluid.speel("dodge")
                if self.dodge_trail_t % 3 == 0:
                    self.partikels.dodge_spoor(self.speler.x, self.speler.y)
            else:
                self.dodge_trail_t = 0

            # Zwaard hits
            for (v, schade) in self.speler.zwaard_hits(self.vijanden):
                hoek = math.degrees(math.atan2(v.y-self.speler.y, v.x-self.speler.x))
                self.partikels.zwaard_vonken(v.x, v.y, hoek)
                self.freeze.start(2)
                self.shake.start(kracht=4, duur=8)
                self.cijfers.voeg_toe(v.x, v.y-20, schade)
                geluid.speel("zwaard_hit")
                dood = v.krijg_schade(schade, self.speler.x, self.speler.y)
                if dood:
                    kl = (220,60,220) if v.type=="baas" else (C_MELEE if v.type=="melee" else C_RANGED)
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
                        self.cijfers.voeg_toe(self.speler.x, self.speler.y-50,
                            f"LEVEL UP! {self.save['level']}", kleur_override=True)
                        geluid.speel("level_up")
                    self.vijanden.remove(v)

            # Check exit openen
            if not self.exit_open and len(self.vijanden) == 0:
                self.exit_open = True

            # Check fontein
            if self.fontein_pos and not self.fontein_gebruikt:
                fx, fy = self.fontein_pos
                if math.hypot(self.speler.x-fx, self.speler.y-fy) < 40:
                    herstel = self.speler.mhp * 0.5
                    self.speler.hp = min(self.speler.mhp, self.speler.hp + herstel)
                    self.fontein_gebruikt = True
                    self.cijfers.voeg_toe(fx, fy-30, f"+{int(herstel)} HP", kleur_override=False, is_xp=True)
                    self.partikels.dood_explosie(fx, fy, (100,200,255))
                    geluid.speel("fontein")

            # Check exit betreden
            if self.exit_open:
                dist_exit = math.hypot(self.speler.x-self.exit_x, self.speler.y-self.exit_y)
                if dist_exit < 32:
                    sla_op(self.save)
                    self.overgang_timer = 60

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

            # Pijlen
            for p in self.pijlen[:]:
                if p.update(self.geblokkeerd):
                    hoek = math.degrees(math.atan2(p.dy, p.dx))
                    self.partikels.zwaard_vonken(p.x, p.y, hoek+180)
                    self.pijlen.remove(p); continue
                dist = math.hypot(p.x-self.speler.x, p.y-self.speler.y)
                if dist < 18:
                    ph = math.degrees(math.atan2(p.dy, p.dx))
                    if blok and abs(hoek_diff(ph+180, fh_sp)) < 60:
                        self.partikels.zwaard_vonken(p.x, p.y, ph+180)
                        self.shake.start(kracht=3, duur=6)
                        geluid.speel("schild_blok")
                        geraakt = self.speler.krijg_schade(p.schade * 0.3, p.x-p.dx*5, p.y-p.dy*5)
                        if geraakt:
                            self.cijfers.voeg_toe(self.speler.x, self.speler.y-30,
                                p.schade * 0.3, is_speler_schade=True)
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

            self.partikels.update()
            self.cijfers.update()
            geluid.update_geluid()
            if self.kamer_intro_timer > 0: self.kamer_intro_timer -= 1

            # Struik geluid
            if in_struik and self.speler.dodge_t == 0:
                geluid.speel("struik")

            # Voetstap geluid (alleen als speler beweegt en niet in struik)
            sp = self.speler
            _keys = pygame.key.get_pressed()
            _beweegt = any([_keys[pygame.K_w], _keys[pygame.K_s],
                            _keys[pygame.K_a], _keys[pygame.K_d]])
            if _beweegt and not in_struik and sp.dodge_t == 0:
                geluid.speel("stap")

            if not self.speler.levend:
                sla_op(self.save)
                return self.game_over_scherm(), self.save

            self._teken()

    # ── Teken ──────────────────────────────────────────────────────────────────
    def _teken(self):
        blok = pygame.mouse.get_pressed()[2]
        sp   = self.speler
        cam_x = max(0, min(int(sp.x-SCREEN_W/2), self.W*TILE-SCREEN_W))
        cam_y = max(0, min(int(sp.y-SCREEN_H/2), self.H*TILE-SCREEN_H))
        ox, oy = self.shake.update()

        self.screen.fill(C_BG)

        stx2 = max(0, cam_x//TILE); sty2 = max(0, cam_y//TILE)
        etx  = min(stx2+SCREEN_W//TILE+2, self.W)
        ety  = min(sty2+SCREEN_H//TILE+2, self.H)
        for ty in range(sty2, ety):
            for tx in range(stx2, etx):
                teken_bos_tegel(self.screen, tx, ty,
                    tx*TILE-cam_x+ox, ty*TILE-cam_y+oy, self.tile_op)

        # Fontein
        if self.fontein_pos:
            fx = int(self.fontein_pos[0]-cam_x)+ox
            fy = int(self.fontein_pos[1]-cam_y)+oy
            kl = (80,140,220) if not self.fontein_gebruikt else (60,80,120)
            pygame.draw.circle(self.screen, kl, (fx,fy), 22)
            pygame.draw.circle(self.screen, (150,200,255), (fx,fy), 22, 3)
            ft = self.font_s.render("Fontein" if not self.fontein_gebruikt else "Leeg", True, (200,230,255))
            self.screen.blit(ft, (fx-ft.get_width()//2, fy-36))

        # Exit portal
        if self.exit_open:
            ex = int(self.exit_x-cam_x)+ox
            ey = int(self.exit_y-cam_y)+oy
            kl_p = puls_kleur((40,200,80),(150,255,150), self.tik)
            pygame.draw.circle(self.screen, kl_p, (ex,ey), 24)
            pygame.draw.circle(self.screen, (200,255,200), (ex,ey), 24, 3)
            pt = self.font_s.render("VOLGENDE KAMER", True, (180,255,180))
            self.screen.blit(pt, (ex-pt.get_width()//2, ey-38))
        else:
            if len(self.vijanden) > 0:
                ex = int(self.exit_x-cam_x)+ox
                ey = int(self.exit_y-cam_y)+oy
                pygame.draw.circle(self.screen, (100,40,40), (ex,ey), 24)
                pygame.draw.circle(self.screen, (160,60,60), (ex,ey), 24, 3)
                lt = self.font_s.render(f"Versla alle vijanden ({len(self.vijanden)})", True, (200,100,100))
                self.screen.blit(lt, (ex-lt.get_width()//2, ey-38))

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
        self._teken_hud(blok)

        # Kamer intro tekst
        if self.kamer_intro_timer > 0:
            alpha = min(255, self.kamer_intro_timer * 6)
            kl = (255,100,100) if self.level_mgr.is_baas else (220,220,100)
            t = self.font_g.render(self.level_mgr.omschrijving(), True, kl)
            t.set_alpha(alpha)
            self.screen.blit(t, (SCREEN_W//2-t.get_width()//2, SCREEN_H//2-40))
            if self.level_mgr.is_rust:
                s = self.font_m.render("Loop naar de fontein voor herstel", True, (150,200,255))
                s.set_alpha(alpha)
                self.screen.blit(s, (SCREEN_W//2-s.get_width()//2, SCREEN_H//2+20))

        pygame.display.flip()

    def _teken_overgang(self):
        """Fade to black tussen kamers."""
        alpha = int(255 * (1 - self.overgang_timer/60))
        overlay = pygame.Surface((SCREEN_W, SCREEN_H))
        overlay.fill((0,0,0))
        overlay.set_alpha(alpha)
        self.screen.blit(overlay, (0,0))
        t = self.font_m.render(f"Kamer {self.level_mgr.level_nr+1}...", True, (200,200,200))
        t.set_alpha(alpha)
        self.screen.blit(t, (SCREEN_W//2-t.get_width()//2, SCREEN_H//2))
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

        regels = [
            (f"Kamer: {self.level_mgr.level_nr}  {self.level_mgr.kamer.upper()}", (200,190,120)),
            (f"Level {s['level']}  Gold: {s['gold']}", (200,190,120)),
            (f"Dodge: {ds}", dc),
        ]
        if blok: regels.append(("SCHILD OMHOOG", (230,185,90)))
        for i,(t,c) in enumerate(regels):
            self.screen.blit(self.font_s.render(t,True,c),(10,50+i*20))

        et = self.font_s.render("ESC = terug naar kasteel", True,(140,140,140))
        self.screen.blit(et,(SCREEN_W-et.get_width()-10,10))

    def game_over_scherm(self):
        knop = pygame.Rect(SCREEN_W//2-130, SCREEN_H//2+60, 260, 50)
        while True:
            self.screen.fill((12,8,8))
            t = self.font_g.render("GAME OVER", True,(220,60,60))
            self.screen.blit(t,(SCREEN_W//2-t.get_width()//2, SCREEN_H//2-110))
            s = self.save
            for i,(r,kl) in enumerate([
                (f"Gevallen in kamer {self.level_mgr.level_nr}", (180,80,80)),
                (f"Gold: {s['gold']}  |  Level: {s['level']}", (160,160,160)),
                (f"Ability points: {s['ability_points']}", (160,160,160)),
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
