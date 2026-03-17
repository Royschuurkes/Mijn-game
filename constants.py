# constants.py - Constants, save/load, stat calculations
import json, os, copy

SAVE_FILE = "savegame.json"
SCREEN_W, SCREEN_H = 800, 600
FPS  = 60
TILE = 48

# ── Player stats ──────────────────────────────────────────────────────────────
BASE_HP      = 100.0
BASE_STAMINA = 84.0

# ── Movement ──────────────────────────────────────────────────────────────────
PLAYER_SPEED   = 3.0
DODGE_SPEED    = 8.0
DODGE_FRAMES   = 12
DODGE_CD       = 38
CHARGE_SPEED  = 14.0
CHARGE_FRAMES = 13
SPRINT_SPEED   = 1.7
SPRINT_STAMINA = 0.5

# ── Stamina costs ─────────────────────────────────────────────────────────────
STAMINA_DODGE        = 14
STAMINA_SWORD        = 14
STAMINA_REGEN_PCT    = 0.8
STAMINA_DELAY        = 70
STAMINA_SHIELD       = 12.0
STAMINA_SHIELD_ARROW = 8.0
BLOCK_DAMAGE_THROUGH = 0.50
GUARD_BREAK_TIMER    = 50

# ── Combat ────────────────────────────────────────────────────────────────────
PLAYER_DAMAGE      = 25.0
ENEMY_MELEE_DAMAGE = 25.0
ARROW_DAMAGE       = 25.0
ENEMY_BASE_HP      = 100.0
ENEMY_SPEED        = 1.4
ARROW_SPEED        = 10

FLINCH_PLAYER    = 18
FLINCH_ENEMY     = 50
FLINCH_CD_PLAYER = 60
KNOCKBACK        = 10.0

# ── Tile types ────────────────────────────────────────────────────────────────
GRASS, PATH, TREE, BUSH = 0, 1, 2, 3

# ── Colours ───────────────────────────────────────────────────────────────────
C_GRASS        = (75, 155, 65);  C_GRASS_D      = (60, 135, 50)
C_BG           = (30, 30, 30)
C_PLAYER       = (80, 160, 255); C_PLAYER_DODGE = (180, 220, 255)
C_EYE          = (220, 240, 255); C_SHADOW      = (15, 25, 15)
C_SWORD        = (210, 210, 230); C_SHIELD       = (190, 150, 60)
C_MELEE        = (220, 80, 80);   C_RANGED       = (180, 80, 210)
C_ARROW        = (190, 150, 80)

# ── Tree palette (used by map_gen and forest) ─────────────────────────────────
TREE_PALETTE = [
    ((100, 65, 30), (45, 130, 40),  (30, 100, 25)),
    ((90,  55, 25), (55, 145, 35),  (35, 110, 20)),
    ((110, 70, 35), (35, 110, 50),  (20,  85, 35)),
    ((95,  60, 28), (80, 130, 30),  (60, 100, 15)),
]

# ── Save data ─────────────────────────────────────────────────────────────────
DEFAULT_SAVE = {
    "main_hand":          "sword",
    "off_hand":           None,
    "inventory_weapons":  ["sword"],
    "inventory_shields":  [],
    "highest_floor":      0,
    "items":              [],
    "item_charges":       {},
    "active_effects": {
        "invis":       0,
        "fire_potion": 0,
    },
}

def load_save():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE) as f:
                d = json.load(f)
            # Migrate old save format
            if "weapon" in d and "main_hand" not in d:
                d["main_hand"] = "sword"
                d["off_hand"]  = "wooden_shield"
                d["inventory_weapons"] = ["sword"]
                d["inventory_shields"] = ["wooden_shield"]
                del d["weapon"]
            for k, v in DEFAULT_SAVE.items():
                if k not in d:
                    d[k] = copy.deepcopy(v)
            return d
        except:
            pass
    return copy.deepcopy(DEFAULT_SAVE)

def save_game(save):
    with open(SAVE_FILE, "w") as f:
        json.dump(save, f, indent=2)

def reset_save():
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)

# ── Stat helpers ──────────────────────────────────────────────────────────────
def get_max_hp(save):       return BASE_HP
def get_max_stamina(save):  return BASE_STAMINA
def get_bonus_damage(save): return 0.0
def get_bonus_dodge(save):  return 0.0