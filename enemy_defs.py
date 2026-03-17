# enemy_defs.py - Data-driven enemy definitions
# Single source of truth for all enemy stats and AI parameters.
# Adding a new enemy = adding a new dict entry.
# Tweaking an enemy = changing a number.

ENEMIES = {
    "wolf": {
        "name":        "Wolf",
        "hp_mult":     0.8,
        "speed_mult":  1.1,
        "radius":      13,
        "aggro_range": 200,
        "kb_mult":     0.4,
        "exp":         15,       # knockback received multiplier
        "color":       (160, 130, 60),  # base color (glow modifies it)
        "ai":          "wolf",

        # Wolf AI parameters
        "standoff_dist":   180,
        "windup_frames":   30,
        "dash_frames":     28,
        "dash_speed_mult": 1.9,    # multiplier on DODGE_SPEED
        "recovery_frames": 100,
        "damage_mult":     1.2,    # multiplier on ENEMY_MELEE_DAMAGE
    },

    "melee": {
        "name":        "Melee",
        "hp_mult":     1.0,
        "speed_mult":  1.0,
        "radius":      14,
        "aggro_range": 260,
        "kb_mult":     1.0,
        "exp":         12,
        "gold_chance": 0.20,
        "gold_range":  (2, 5),
        "color":       None,       # uses C_MELEE constant
        "ai":          "melee",

        # Melee AI parameters
        "reach":           48,
        "attack_cooldown": 90,
        "windup_frames":   6,
        "anim_frames":     20,
    },

    "ranged": {
        "name":        "Ranged",
        "hp_mult":     1.0,
        "speed_mult":  1.0,
        "radius":      14,
        "aggro_range": 260,
        "kb_mult":     1.0,
        "exp":         18,
        "gold_chance": 0.20,
        "gold_range":  (2, 5),
        "color":       None,       # uses C_RANGED constant
        "ai":          "ranged",

        # Ranged AI parameters
        "flee_dist":       130,
        "target_dist":     240,
        "aim_frames":      35,
        "salvo_size":      3,
        "salvo_interval":  8,
    },

    "iron_warden": {
        "name":        "The Iron Warden",
        "hp_mult":     2.5,
        "speed_mult":  0.85,
        "radius":      18,
        "aggro_range": 280,
        "kb_mult":     0.5,       # hard to knock back
        "exp":         40,
        "gold_chance": 0,         # drops key instead
        "loot_item":   "rusted_key",
        "color":       (85, 95, 105),
        "ai":          "melee",

        # Melee AI parameters
        "reach":           52,
        "attack_cooldown": 80,
        "windup_frames":   8,
        "anim_frames":     22,
    },
}


def get_enemy(name):
    """Get enemy definition by key. Returns melee as fallback."""
    return ENEMIES.get(name, ENEMIES["melee"])
