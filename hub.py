# hub.py - Binnenplein (kasteel hub wereld)
import math, pygame
from opslaan import *

# Hub tile types (apart van de bos types)
STEEN  = 4
MUU    = 5  # muur
GRAS_H = 6  # gras in binnenplein

C_STEEN   = (130,120,110)
C_STEEN_D = (115,105,95)
C_MUU     = (85,75,70)
C_GRAS_H  = (70,140,60)
C_GRAS_HD = (55,120,45)

# Binnenplein kaart (24 x 18 tiles)
# F=steen, W=muur, G=gras, _=open ruimte (steen)
HUB_KAART_RAW = [
    "WWWWWWWWWWWWWWWWWWWWWWWW",
    "WFFFFFFFFFFFFFFFFFFFFFFFFW",
    "WFFFFFFFFFFFFFFFFFFFFFFFFW",
    "WFF[B]FFFFFFFFFFFFFFFF[L]FFW",
    "WFFFFFFFFFFFFFFFFFFFFFFFFW",
    "WFFFFFFFFFFFFFFFFFFFFFFFFW",
    "WFFFFFFFFgggggggFFFFFFFFFW",
    "WFFFFFFFFgggSgggFFFFFFFFFW",
    "WFFFFFFFFgggggggFFFFFFFFFW",
    "WFFFFFFFFFFFFFFFFFFFFFFFFW",
    "WFFFFFFFFFFFFFFFFFFFFFFFFW",
    "WFFFFFFFFFFFFFFFFFFFFFFFFW",
    "WFFFFFFFFFFFFFFFFFFFFFFFFW",
    "WFFFFFFFFFFFFFFFFFFFFFFFFW",
    "WFFFFFFFFFFFFFFFFFFFFFFFFW",
    "WFFFFFFFFFFFFFFFFFFFFFFFFW",
    "WFFFFFFFFFFFFFFFFFFFFFFFFW",
    "WWWWWWWWWWWWWWWWWWWWWWWW",
]

# Simpelere versie: kaart als 2D array
def maak_hub_kaart():
    breedte=24; hoogte=18
    kaart=[[STEEN]*breedte for _ in range(hoogte)]

    # Muren
    for x in range(breedte):
        kaart[0][x]=MUU; kaart[hoogte-1][x]=MUU
    for y in range(hoogte):
        kaart[y][0]=MUU; kaart[y][breedte-1]=MUU

    # Gras in het midden
    for y in range(6,9):
        for x in range(8,16): kaart[y][x]=GRAS_H

    # Ingang (exit naar bos) - gat in de ondermuur midden
    for x in range(10,14): kaart[hoogte-1][x]=STEEN

    return kaart

# Interacteerbare objecten: (tile_x, tile_y, naam, kleur, beschrijving)
INTERACTABLES = [
    (4,  3, "standbeeld", (180,160,100), "Standbeeld"),
    (20, 3, "library",    (80, 120,180), "Bibliotheek"),
    (11, 7, "statue",     (200,200,180), "Standbeeld"),
]

EXIT_TILES = [(x, 17) for x in range(10,14)]

HUB_W = 24
HUB_H = 18


class HubScene:
    def __init__(self, screen, clock, save):
        self.screen=screen; self.clock=clock; self.save=save
        self.kaart=maak_hub_kaart()
        self.sp_x=float(HUB_W//2*TILE+TILE//2)
        self.sp_y=float((HUB_H-3)*TILE)
        self.fx=0.0; self.fy=-1.0
        self.font_s=pygame.font.SysFont("monospace",15)
        self.font_m=pygame.font.SysFont("monospace",20)
        self.font_g=pygame.font.SysFont("monospace",28,bold=True)
        self.menu_open=None
        self.level_up_msg = 3 * FPS if save.get("hoogste_floor", 0) > 0 else 0

    def tile_op(self,tx,ty):
        if 0<=tx<HUB_W and 0<=ty<HUB_H: return self.kaart[ty][tx]
        return MUU

    def geblokkeerd(self,tx,ty):
        return self.tile_op(tx,ty)==MUU

    def dichtstbije_interactable(self):
        for (tx,ty,naam,kl,label) in INTERACTABLES:
            wx=tx*TILE+TILE//2; wy=ty*TILE+TILE//2
            if math.hypot(self.sp_x-wx, self.sp_y-wy)<70:
                return (tx,ty,naam,kl,label)
        return None

    def bij_exit(self):
        tx=int(self.sp_x//TILE); ty=int(self.sp_y//TILE)
        return ty>=HUB_H-1

    def run(self):
        menu_events = []
        while True:
            self.clock.tick(FPS)
            events = pygame.event.get()
            menu_events = events  # standaard zelfde events

            for e in events:
                if e.type==pygame.QUIT: return "quit"
                if e.type==pygame.KEYDOWN:
                    if e.key==pygame.K_ESCAPE:
                        if self.menu_open: self.menu_open=None
                        else: return "quit"
                    if e.key==pygame.K_e and self.menu_open is None:
                        nb=self.dichtstbije_interactable()
                        if nb:
                            self.menu_open=nb[2]
                            menu_events=[]  # lege events zodat menu niet meteen sluit

            if self.menu_open == "statue" or self.menu_open == "standbeeld":
                resultaat = self.teken_placeholder("Standbeeld", "Dit standbeeld straalt kracht uit.", menu_events)
                if resultaat == "sluit": self.menu_open = None
                pygame.display.flip(); continue
            elif self.menu_open == "library":
                resultaat = self.teken_placeholder("Bibliotheek", "Hier kun je later\nmagische spreuken leren!", menu_events)
                if resultaat == "sluit": self.menu_open = None
                pygame.display.flip(); continue
            elif self.menu_open is not None:
                # Onbekend menu — sluit direct
                self.menu_open = None

            if self.menu_open is None:
                keys=pygame.key.get_pressed()
                mx,my=0.0,0.0
                if keys[pygame.K_w] or keys[pygame.K_UP]:    my-=1
                if keys[pygame.K_s] or keys[pygame.K_DOWN]:  my+=1
                if keys[pygame.K_a] or keys[pygame.K_LEFT]:  mx-=1
                if keys[pygame.K_d] or keys[pygame.K_RIGHT]: mx+=1
                l=math.hypot(mx,my)
                if l: mx,my=mx/l,my/l
                if mx or my: self.fx,self.fy=mx,my

                speed=2.5; r=13
                nx=self.sp_x+mx*speed
                if not any(self.geblokkeerd(int((nx+ox)//TILE),int((self.sp_y+oy)//TILE)) for ox in(-r,r) for oy in(-r,r)):
                    self.sp_x=nx
                ny=self.sp_y+my*speed
                if not any(self.geblokkeerd(int((self.sp_x+ox)//TILE),int((ny+oy)//TILE)) for ox in(-r,r) for oy in(-r,r)):
                    self.sp_y=ny

                if self.bij_exit(): return "bos"

            if self.level_up_msg>0: self.level_up_msg-=1
            self.teken()
            pygame.display.flip()

    def teken(self):
        cam_x=max(0,min(int(self.sp_x-SCREEN_W/2),HUB_W*TILE-SCREEN_W))
        cam_y=max(0,min(int(self.sp_y-SCREEN_H/2),HUB_H*TILE-SCREEN_H))

        self.screen.fill((20,20,20))

        # Tiles
        for ty in range(HUB_H):
            for tx in range(HUB_W):
                sx=tx*TILE-cam_x; sy=ty*TILE-cam_y
                t=self.tile_op(tx,ty)
                r=pygame.Rect(sx,sy,TILE,TILE)
                if t==STEEN:
                    kl=C_STEEN if(tx+ty)%2==0 else C_STEEN_D
                    pygame.draw.rect(self.screen,kl,r)
                elif t==MUU:
                    pygame.draw.rect(self.screen,C_MUU,r)
                    pygame.draw.rect(self.screen,(60,52,48),r,2)
                elif t==GRAS_H:
                    kl=C_GRAS_H if(tx+ty)%2==0 else C_GRAS_HD
                    pygame.draw.rect(self.screen,kl,r)

        # Exit markering
        for (etx,ety) in EXIT_TILES:
            sx=etx*TILE-cam_x; sy=ety*TILE-cam_y
            pygame.draw.rect(self.screen,(80,160,80),(sx,sy,TILE,TILE))
            if abs(self.sp_x//TILE - etx)<3 and self.sp_y//TILE>=HUB_H-2:
                t=self.font_s.render("ENTER - Bos",True,(200,255,200))
                self.screen.blit(t,(SCREEN_W//2-t.get_width()//2, SCREEN_H-40))

        # Interactables tekenen
        nb=self.dichtstbije_interactable()
        for (tx,ty,naam,kl,label) in INTERACTABLES:
            sx=tx*TILE-cam_x; sy=ty*TILE-cam_y
            pygame.draw.rect(self.screen,kl,(sx+4,sy+4,TILE-8,TILE-8),border_radius=6)
            pygame.draw.rect(self.screen,(255,255,255),(sx+4,sy+4,TILE-8,TILE-8),2,border_radius=6)
            lt=self.font_s.render(label[:1],True,(255,255,255))
            self.screen.blit(lt,(sx+TILE//2-lt.get_width()//2,sy+TILE//2-lt.get_height()//2))
            if nb and nb[2]==naam:
                pt=self.font_s.render("[E] "+label,True,(255,255,150))
                self.screen.blit(pt,(sx+TILE//2-pt.get_width()//2,sy-22))

        # Speler
        ssx=int(self.sp_x-cam_x); ssy=int(self.sp_y-cam_y)
        pygame.draw.ellipse(self.screen,C_SCH,(ssx-11,ssy+9,22,11))
        pygame.draw.circle(self.screen,C_SP,(ssx,ssy),15)
        pygame.draw.circle(self.screen,C_OOG,(int(ssx+self.fx*9),int(ssy+self.fy*9)),5)

        # HUD
        self.teken_hub_hud()

        # Welkom terug scherm — floor progress
        if self.level_up_msg > 0:
            alpha = min(255, self.level_up_msg * 5)
            floor_bereikt = self.save.get("hoogste_floor", 0)
            if floor_bereikt > 0:
                overlay2 = pygame.Surface((SCREEN_W, 120), pygame.SRCALPHA)
                overlay2.fill((0, 0, 0, min(160, alpha)))
                self.screen.blit(overlay2, (0, SCREEN_H//2 - 70))
                t1 = self.font_g.render("Welkom terug, ridder!", True, (220, 200, 120))
                t1.set_alpha(alpha)
                self.screen.blit(t1, (SCREEN_W//2 - t1.get_width()//2, SCREEN_H//2 - 55))
                t2 = self.font_m.render(f"Hoogste floor bereikt: Floor {floor_bereikt}", True, (180, 220, 255))
                t2.set_alpha(alpha)
                self.screen.blit(t2, (SCREEN_W//2 - t2.get_width()//2, SCREEN_H//2 - 10))

    def teken_hub_hud(self):
        t = self.font_s.render("Hub  —  WASD bewegen, E interacteren, portaal naar level", True, (220,220,180))
        self.screen.blit(t, (10, 10))

    def teken_placeholder(self, titel, tekst, events):
        overlay=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        overlay.fill((0,0,0,180))
        self.screen.blit(overlay,(0,0))
        pw=400; ph=220; px=(SCREEN_W-pw)//2; py=(SCREEN_H-ph)//2
        pygame.draw.rect(self.screen,(35,40,50),(px,py,pw,ph),border_radius=10)
        pygame.draw.rect(self.screen,(100,140,180),(px,py,pw,ph),2,border_radius=10)
        t=self.font_g.render(titel,True,(160,200,230))
        self.screen.blit(t,(px+pw//2-t.get_width()//2,py+20))
        for i,regel in enumerate(tekst.split("\n")):
            rt=self.font_m.render(regel,True,(200,200,200))
            self.screen.blit(rt,(px+pw//2-rt.get_width()//2,py+80+i*28))
        ct=self.font_s.render("Druk E of ESC om te sluiten",True,(150,150,150))
        self.screen.blit(ct,(px+pw//2-ct.get_width()//2,py+ph-30))
        for e in events:
            if e.type==pygame.KEYDOWN and e.key in(pygame.K_e,pygame.K_ESCAPE):
                self.menu_open=None
