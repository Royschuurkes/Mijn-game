# opslaan.py - Constanten, save/load, stat berekeningen
import json, os, copy

SAVE_FILE = "savegame.json"
SCREEN_W, SCREEN_H = 800, 600
FPS  = 60
TILE = 48

# Basis stats (zonder upgrades)
BASIS_HP      = 100.0
BASIS_STAMINA = 100.0
BASIS_MANA    = 50.0

# Groei per ability point
HP_PER_PUNT    = 25.0
STA_PER_PUNT   = 20.0
MANA_PER_PUNT  = 25.0
STR_PER_PUNT   = 3.0   # extra schade per strength punt
DEX_PER_PUNT   = 1.0   # extra dodge afstand per dex punt

# Gevecht
PLAYER_SPEED   = 3.0
DODGE_SPEED    = 13.0
DODGE_FRAMES   = 18
DODGE_CD       = 45
ZWAARD_FRAMES  = 20
ZWAARD_BEREIK  = 58
ZWAARD_HOEK    = 100
ZWAARD_CD      = 18
THORN_DAMAGE   = 0.4

STAMINA_DODGE  = 25.0
STAMINA_ZWAARD = 8.0
STAMINA_REGEN_PCT = 0.25  # 25% van max stamina per seconde
STAMINA_DELAY  = 2 * FPS

SPELER_SCHADE       = 25.0
VIJAND_MELEE_SCHADE = 25.0
PIJL_SCHADE         = 25.0
VIJAND_HP_BASIS     = 100.0
VIJAND_SNELHEID     = 1.4
PIJL_SNELHEID       = 5

FLINCH_SPELER    = 18
FLINCH_VIJAND    = 36
FLINCH_CD_SPELER = 60
KNOCKBACK        = 6.0

# Progressie
XP_PER_VIJAND    = 30
GOLD_MIN         = 5
GOLD_MAX         = 15
PUNTEN_PER_LVL   = 3

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
    "level": 1, "xp": 0, "gold": 0, "ability_points": 0,
    "wapen": "simpel_zwaard",
    "gekochte_wapens": ["simpel_zwaard"],
    "stats": {
        "hp": 0, "stamina": 0, "mana": 0,
        "strength": 0, "dexterity": 0, "intelligence": 0
    }
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

def xp_nodig(level):
    return int(100 * (level ** 1.4))

def voeg_xp_toe(save, xp):
    leveled_up = False
    save["xp"] += xp
    while save["xp"] >= xp_nodig(save["level"]):
        save["xp"] -= xp_nodig(save["level"])
        save["level"] += 1
        save["ability_points"] += PUNTEN_PER_LVL
        leveled_up = True
    return leveled_up

def max_hp(save):      return BASIS_HP      + save["stats"]["hp"]      * HP_PER_PUNT
def max_sta(save):     return BASIS_STAMINA + save["stats"]["stamina"]  * STA_PER_PUNT
def max_mana(save):    return BASIS_MANA    + save["stats"]["mana"]     * MANA_PER_PUNT
def extra_schade(save):return save["stats"]["strength"] * STR_PER_PUNT
def extra_dodge(save): return save["stats"]["dexterity"] * DEX_PER_PUNT
