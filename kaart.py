# kaart.py - Kaart generatie voor het bos
import random
from opslaan import *

BOOM_PAL = [
    ((100,65,30),(45,130,40),(30,100,25)),
    ((90,55,25),(55,145,35),(35,110,20)),
    ((110,70,35),(35,110,50),(20,85,35)),
    ((95,60,28),(80,130,30),(60,100,15)),
]

def genereer_bos(breedte=40, hoogte=40):
    kaart = [[GRAS]*breedte for _ in range(hoogte)]

    def zet(tx,ty,t):
        if 0<=tx<breedte and 0<=ty<hoogte: kaart[ty][tx]=t

    def tile_op(tx,ty):
        if 0<=tx<breedte and 0<=ty<hoogte: return kaart[ty][tx]
        return BOOM

    # Slingerende paden
    def slingerpad(horizontaal=True):
        if horizontaal:
            y=hoogte//2+random.randint(-3,3)
            for x in range(breedte):
                y=max(3,min(hoogte-4,y+random.randint(-1,1)))
                for dy in range(-1,2): zet(x,y+dy,PAD)
        else:
            x=breedte//2+random.randint(-3,3)
            for y in range(hoogte):
                x=max(3,min(breedte-4,x+random.randint(-1,1)))
                for dx in range(-1,2): zet(x+dx,y,PAD)

    slingerpad(True); slingerpad(False)

    # Struiken
    for _ in range(60):
        tx=random.randint(1,breedte-2); ty=random.randint(1,hoogte-2)
        if kaart[ty][tx]==GRAS:
            for dy in range(random.randint(1,2)):
                for dx in range(random.randint(1,2)): zet(tx+dx,ty+dy,STRUIK)

    # Bomen
    bomen=[]
    def plaats_boom(tx,ty,g):
        for dy in range(g):
            for dx in range(g):
                if tile_op(tx+dx,ty+dy)!=GRAS: return False
        for dy in range(g):
            for dx in range(g): zet(tx+dx,ty+dy,BOOM)
        bomen.append((tx,ty,g)); return True

    for _ in range(300):
        g=random.choices([2,3,4],weights=[5,3,1])[0]
        tx=random.randint(0,breedte-g-1); ty=random.randint(0,hoogte-g-1)
        plaats_boom(tx,ty,g)

    # Rand dicht
    for tx in range(breedte):
        for ty in [0,hoogte-1]: zet(tx,ty,BOOM)
    for ty in range(hoogte):
        for tx in [0,breedte-1]: zet(tx,ty,BOOM)

    # Spawnplek vrijmaken
    stx,sty=breedte//2,hoogte//2
    for dy in range(-3,4):
        for dx in range(-3,4): zet(stx+dx,sty+dy,PAD)
    bomen=[(tx,ty,g) for (tx,ty,g) in bomen
           if not(stx-g<=tx<=stx+3 and sty-g<=ty<=sty+3)]

    rng=random.Random(random.randint(0,9999))
    pal_map={(tx,ty):rng.choice(BOOM_PAL) for (tx,ty,g) in bomen}

    return kaart, bomen, pal_map, stx, sty, tile_op


def teken_bos_tegel(surface, tx, ty, sx, sy, tile_op):
    import pygame, random
    t=tile_op(tx,ty); r=pygame.Rect(sx,sy,TILE,TILE)
    if t in(GRAS,BOOM):
        pygame.draw.rect(surface,C_GRAS if(tx+ty)%2==0 else C_GRAS_D,r)
    elif t==PAD:
        pygame.draw.rect(surface,C_PAD,r)
        pygame.draw.rect(surface,C_PAD_R,r,2)
    elif t==STRUIK:
        pygame.draw.rect(surface,C_GRAS if(tx+ty)%2==0 else C_GRAS_D,r)
        rn=random.Random(tx*999+ty)
        for _ in range(5):
            bx=rn.randint(6,TILE-10); by=rn.randint(6,TILE-10)
            pygame.draw.circle(surface,(160,50,50),(sx+bx,sy+by),9)
            pygame.draw.circle(surface,(120,30,30),(sx+bx,sy+by),9,2)


def teken_boom_object(surface, tx, ty, grootte, palet, cam_x, cam_y):
    import pygame, random, math
    sk,bk,rk=palet; pw=grootte*TILE
    cx=tx*TILE-cam_x+pw//2; cy=ty*TILE-cam_y+pw//2
    pygame.draw.ellipse(surface,(15,25,15),(cx-pw//2+8,cy+pw//4-4,pw-8,pw//3))
    sb=max(6,grootte*5)
    pygame.draw.rect(surface,sk,(cx-sb//2,cy,sb,pw//2))
    rh=int(pw*0.52)
    pygame.draw.circle(surface,bk,(cx,cy-pw//6),rh)
    rn=random.Random(tx*1000+ty)
    for _ in range(grootte*3):
        ox=rn.randint(-rh//2,rh//2); oy=rn.randint(-rh//2,rh//2)
        rb=rn.randint(rh//4,rh//2)
        pygame.draw.circle(surface,bk,(cx+ox,cy-pw//6+oy),rb)
    pygame.draw.circle(surface,rk,(cx,cy-pw//6),rh,3)
