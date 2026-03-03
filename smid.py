# smid.py - Smid shop UI
import pygame
from opslaan import SCREEN_W, SCREEN_H, FPS, sla_op
from wapens import WAPENS, SHOP_VOLGORDE, get_wapen, kan_dragen, vereisten_tekst

C_ACHTER   = (25, 20, 15)
C_PANEL    = (45, 35, 25)
C_RAND     = (150, 110, 60)
C_RAND_ACT = (220, 180, 80)
C_TEKST    = (220, 200, 160)
C_GRIJS    = (130, 120, 110)
C_GOUD     = (220, 190, 60)
C_GROEN    = (80, 200, 100)
C_ROOD     = (220, 80, 80)
C_UITGERUST= (80, 180, 255)


class SmidScene:
    def __init__(self, screen, clock, save):
        self.screen = screen
        self.clock  = clock
        self.save   = save
        self.font_g = pygame.font.SysFont("monospace", 26, bold=True)
        self.font_m = pygame.font.SysFont("monospace", 18)
        self.font_s = pygame.font.SysFont("monospace", 14)
        self.geselecteerd = 0
        self.bericht = ""
        self.bericht_timer = 0

        if "wapen" not in self.save:
            self.save["wapen"] = "simpel_zwaard"
        if "gekochte_wapens" not in self.save:
            self.save["gekochte_wapens"] = ["simpel_zwaard"]

    def run(self):
        while True:
            self.clock.tick(FPS)
            events = pygame.event.get()
            resultaat = self._verwerk_events(events)
            if resultaat: return resultaat
            if self.bericht_timer > 0: self.bericht_timer -= 1
            self._teken()
            pygame.display.flip()

    def _verwerk_events(self, events):
        for e in events:
            if e.type == pygame.QUIT: return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE: return "sluit"
                if e.key == pygame.K_LEFT  or e.key == pygame.K_a:
                    self.geselecteerd = max(0, self.geselecteerd-1)
                if e.key == pygame.K_RIGHT or e.key == pygame.K_d:
                    self.geselecteerd = min(len(SHOP_VOLGORDE)-1, self.geselecteerd+1)
                if e.key == pygame.K_b: self._koop()
                if e.key == pygame.K_RETURN: self._uitrusten()
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                koop_knop, uitrust_knop, sluit_knop = self._knop_rects()
                if koop_knop    and koop_knop.collidepoint(e.pos):    self._koop()
                if uitrust_knop and uitrust_knop.collidepoint(e.pos): self._uitrusten()
                if sluit_knop.collidepoint(e.pos): return "sluit"
                for i, rect in enumerate(self._wapen_rects()):
                    if rect.collidepoint(e.pos): self.geselecteerd = i
        return None

    def _koop(self):
        sleutel = SHOP_VOLGORDE[self.geselecteerd]
        wapen   = WAPENS[sleutel]
        if sleutel in self.save["gekochte_wapens"]:
            self.bericht = "Al in bezit!"; self.bericht_timer = 2*FPS; return
        if not kan_dragen(wapen, self.save["stats"]):
            self.bericht = "Niet genoeg stats!"; self.bericht_timer = 2*FPS; return
        if self.save["gold"] < wapen["prijs"]:
            self.bericht = "Niet genoeg gold!"; self.bericht_timer = 2*FPS; return
        self.save["gold"] -= wapen["prijs"]
        self.save["gekochte_wapens"].append(sleutel)
        sla_op(self.save)
        self.bericht = wapen["naam"] + " gekocht!"; self.bericht_timer = 2*FPS

    def _uitrusten(self):
        sleutel = SHOP_VOLGORDE[self.geselecteerd]
        if sleutel not in self.save["gekochte_wapens"]:
            self.bericht = "Eerst kopen!"; self.bericht_timer = 2*FPS; return
        self.save["wapen"] = sleutel
        sla_op(self.save)
        self.bericht = WAPENS[sleutel]["naam"] + " uitgerust!"; self.bericht_timer = 2*FPS

    def _wapen_rects(self):
        rects = []
        n = len(SHOP_VOLGORDE)
        breedte = min(100, (SCREEN_W-80)//n)
        totaal  = n*breedte + (n-1)*10
        start_x = SCREEN_W//2 - totaal//2
        for i in range(n):
            rects.append(pygame.Rect(start_x + i*(breedte+10), 80, breedte, 90))
        return rects

    def _knop_rects(self):
        sleutel     = SHOP_VOLGORDE[self.geselecteerd]
        al_in_bezit = sleutel in self.save["gekochte_wapens"]
        uitgerust   = self.save.get("wapen") == sleutel
        midden      = SCREEN_W//2
        koop_knop    = None if al_in_bezit else pygame.Rect(midden-130, SCREEN_H-90, 120, 40)
        uitrust_knop = None if uitgerust   else pygame.Rect(midden+10,  SCREEN_H-90, 120, 40)
        sluit_knop   = pygame.Rect(SCREEN_W-140, SCREEN_H-50, 120, 36)
        return koop_knop, uitrust_knop, sluit_knop

    def _teken(self):
        self.screen.fill(C_ACHTER)
        t = self.font_g.render("Smid", True, C_RAND_ACT)
        self.screen.blit(t, (SCREEN_W//2-t.get_width()//2, 20))
        gt = self.font_m.render("Gold: " + str(self.save["gold"]), True, C_GOUD)
        self.screen.blit(gt, (SCREEN_W-gt.get_width()-20, 20))
        huidig = WAPENS.get(self.save.get("wapen","simpel_zwaard"), WAPENS["simpel_zwaard"])
        ht = self.font_s.render("Uitgerust: " + huidig["naam"], True, C_UITGERUST)
        self.screen.blit(ht, (20, 20))

        rects = self._wapen_rects()
        for i, sleutel in enumerate(SHOP_VOLGORDE):
            wapen     = WAPENS[sleutel]
            rect      = rects[i]
            act       = i == self.geselecteerd
            bezit     = sleutel in self.save["gekochte_wapens"]
            uitgerust = self.save.get("wapen") == sleutel
            kan       = kan_dragen(wapen, self.save["stats"])
            rand_kl   = C_UITGERUST if uitgerust else (C_RAND_ACT if act else C_RAND)
            bg_kl     = (60,50,35) if act else C_PANEL
            pygame.draw.rect(self.screen, bg_kl,   rect, border_radius=6)
            pygame.draw.rect(self.screen, rand_kl, rect, 2, border_radius=6)
            cx = rect.centerx; cy = rect.y+35
            pygame.draw.circle(self.screen, wapen["kleur"] if kan else C_GRIJS, (cx,cy), 20)
            if uitgerust:
                pygame.draw.circle(self.screen, C_UITGERUST, (cx,cy), 20, 3)
            nt = self.font_s.render(wapen["naam"][:10], True, C_TEKST if kan else C_GRIJS)
            self.screen.blit(nt, (rect.centerx-nt.get_width()//2, rect.y+62))
            if bezit:
                st = self.font_s.render("In bezit", True, C_GROEN)
            else:
                kl2 = C_GOUD if self.save["gold"] >= wapen["prijs"] and kan else C_ROOD
                st  = self.font_s.render(str(wapen["prijs"])+"g", True, kl2)
            self.screen.blit(st, (rect.centerx-st.get_width()//2, rect.y+74))

        sleutel = SHOP_VOLGORDE[self.geselecteerd]
        wapen   = WAPENS[sleutel]
        kan     = kan_dragen(wapen, self.save["stats"])
        px=40; py=190; pw=SCREEN_W-80; ph=SCREEN_H-310
        pygame.draw.rect(self.screen, C_PANEL, (px,py,pw,ph), border_radius=8)
        pygame.draw.rect(self.screen, C_RAND,  (px,py,pw,ph), 2, border_radius=8)
        nt = self.font_g.render(wapen["naam"], True, wapen["kleur"])
        self.screen.blit(nt, (px+20, py+14))
        tt = self.font_s.render(wapen["type"].upper(), True, C_GRIJS)
        self.screen.blit(tt, (px+20, py+46))

        stats = []
        if wapen["schade"] > 0:
            stats.append("Schade:   " + str(wapen["schade"]))
        if wapen["zwaard_cd"] > 0:
            stats.append("Snelheid: " + str(round(60/wapen["zwaard_cd"],1)) + " aanslagen/sec")
        if wapen["bereik"] > 0:
            stats.append("Bereik:   " + str(wapen["bereik"]) + " px")
        if wapen.get("blok_reductie"):
            stats.append("Blok:     " + str(int(wapen["blok_reductie"]*100)) + "% reductie")
        if wapen["special"]:
            stats.append("Special:  " + wapen["special"] + " (" + str(wapen["special_stamina"]) + " stamina)")
        for i, s in enumerate(stats):
            self.screen.blit(self.font_s.render(s, True, C_TEKST), (px+20, py+68+i*20))

        for i, regel in enumerate(wapen["omschrijving"].split("\n")):
            rt = self.font_m.render(regel, True, C_TEKST)
            self.screen.blit(rt, (px+pw//2, py+68+i*26))

        vt = self.font_s.render("Vereist: " + vereisten_tekst(wapen), True,
                                 C_GROEN if kan else C_ROOD)
        self.screen.blit(vt, (px+20, py+ph-28))

        koop_knop, uitrust_knop, sluit_knop = self._knop_rects()
        mp = pygame.mouse.get_pos()
        if koop_knop:
            kk = (70,130,70) if koop_knop.collidepoint(mp) else (45,90,45)
            pygame.draw.rect(self.screen, kk,      koop_knop, border_radius=6)
            pygame.draw.rect(self.screen, C_GROEN, koop_knop, 2, border_radius=6)
            kt = self.font_m.render("Koop (" + str(wapen["prijs"]) + "g)", True, (255,255,255))
            self.screen.blit(kt, (koop_knop.centerx-kt.get_width()//2, koop_knop.centery-kt.get_height()//2))
        if uitrust_knop:
            uk = (60,80,140) if uitrust_knop.collidepoint(mp) else (40,55,100)
            pygame.draw.rect(self.screen, uk,          uitrust_knop, border_radius=6)
            pygame.draw.rect(self.screen, C_UITGERUST, uitrust_knop, 2, border_radius=6)
            ut = self.font_m.render("Uitrusten", True, (255,255,255))
            self.screen.blit(ut, (uitrust_knop.centerx-ut.get_width()//2, uitrust_knop.centery-ut.get_height()//2))
        sk = (100,60,60) if sluit_knop.collidepoint(mp) else (70,40,40)
        pygame.draw.rect(self.screen, sk,     sluit_knop, border_radius=6)
        pygame.draw.rect(self.screen, C_ROOD, sluit_knop, 2, border_radius=6)
        st2 = self.font_m.render("Sluiten (ESC)", True, (255,255,255))
        self.screen.blit(st2, (sluit_knop.centerx-st2.get_width()//2, sluit_knop.centery-st2.get_height()//2))

        if self.bericht_timer > 0:
            bt = self.font_m.render(self.bericht, True, C_GOUD)
            self.screen.blit(bt, (SCREEN_W//2-bt.get_width()//2, SCREEN_H-130))
