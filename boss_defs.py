# boss_defs.py - Data-driven boss definitions
# Single source of truth for all boss stats, attack patterns, and phase transitions.
# Adding a new boss = adding a new dict entry.
# Tweaking a boss = changing a number.

from constants import DODGE_SPEED

BOSSES = {
    "forest_warrior": {
        "name":       "The Forest Warrior",
        "hp":         700.0,
        "radius":     32,
        "speed":      1.6,
        "color_p1":   (55, 90, 45),
        "color_p2":   (110, 30, 20),
        "color_eye":  (200, 80, 255),

        # Phase 2
        "phase2_threshold":   0.5,     # HP ratio to trigger phase 2
        "phase2_speed_mult":  1.3,     # speed multiplier in phase 2
        "phase2_windup_mult": 0.8,     # windup becomes faster
        "phase2_cd_mult":     0.75,    # cooldowns become shorter

        # Attacks
        "attacks": {
            "melee": {
                "windup":   30,
                "frames":   20,
                "cooldown": 70,          # snelle jab, korte cooldown
                "damage":   35.0,
                "reach":    120,
                "recovery": 30,          # kort punish window (1-2 hits)
            },
            "charge": {
                "windup":     38,
                "duration":   22,
                "cooldown":   120,       # gemiddelde cooldown
                "damage":     28.0,
                "speed":      DODGE_SPEED * 2.2,
                "recovery":   45,        # gemiddeld punish (2-3 hits)
            },
            "stamp": {
                "windup":     30,
                "active":     10,
                "cooldown":   180,       # langere cooldown
                "damage":     30.0,
                "max_radius": 180,
                "ring_speed": 4.5,
                "recovery":   55,        # groot punish window (3 hits)
            },
            "jump": {
                "windup":       30,      # crouch before jumping
                "airtime":      45,      # frames in the air
                "land_damage":  45.0,    # high damage on hit
                "land_radius":  70,      # AoE radius at landing
                "stun_duration": 70,     # grootste punish window (3-4 hits)
                "cooldown":     220,
                "shadow_grow":  0.8,
            },
        },

        # Attack selection weights (checked in order)
        "attack_priority": [
            {"attack": "jump",   "min_range": 120, "weight": 0.35},
            {"attack": "stamp",  "min_range": 180, "weight": 0.4},
            {"attack": "charge", "min_range": 130, "weight": 0.45},
            {"attack": "melee",  "min_range": 0,   "weight": 1.0},
        ],
    },
}


def get_boss(name):
    """Get boss definition by key. Returns forest_warrior as fallback."""
    return BOSSES.get(name, BOSSES["forest_warrior"])
