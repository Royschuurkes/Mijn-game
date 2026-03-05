# bos.py - Bos gevecht scene met floor/kamer systeem (BoI-stijl)
import math, random, pygame
from opslaan import *
from entiteiten import Speler, Vijand, BaasVijand, Pijl, normalize, hoek_diff
from kaart import (genereer_bos, genereer_arena, teken_bos_tegel, teken_boom_object,
                   BOOM_PAL, KAART_B, KAART_H)
from juice import ScreenShake, FreezeFrames, PartikelSysteem, SchadeCijferSysteem, HitFlash
from level_manager import LevelManager, genereer_floor_graph, TEGENOVER
from items import ITEMS, RARITY_KLEUR, RARITY_NAAM, kies_items
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
            if kamer["type"] == "baas":
                kd = genereer_arena(kamer["deuren"])
            else:
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
        # Vijanden — spawn per groep geclusterd
        self.vijanden  = []
        self.baas      = None   # apart bijhouden voor speciale behandeling
        self.kampvuur_posities = []
        if not kamer["gecleared"]:
            for groep in kamer["vijanden_config"]:
                type_, aantal, hp_mult = groep
                if type_ == "baas":
                    # Baas spawnt altijd in het midden
                    cx = KAART_B//2 * TILE + TILE//2
                    cy = KAART_H//2 * TILE + TILE//2
                    self.baas = BaasVijand(cx, cy, schade_mult=hp_mult)
                else:
                    self._spawn_groep(type_, aantal, hp_mult, kamer["schade_mult"])
        else:
            self.floor_portal_open = (kamer["type"] == "baas")
        # Fontein + item pedestal
        self.fontein_pos    = None
        self.fontein_gebruikt = kamer.get("fontein_gebruikt", False)
        self.item_pedestal_pos = None
        self.item_keuze_actief = False
        self.item_keuze_opties = []
        if kamer["type"] == "rust":
            fx = KAART_B//2 * TILE + TILE//2
            fy = KAART_H//2 * TILE + TILE//2
            self.fontein_pos = (fx, fy)
            if not kamer.get("item_gepakt", False):
                # Pedestal links van de fontein
                self.item_pedestal_pos = (fx - 100, fy)

    def _spawn_groep(self, type_, aantal, hp_mult, schade_mult):
        """Spawn een groep vijanden geclusterd op één locatie."""
        sp = self.speler
        # Zoek een vrije centerpositie ver genoeg van de speler
        cx, cy = sp.x, sp.y
        for _ in range(200):
            hoek = random.uniform(0, math.pi*2)
            d    = random.randint(280, 460)
            tx   = sp.x + math.cos(hoek)*d
            ty   = sp.y + math.sin(hoek)*d
            if self.tile_op(int(tx//TILE), int(ty//TILE)) in (GRAS, PAD, STRUIK):
                cx, cy = tx, ty
                break

        # Kampvuur positie voor archers
        if type_ == "ranged" and aantal >= 2:
            self.kampvuur_posities.append((cx, cy))

        # Groep ID voor gedeelde aggro
        groep_id = random.randint(1000, 9999)

        # Spawn individuele vijanden rondom het center
        WOLF_OFFSETS  = [(0,0), (-28, 16), (28, 16), (-20,-20), (20,-20)]
        RANGE_OFFSETS = [(0,0), (-32, 0),  (32, 0),  (0,-36),   (0, 36)]
        offsets = WOLF_OFFSETS if type_ == "wolf" else RANGE_OFFSETS

        for i in range(aantal):
            ox, oy = offsets[i % len(offsets)]
            for _ in range(50):
                wx = cx + ox + random.uniform(-8, 8)
                wy = cy + oy + random.uniform(-8, 8)
                if self.tile_op(int(wx//TILE), int(wy//TILE)) in (GRAS, PAD, STRUIK):
                    v = Vijand(wx, wy, type_, hp_mult, schade_mult)
                    v.groep_id = groep_id
                    # Stagger acd zodat ze niet synchroon aanvallen
                    v.acd = random.randint(0, 60)
                    self.vijanden.append(v)
                    break

    def geblokkeerd(self, tx, ty): return self.tile_op(tx, ty) == BOOM

    def _check_deur_exit(self):
        sp = self.speler
        kamer = self.floor_graph[self.huidige_pos]
        # Deuren op slot zolang vijanden leven
        if not kamer["gecleared"]:
            return None
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
                    self._reset_run_items()
                    sla_op(self.save); return "hub", self.save
                if e.type == pygame.KEYDOWN and e.key == pygame.K_q:
                    self._gebruik_actief_item()
                # Item keuze scherm: klik op 1/2/3 of kaart
                if self.item_keuze_actief and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    self._verwerk_item_klik(e.pos)
                if self.item_keuze_actief and e.type == pygame.KEYDOWN and e.key in (
                        pygame.K_1, pygame.K_2, pygame.K_3):
                    idx = e.key - pygame.K_1
                    if idx < len(self.item_keuze_opties):
                        self._pak_item(self.item_keuze_opties[idx])
            if self.freeze.update():
                self._teken(); continue
            # Item keuze scherm — game gepauzeerd, overlay wordt in _teken getekend
            if self.item_keuze_actief:
                self._teken()
                continue
            # Overgangsanimatie
            if self.overgang_timer > 0:
                self.overgang_timer -= 1
                self._teken_overgang()
                if self.overgang_timer == 0:
                    if self._pending_kamer == "volgende_floor":
                        # Bijhouden hoogste floor ooit bereikt
                        huidige = self.level_mgr.floor_nr
                        if huidige > self.save.get("hoogste_floor", 0):
                            self.save["hoogste_floor"] = huidige
                        sla_op(self.save)
                        self.level_mgr.volgende_floor()
                        self._genereer_floor(eerste=False)
                    else:
                        pos, richting = self._pending_kamer
                        self._laad_kamer(pos, verplaatsing=richting)
                continue
            blok = pygame.mouse.get_pressed()[2] and self.speler._heeft_schild() and not self.speler.schild_geblokt
            self.speler.verwerk_events(events, blok)
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
            baas_lijst = [self.baas] if self.baas else []
            for (v, schade, kb_nx, kb_ny) in self.speler.zwaard_hits(self.vijanden + baas_lijst):
                hoek = math.degrees(math.atan2(v.y-self.speler.y, v.x-self.speler.x))
                self.partikels.zwaard_vonken(v.x, v.y, hoek)
                is_finisher = (self.speler.combo_stap == 3 and not self.speler.is_dash_strike)
                if is_finisher:
                    self.freeze.start(5); self.shake.start(kracht=9, duur=14)
                    self.flash.start(kracht=40)
                    # Ring burst partikel
                    self.partikels.dood_explosie(v.x, v.y, (255,200,50))
                else:
                    self.freeze.start(2); self.shake.start(kracht=4, duur=8)
                self.cijfers.voeg_toe(v.x, v.y-20, schade)
                geluid.speel("zwaard_hit")
                # Burning kans bij fire_damage of fire_potion
                heeft_vuur = self.speler.heeft_item("fire_damage") or self.speler.heeft_actief_effect("fire_potion")
                if heeft_vuur and random.random() < 0.30 and v.burning_t == 0:
                    v.burning_t    = 360   # 6 sec
                    v.burning_tick = 120
                dood = v.krijg_schade_swing(schade, kb_nx, kb_ny)
                if dood:
                    kl = (220,60,220) if v.type=="baas" else (200,130,50) if v.type=="wolf" else C_RANGED
                    self.partikels.dood_explosie(v.x, v.y, kl)
                    self.shake.start(kracht=8 if v.type=="baas" else 6, duur=16)
                    geluid.speel("baas_dood" if v.type=="baas" else "vijand_dood")
                    # Bloodthirst: heal bij kill
                    if self.speler.heeft_item("bloodthirst"):
                        heal = 8
                        self.speler.hp = min(self.speler.mhp, self.speler.hp + heal)
                        self.cijfers.voeg_toe(self.speler.x, self.speler.y-40, f"+{heal} HP",
                            kleur_override=True, kl_override=(80,220,120))
                    self.vijanden.remove(v)
            for (v, schade, kb) in self.speler.special_hits(self.vijanden + baas_lijst):
                hoek = math.degrees(math.atan2(v.y-self.speler.y, v.x-self.speler.x))
                self.partikels.zwaard_vonken(v.x, v.y, hoek)
                self.freeze.start(3); self.shake.start(kracht=6, duur=10)
                self.cijfers.voeg_toe(v.x, v.y-20, schade)
                geluid.speel("zwaard_hit")
                dood = v.krijg_schade_knockback(schade, self.speler.x, self.speler.y, kb)
                if dood:
                    kl = (220,60,220) if v.type=="baas" else (200,130,50) if v.type=="wolf" else C_RANGED
                    self.partikels.dood_explosie(v.x, v.y, kl)
                    self.shake.start(kracht=8 if v.type=="baas" else 6, duur=16)
                    geluid.speel("baas_dood" if v.type=="baas" else "vijand_dood")
                    self.vijanden.remove(v)
            # Kamer gecleared? (baas heeft eigen check hierboven)
            kamer = self.floor_graph[self.huidige_pos]
            if not kamer["gecleared"] and len(self.vijanden) == 0 and self.baas is None:
                kamer["gecleared"] = True
                if kamer["type"] == "baas":
                    self.floor_portal_open = True
                else:
                    # Visuele bevestiging — gouden splash in het midden
                    mx = KAART_B//2 * TILE + TILE//2
                    my = KAART_H//2 * TILE + TILE//2
                    self.partikels.dood_explosie(mx, my, (255, 210, 60))
                    self.cijfers.voeg_toe(mx, my - 40, "KAMER GECLEARED",
                        kleur_override=True, kl_override=(220, 190, 60))
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
                    self.cijfers.voeg_toe(fx, fy-30, f"+{int(herstel)} HP", kleur_override=True, kl_override=(80,220,120))
                    self.partikels.dood_explosie(fx, fy, (100,200,255))
                    geluid.speel("fontein")
            # Item pedestal
            if self.item_pedestal_pos and not self.item_keuze_actief:
                px, py = self.item_pedestal_pos
                if math.hypot(self.speler.x-px, self.speler.y-py) < 45:
                    self.item_keuze_opties  = kies_items(3,
                        self.save.get("items", []),
                        self.save.get("item_charges", {}))
                    self.item_keuze_actief  = True
                    self.item_pedestal_pos  = None  # verberg pedestal
            # Deur transitie
            if self.overgang_timer == 0:
                result = self._check_deur_exit()
                if result:
                    richting, buur_pos = result
                    self._pending_kamer = (buur_pos, richting)
                    self.overgang_timer = 35
            # Gedeelde aggro: als één groepsgenoot aggro krijgt, wakker de rest
            for v in self.vijanden:
                if v.aggro and v.groep_id:
                    for v2 in self.vijanden:
                        if v2.groep_id == v.groep_id and not v2.aggro:
                            d = math.hypot(v2.x-v.x, v2.y-v.y)
                            if d < 200:
                                v2.acd = max(v2.acd, random.randint(20, 70))
                                v2.aggro = True

            # Vijanden AI
            fh_sp = math.degrees(math.atan2(self.speler.fy, self.speler.fx))
            blok_actief = blok and not self.speler.schild_geblokt

            # Baas AI
            if self.baas:
                aanval, fase2_trigger = self.baas.update(
                    self.speler.x, self.speler.y, self.geblokkeerd,
                    fh_sp, blok_actief, self.speler.flinch_cd)
                if fase2_trigger:
                    self.shake.start(kracht=12, duur=30)
                    self.freeze.start(8)
                    self.flash.start(kracht=120)
                    geluid.speel("fase2")
                if aanval:
                    if aanval[0] == "melee":
                        _, vx, vy, sch = aanval
                        rvn = math.degrees(math.atan2(vy-self.speler.y, vx-self.speler.x))
                        if blok_actief and abs(hoek_diff(rvn, fh_sp)) < 70:
                            geblokt = self.speler.verwerk_blok(vx, vy, stamina_kosten=STAMINA_SCHILD * 1.5)
                            self.partikels.zwaard_vonken(self.speler.x, self.speler.y, rvn)
                            if geblokt:
                                self.shake.start(kracht=8, duur=12)
                                self.freeze.start(4)
                                geluid.speel("schild_blok")
                                self.speler.krijg_schade(sch * BLOK_SCHADE_DOOR, vx, vy)
                            else:
                                self.speler.krijg_schade(sch, vx, vy)
                                self.shake.start(kracht=12, duur=20)
                                self.freeze.start(5)
                                self.flash.start(kracht=100)
                                geluid.speel("speler_geraakt")
                        else:
                            geraakt = self.speler.krijg_schade(sch, vx, vy)
                            if geraakt:
                                self.partikels.bloed_spat(self.speler.x, self.speler.y, rvn)
                                self.shake.start(kracht=8, duur=12)
                                self.freeze.start(3)
                                self.flash.start(kracht=80)
                                geluid.speel("speler_geraakt")
                    elif aanval[0] == "charge":
                        # Charge niet blockbaar
                        _, vx, vy, sch = aanval
                        geraakt = self.speler.krijg_schade(sch, vx, vy)
                        if geraakt:
                            self.partikels.bloed_spat(self.speler.x, self.speler.y, 0)
                            self.shake.start(kracht=14, duur=22)
                            self.freeze.start(6)
                            self.flash.start(kracht=120)
                            geluid.speel("speler_geraakt")
                # Stamp shockwave schade
                for ring in self.baas.stamp_ringen:
                    rx = ring["r"]
                    speler_dist = math.hypot(self.speler.x - self.baas.x,
                                             self.speler.y - self.baas.y)
                    if abs(speler_dist - rx) < 18 and self.speler.flinch_cd <= 0:
                        geraakt = self.speler.krijg_schade(
                            self.baas.STAMP_SCHADE * self.baas.schade_mult,
                            self.baas.x, self.baas.y)
                        if geraakt:
                            self.shake.start(kracht=10, duur=16)
                            self.flash.start(kracht=90)
                            geluid.speel("speler_geraakt")
                # Baas dood?
                if self.baas.hp <= 0:
                    self.partikels.dood_explosie(self.baas.x, self.baas.y, (220,60,220))
                    self.partikels.dood_explosie(self.baas.x, self.baas.y, (255,200,50))
                    self.shake.start(kracht=16, duur=40)
                    self.freeze.start(12)
                    self.flash.start(kracht=180)
                    geluid.speel("baas_dood")
                    self.baas = None
                    kamer = self.floor_graph[self.huidige_pos]
                    kamer["gecleared"] = True
                    self.floor_portal_open = True

            for v in self.vijanden:
                aanval = v.update(self.speler.x, self.speler.y, self.geblokkeerd,
                                  fh_sp, blok_actief, self.speler.flinch_cd)
                if aanval:
                    if aanval[0] == "melee":
                        _, vx, vy, sch = aanval
                        # rvn = richting van aanval naar speler; speler moet NAAR vijand kijken
                        rvn = math.degrees(math.atan2(vy-self.speler.y, vx-self.speler.x))
                        if blok_actief and abs(hoek_diff(rvn, fh_sp)) < 70:
                            geblokt = self.speler.verwerk_blok(vx, vy)
                            self.partikels.zwaard_vonken(self.speler.x, self.speler.y, rvn)
                            if geblokt:
                                self.shake.start(kracht=6, duur=10)
                                self.freeze.start(3)
                                geluid.speel("schild_blok")
                                # 10% schade lekt door
                                self.speler.krijg_schade(sch * BLOK_SCHADE_DOOR, vx, vy)
                            else:
                                # Guard break — volledige schade
                                self.speler.krijg_schade(sch, vx, vy)
                                self.shake.start(kracht=10, duur=18)
                                self.freeze.start(4)
                                self.flash.start(kracht=80)
                                self.cijfers.voeg_toe(self.speler.x, self.speler.y-30,
                                    "GUARD BREAK", kleur_override=True)
                                geluid.speel("speler_geraakt")
                        else:
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
                    if blok_actief and abs(hoek_diff(ph+180, fh_sp)) < 60:
                        geblokt = self.speler.verwerk_blok(p.x-p.dx*5, p.y-p.dy*5,
                                                           stamina_kosten=STAMINA_SCHILD_PIJL)
                        self.partikels.zwaard_vonken(p.x, p.y, ph+180)
                        if geblokt:
                            self.shake.start(kracht=4, duur=7)
                            geluid.speel("schild_blok")
                            self.speler.krijg_schade(p.schade * BLOK_SCHADE_DOOR, p.x-p.dx*5, p.y-p.dy*5)
                        else:
                            self.speler.krijg_schade(p.schade, p.x-p.dx*5, p.y-p.dy*5)
                            self.shake.start(kracht=10, duur=18)
                            self.freeze.start(4)
                            self.flash.start(kracht=80)
                            self.cijfers.voeg_toe(self.speler.x, self.speler.y-30,
                                "GUARD BREAK", kleur_override=True)
                            geluid.speel("speler_geraakt")
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
            deur_open = kamer["gecleared"]
            if not deur_open:
                kl = (160, 40, 40)  # rood slot
            elif buur["type"] == "rust":
                kl = (60, 100, 200)
            elif buur["type"] == "baas":
                kl = (180, 40, 180)
            else:
                kl = (80, 200, 80)
            if richting == "E": dx=(KAART_B-1)*TILE-cam_x+ox; dy=(KAART_H//2)*TILE-cam_y+oy
            elif richting == "W": dx=0-cam_x+ox+4; dy=(KAART_H//2)*TILE-cam_y+oy
            elif richting == "N": dx=(KAART_B//2)*TILE-cam_x+ox; dy=0-cam_y+oy+4
            else: dx=(KAART_B//2)*TILE-cam_x+ox; dy=(KAART_H-1)*TILE-cam_y+oy
            pygame.draw.circle(self.screen, kl, (dx, dy), 10)
            # Slot-icoon als deur dicht is
            if not deur_open:
                pygame.draw.circle(self.screen, (220, 60, 60), (dx, dy), 10, 2)
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
        # Kampvuren tekenen
        for kx, ky in getattr(self, 'kampvuur_posities', []):
            sx = int(kx-cam_x)+ox; sy = int(ky-cam_y)+oy
            puls = 0.7 + 0.3*math.sin(self.tik * 0.18)
            r_vuur = int(12 * puls)
            vuur_surf = pygame.Surface((r_vuur*2+4, r_vuur*2+4), pygame.SRCALPHA)
            pygame.draw.circle(vuur_surf, (255, int(140*puls), 20, 160), (r_vuur+2, r_vuur+2), r_vuur)
            pygame.draw.circle(vuur_surf, (255, 220, 80, 120), (r_vuur+2, r_vuur+2), max(2, r_vuur-4))
            self.screen.blit(vuur_surf, (sx-r_vuur-2, sy-r_vuur-2))
        # Item pedestal
        if self.item_pedestal_pos:
            px = int(self.item_pedestal_pos[0]-cam_x)+ox
            py = int(self.item_pedestal_pos[1]-cam_y)+oy
            puls_kl = puls_kleur((120,90,30),(255,210,80), self.tik, snelheid=0.12)
            pygame.draw.rect(self.screen, (60,50,35), (px-18,py-8,36,16), border_radius=4)
            pygame.draw.rect(self.screen, (100,80,40),(px-18,py-8,36,16), 2, border_radius=4)
            pygame.draw.circle(self.screen, puls_kl, (px, py-18), 12)
            pygame.draw.circle(self.screen, (255,240,150), (px, py-18), 12, 2)
            hint = self.font_s.render("Loopnaartoe", True, (200,180,100))
            self.screen.blit(hint, (px - hint.get_width()//2, py - 40))
        self.partikels.teken(self.screen, cam_x-ox, cam_y-oy)
        alle_entiteiten = list(self.vijanden) + ([self.baas] if self.baas else [])
        for v in [v for v in alle_entiteiten if v.y <= sp.y]:
            v.teken(self.screen, cam_x-ox, cam_y-oy)
        sp.teken(self.screen, cam_x-ox, cam_y-oy, blok)
        for v in [v for v in alle_entiteiten if v.y > sp.y]:
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
        if self.item_keuze_actief:
            self._teken_item_keuze()
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
        sta_kl_bar = (220,60,60) if self.speler.schild_geblokt else (60,200,80)
        pygame.draw.rect(self.screen, sta_kl_bar, (10,32,int(bw*sp.sta/sp.msta),12))
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
            (f"Dodge: {ds}", dc),
        ]
        if vijanden_over > 0 and not kamer["gecleared"]:
            regels.append((f"Vijanden: {vijanden_over}", (220,100,100)))
        if blok: regels.append(("SCHILD OMHOOG", (230,185,90)))
        for i,(t,c) in enumerate(regels):
            self.screen.blit(self.font_s.render(t,True,c),(10,50+i*20))
        et = self.font_s.render("ESC = terug naar kasteel", True,(140,140,140))
        self.screen.blit(et,(SCREEN_W-et.get_width()-130,10))

        # Baas HP balk — groot, bovenaan
        if self.baas:
            bw = 340; bh = 18
            bx = SCREEN_W//2 - bw//2; by = 10
            ratio = max(0, self.baas.hp / self.baas.max_hp)
            pygame.draw.rect(self.screen, (50,15,15),    (bx,   by,   bw,   bh), border_radius=4)
            kl_hp = (255,80,20) if self.baas.fase2 else (200,50,50)
            pygame.draw.rect(self.screen, kl_hp,          (bx,   by,   int(bw*ratio), bh), border_radius=4)
            # Fase 2 markering bij 50%
            pygame.draw.line(self.screen, (200,180,150), (bx+bw//2, by), (bx+bw//2, by+bh), 2)
            pygame.draw.rect(self.screen, (200,160,100), (bx,   by,   bw,   bh), 2, border_radius=4)
            naam_t = self.font_s.render("De Bosridder", True, (220,190,140))
            self.screen.blit(naam_t, (SCREEN_W//2 - naam_t.get_width()//2, by + bh + 3))

        # Item HUD — rechtsonder
        items      = self.save.get("items", [])
        charges    = self.save.get("item_charges", {})
        effecten   = self.save.get("actieve_effecten", {})
        alle_items = [(k, None)       for k in items] + \
                     [(k, charges[k]) for k in charges if charges[k] > 0]
        if alle_items:
            ix = SCREEN_W - 10
            for key, ch in reversed(alle_items):
                item = ITEMS[key]
                # Achtergrond
                ix -= 38
                is_actief = effecten.get(key.replace("_potion",""), 0) > 0 or \
                            effecten.get("fire_potion" if "fire" in key else "", 0) > 0
                rand_kl = (255,220,80) if is_actief else item["kleur"]
                pygame.draw.circle(self.screen, (30,25,20), (ix+14, SCREEN_H-30), 16)
                pygame.draw.circle(self.screen, item["kleur"], (ix+14, SCREEN_H-30), 14)
                pygame.draw.circle(self.screen, rand_kl, (ix+14, SCREEN_H-30), 14, 2)
                if ch is not None:
                    ct = self.font_s.render(str(ch), True, (255,255,255))
                    self.screen.blit(ct, (ix+14-ct.get_width()//2, SCREEN_H-20))
        if alle_items:
            qt = self.font_s.render("Q = gebruik item", True, (130,130,130))
            self.screen.blit(qt, (SCREEN_W - qt.get_width() - 10, SCREEN_H - 55))

    def _reset_run_items(self):
        """Items resetten aan het einde van een run (game over of terug naar kasteel)."""
        self.save["items"]            = []
        self.save["item_charges"]     = {}
        self.save["actieve_effecten"] = {"invis": 0, "fire_potion": 0}

    def _gebruik_actief_item(self):
        """Gebruik het eerste beschikbare actieve item (Q toets)."""
        charges = self.save.get("item_charges", {})
        effecten = self.save.setdefault("actieve_effecten", {"invis": 0, "fire_potion": 0})
        # Prioriteit: invis potion > health potion > fire potion
        volgorde = ["invis_potion", "health_potion", "fire_potion"]
        for key in volgorde:
            if charges.get(key, 0) > 0:
                item = ITEMS[key]
                if key == "invis_potion":
                    effecten["invis"] = item["duur"]
                    charges[key] -= 1
                    self.cijfers.voeg_toe(self.speler.x, self.speler.y-50,
                        "ONKWETSBAAR!", kleur_override=True, kl_override=(100,200,255))
                elif key == "health_potion":
                    heal = item["heal"]
                    self.speler.hp = min(self.speler.mhp, self.speler.hp + heal)
                    charges[key] -= 1
                    self.cijfers.voeg_toe(self.speler.x, self.speler.y-50,
                        f"+{heal} HP", kleur_override=True, kl_override=(80,220,120))
                elif key == "fire_potion":
                    effecten["fire_potion"] = item["duur"]
                    charges[key] -= 1
                    self.cijfers.voeg_toe(self.speler.x, self.speler.y-50,
                        "VUUR ACTIEF!", kleur_override=True, kl_override=(255,120,30))
                if charges[key] <= 0:
                    del charges[key]
                return

    def _pak_item(self, key):
        """Voeg gekozen item toe aan save."""
        item = ITEMS[key]
        self.save.setdefault("items", [])
        self.save.setdefault("item_charges", {})
        if item["type"] == "passief":
            if key not in self.save["items"]:
                self.save["items"].append(key)
        else:
            # Actief: charges ophogen
            bestaand = self.save["item_charges"].get(key, 0)
            self.save["item_charges"][key] = bestaand + item["charges"]
        # Markeer kamer als gepakt
        kamer = self.floor_graph[self.huidige_pos]
        kamer["item_gepakt"] = True
        self.item_keuze_actief = False
        self.item_keuze_opties = []

    def _verwerk_item_klik(self, pos):
        kaarten = self._item_keuze_rects()
        for i, rect in enumerate(kaarten):
            if rect.collidepoint(pos) and i < len(self.item_keuze_opties):
                self._pak_item(self.item_keuze_opties[i])
                return

    def _item_keuze_rects(self):
        n = len(self.item_keuze_opties)
        breedte = 180; hoogte = 240; marge = 20
        totaal = n * breedte + (n-1) * marge
        sx = SCREEN_W//2 - totaal//2
        sy = SCREEN_H//2 - hoogte//2
        return [pygame.Rect(sx + i*(breedte+marge), sy, breedte, hoogte) for i in range(n)]

    def _teken_item_keuze(self):
        """Overlay met 3 item kaarten om uit te kiezen."""
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        t = self.font_g.render("Kies een item", True, (220, 200, 120))
        self.screen.blit(t, (SCREEN_W//2 - t.get_width()//2, 80))
        hint = self.font_s.render("Klik of druk 1 / 2 / 3", True, (140, 140, 140))
        self.screen.blit(hint, (SCREEN_W//2 - hint.get_width()//2, 115))
        rects = self._item_keuze_rects()
        mp = pygame.mouse.get_pos()
        for i, key in enumerate(self.item_keuze_opties):
            item  = ITEMS[key]
            rect  = rects[i]
            hover = rect.collidepoint(mp)
            r_kl  = item["kleur"] if hover else item["kleur_dim"]
            bg_kl = (40, 35, 30) if hover else (25, 22, 18)
            pygame.draw.rect(self.screen, bg_kl,   rect, border_radius=10)
            pygame.draw.rect(self.screen, r_kl,    rect, 2 if not hover else 3, border_radius=10)
            # Rarity badge
            rar_kl = RARITY_KLEUR[item["rarity"]]
            rar_t  = self.font_s.render(RARITY_NAAM[item["rarity"]], True, rar_kl)
            self.screen.blit(rar_t, (rect.x + 10, rect.y + 10))
            # Item kleur cirkel
            pygame.draw.circle(self.screen, item["kleur"], (rect.centerx, rect.y + 75), 28)
            pygame.draw.circle(self.screen, (255,255,255), (rect.centerx, rect.y + 75), 28, 2)
            # Nummer
            num_t = self.font_m.render(str(i+1), True, (200,200,200))
            self.screen.blit(num_t, (rect.x + rect.width - 22, rect.y + 10))
            # Naam
            naam_t = self.font_m.render(item["naam"], True, (220, 200, 150))
            self.screen.blit(naam_t, (rect.centerx - naam_t.get_width()//2, rect.y + 115))
            # Beschrijving (meerdere regels)
            for j, regel in enumerate(item["beschrijving"].split("\n")):
                rt = self.font_s.render(regel, True, (160, 155, 145))
                self.screen.blit(rt, (rect.centerx - rt.get_width()//2, rect.y + 145 + j * 18))

    def game_over_scherm(self):
        knop = pygame.Rect(SCREEN_W//2-130, SCREEN_H//2+60, 260, 50)
        while True:
            self.screen.fill((12,8,8))
            t = self.font_g.render("GAME OVER", True,(220,60,60))
            self.screen.blit(t,(SCREEN_W//2-t.get_width()//2, SCREEN_H//2-110))
            s = self.save
            for i,(r,kl) in enumerate([
                (f"Gevallen op floor {self.level_mgr.floor_nr}", (180,80,80)),
                ("Je kunt het opnieuw proberen!", (200,200,120)),
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
                    self._reset_run_items()
                    return "hub"
