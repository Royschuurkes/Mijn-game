# opslaan.py - Constanten, save/load
import json, os, copy

SAVE_FILE = "savegame.json"
SCREEN_W, SCREEN_H = 800, 600
FPS  = 60
TILE = 48

# Speler stats (vast, geen leveling)
BASIS_HP      = 100.0
BASIS_STAMINA = 84.0

# Beweging
PLAYER_SPEED   = 3.0
DODGE_SPEED    = 8.0
DODGE_FRAMES   = 12
DODGE_CD       = 38
SPRINT_SPEED   = 1.7
SPRINT_STAMINA = 0.25

# Zwaard
ZWAARD_FRAMES  = 12
ZWAARD_BEREIK  = 88
ZWAARD_HOEK    = 100
ZWAARD_CD      = 14

# Stamina
STAMINA_DODGE     = 30.0
STAMINA_ZWAARD    = 14.0
STAMINA_REGEN_PCT = 0.80
STAMINA_DELAY     = 90
STAMINA_SCHILD    = 18.0   # melee blok: ~4-5 hits voor guard break
STAMINA_SCHILD_PIJL = 12.0  # pijl blok: goedkoper, maar salvo kost alsnog 36
GUARD_BREAK_T     = 50

# Schade & gevecht
SPELER_SCHADE       = 25.0
VIJAND_MELEE_SCHADE = 25.0
PIJL_SCHADE         = 25.0
VIJAND_HP_BASIS     = 100.0
VIJAND_SNELHEID     = 1.4
PIJL_SNELHEID       = 10

FLINCH_SPELER    = 18
FLINCH_VIJAND    = 50
FLINCH_CD_SPELER = 60
KNOCKBACK        = 10.0

# Tile types
GRAS, PAD, BOOM, STRUIK = 0, 1, 2, 3

# Kleuren
C_GRAS   = (75,155,65);   C_GRAS_D  = (60,135,50)
C_PAD    = (210,185,130); C_PAD_R   = (185,160,105)
C_BG     = (30,30,30)
C_SP     = (80,160,255);  C_SP_DOD  = (180,220,255)
C_OOG    = (220,240,255); C_SCH     = (15,25,15)
C_STR    = (160,50,50);   C_STR2    = (120,30,30)
C_ZWAARD = (210,210,230); C_SCHILD  = (190,150,60)
C_MELEE  = (220,80,80);   C_RANGED  = (180,80,210)
C_PIJL   = (190,150,80)

BOOM_PAL = [
    ((100,65,30),(45,130,40),(30,100,25)),
    ((90,55,25),(55,145,35),(35,110,20)),
    ((110,70,35),(35,110,50),(20,85,35)),
    ((95,60,28),(80,130,30),(60,100,15)),
]

DEFAULT_SAVE = {
    "wapen":            "schild",
    "items":            [],   # verkregen items deze run
    "item_charges":     {},   # {item_key: charges_remaining}
    "actieve_effecten": {     # tijdelijke effecten met afteltimer
        "invis":       0,
        "fire_potion":  0,
    },
}

def laad_save():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE) as f: d = json.load(f)
            for k, v in DEFAULT_SAVE.items():
                if k not in d: d[k] = copy.deepcopy(v)
            return d
        except: pass
    return copy.deepcopy(DEFAULT_SAVE)

def sla_op(save):
    with open(SAVE_FILE, "w") as f: json.dump(save, f, indent=2)

def reset_save():
    if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)

def max_hp(save):       return BASIS_HP
def max_sta(save):      return BASIS_STAMINA
def extra_schade(save): return 0.0
def extra_dodge(save):  return 0.0
