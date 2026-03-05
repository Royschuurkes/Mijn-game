# kaart.py - Arena-gebaseerde kaartgeneratie (BoI/Archero stijl)
import random, math, pygame
from opslaan import *

BOOM_PAL = [
    ((100,65,30),(45,130,40),(30,100,25)),
    ((90,55,25),(55,145,35),(35,110,20)),
    ((110,70,35),(35,110,50),(20,85,35)),
    ((95,60,28),(80,130,30),(60,100,15)),
]
KAART_B = 26
KAART_H = 20

def _zet(kaart, tx, ty, t):
    if 0 <= tx < KAART_B and 0 <= ty < KAART_H:
        kaart[ty][tx] = t

def _tile_op_fn(kaart):
    def tile_op(tx, ty):
        if 0 <= tx < KAART_B and 0 <= ty < KAART_H: return kaart[ty][tx]
        return BOOM
    return tile_op

def _boom_pilaar(kaart, cx, cy, straal=1):
    for dy in range(-straal, straal+1):
        for dx in range(-straal, straal+1):
            if dx*dx + dy*dy <= straal*straal + 0.5:
                _zet(kaart, cx+dx, cy+dy, BOOM)

def _struik_plek(kaart, cx, cy, breedte=2, hoogte=2):
    for dy in range(hoogte):
        for dx in range(breedte):
            if 0<=cx+dx<KAART_B and 0<=cy+dy<KAART_H and kaart[cy+dy][cx+dx]==GRAS:
                _zet(kaart, cx+dx, cy+dy, STRUIK)

def _maak_basis():
    kaart = [[GRAS]*KAART_B for _ in range(KAART_H)]
    for tx in range(KAART_B):
        for d in range(2):
            _zet(kaart, tx, d, BOOM)
            _zet(kaart, tx, KAART_H-1-d, BOOM)
    for ty in range(KAART_H):
        for d in range(2):
            _zet(kaart, d, ty, BOOM)
            _zet(kaart, KAART_B-1-d, ty, BOOM)
    return kaart

def _layout_open_pilaren(kaart):
    mx=KAART_B//2; my=KAART_H//2
    for ox,oy in [(-4,-3),(4,-3),(-4,3),(4,3)]:
        _boom_pilaar(kaart, mx+ox, my+oy, straal=1)
    _struik_plek(kaart, 4, 4, 3, 2)
    _struik_plek(kaart, KAART_B-7, 4, 3, 2)
    _struik_plek(kaart, 4, KAART_H-6, 3, 2)
    _struik_plek(kaart, KAART_B-7, KAART_H-6, 3, 2)

def _layout_chokepoint(kaart):
    my=KAART_H//2
    for ty in range(2, KAART_H-2):
        if abs(ty-my) > 2:
            _zet(kaart, KAART_B//2-1, ty, BOOM)
            _zet(kaart, KAART_B//2,   ty, BOOM)
            _zet(kaart, KAART_B//2+1, ty, BOOM)
    _struik_plek(kaart, KAART_B//2-4, my-1, 2, 3)
    _struik_plek(kaart, KAART_B//2+3, my-1, 2, 3)

def _layout_boomgang(kaart):
    my=KAART_H//2
    for tx in range(4, KAART_B-4):
        if random.random()<0.65: _zet(kaart, tx, my-3, BOOM)
        if random.random()<0.65: _zet(kaart, tx, my+3, BOOM)
    for tx in range(KAART_B//3, 2*KAART_B//3):
        _zet(kaart, tx, my-3, GRAS)
        _zet(kaart, tx, my+3, GRAS)

def _layout_ruines(kaart):
    for tx,ty in [(5,4),(5,5),(6,4),(KAART_B-7,4),(KAART_B-6,4),(KAART_B-7,5),
                  (5,KAART_H-6),(5,KAART_H-5),(6,KAART_H-5),
                  (KAART_B-7,KAART_H-5),(KAART_B-6,KAART_H-5),(KAART_B-7,KAART_H-6),
                  (KAART_B//2-1,KAART_H//2-1),(KAART_B//2,KAART_H//2-1),
                  (KAART_B//2-1,KAART_H//2+1),(KAART_B//2,KAART_H//2+1)]:
        _zet(kaart, tx, ty, BOOM)
    for _ in range(6):
        tx=random.randint(5,KAART_B-6); ty=random.randint(4,KAART_H-5)
        _struik_plek(kaart, tx, ty, random.randint(1,2), random.randint(1,2))

def _layout_arena(kaart):
    cx=KAART_B//2; cy=KAART_H//2
    r_buiten=min(KAART_B,KAART_H)//2-2; r_binnen=r_buiten-3
    for ty in range(2, KAART_H-2):
        for tx in range(2, KAART_B-2):
            dist=math.hypot(tx-cx,(ty-cy)*1.4)
            if r_binnen<dist<r_buiten and random.random()<0.7:
                _zet(kaart, tx, ty, BOOM)
    for _ in range(4):
        hoek=random.uniform(0,math.pi*2)
        d=random.randint(2, max(2,r_binnen-2))
        _struik_plek(kaart, int(cx+math.cos(hoek)*d), int(cy+math.sin(hoek)*d/1.4), 2, 1)

def _layout_split(kaart):
    mx=KAART_B//2
    for ty in range(2, KAART_H-2):
        if ty<KAART_H//2-3 or ty>KAART_H//2+3:
            _zet(kaart, mx, ty, BOOM)
            _zet(kaart, mx+1, ty, BOOM)
    _boom_pilaar(kaart, mx//2, KAART_H//2, 1)
    _boom_pilaar(kaart, mx+mx//2+1, KAART_H//2, 1)
    _struik_plek(kaart, mx-2, KAART_H//2-2, 2, 4)

LAYOUTS = [_layout_open_pilaren, _layout_chokepoint, _layout_boomgang,
           _layout_ruines, _layout_arena, _layout_split]

def genereer_bos(deuren=None):
    if deuren is None: deuren = {"E"}
    kaart = _maak_basis()
    random.choice(LAYOUTS)(kaart)
    my = KAART_H // 2
    mx = KAART_B // 2
    spawn_posities = {}  # richting -> (tile_x, tile_y)
    if "W" in deuren:
        for dy in range(-2, 3):
            for dx in range(0, 4): _zet(kaart, dx, my+dy, PAD)
        spawn_posities["W"] = (2, my)
    if "E" in deuren:
        for dy in range(-2, 3):
            for dx in range(KAART_B-4, KAART_B): _zet(kaart, dx, my+dy, GRAS)
        spawn_posities["E"] = (KAART_B-3, my)
    if "N" in deuren:
        for dx in range(-2, 3):
            for dy in range(0, 4): _zet(kaart, mx+dx, dy, PAD)
        spawn_posities["N"] = (mx, 2)
    if "S" in deuren:
        for dx in range(-2, 3):
            for dy in range(KAART_H-4, KAART_H): _zet(kaart, mx+dx, dy, GRAS)
        spawn_posities["S"] = (mx, KAART_H-3)
    if not spawn_posities:
        spawn_posities["W"] = (KAART_B//2, KAART_H//2)
    tile_op = _tile_op_fn(kaart)
    bomen=[]; bezocht=set()
    for ty in range(KAART_H):
        for tx in range(KAART_B):
            if kaart[ty][tx]==BOOM and (tx,ty) not in bezocht:
                grootte=1
                if (tx+1<KAART_B and ty+1<KAART_H and kaart[ty][tx+1]==BOOM
                        and kaart[ty+1][tx]==BOOM and kaart[ty+1][tx+1]==BOOM
                        and (tx+1,ty) not in bezocht and (tx,ty+1) not in bezocht):
                    grootte=2
                    bezocht.update([(tx,ty),(tx+1,ty),(tx,ty+1),(tx+1,ty+1)])
                else:
                    bezocht.add((tx,ty))
                bomen.append((tx,ty,grootte))
    rng=random.Random(random.randint(0,9999))
    pal_map={(tx,ty):rng.choice(BOOM_PAL) for tx,ty,g in bomen}
    return kaart, bomen, pal_map, spawn_posities, tile_op


def teken_bos_tegel(surface, tx, ty, sx, sy, tile_op):
    t=tile_op(tx,ty); r=pygame.Rect(sx,sy,TILE,TILE)
    if t in (GRAS,BOOM):
        pygame.draw.rect(surface, C_GRAS if (tx+ty)%2==0 else C_GRAS_D, r)
    elif t==PAD:
        pygame.draw.rect(surface, C_PAD, r)
        pygame.draw.rect(surface, C_PAD_R, r, 2)
    elif t==STRUIK:
        pygame.draw.rect(surface, C_GRAS if (tx+ty)%2==0 else C_GRAS_D, r)
        rn=random.Random(tx*999+ty)
        for _ in range(5):
            bx=rn.randint(6,TILE-10); by=rn.randint(6,TILE-10)
            pygame.draw.circle(surface,(160,50,50),(sx+bx,sy+by),9)
            pygame.draw.circle(surface,(120,30,30),(sx+bx,sy+by),9,2)


def teken_boom_object(surface, tx, ty, grootte, palet, cam_x, cam_y):
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
