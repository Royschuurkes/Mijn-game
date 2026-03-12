# weapons.py - Weapon and shield definitions
# Single source of truth for all weapon/shield values.
# Every value is individually tunable per weapon and per combo step.
#
# Combo structure:
#   Each weapon has a "combo" list — one entry per hit in the combo chain.
#   The LAST entry is always the finisher (has "windup" key).
#   All values are per-step so you can fine-tune each hit independently.
#
# Per-step keys:
#   swing_frames - how long the active swing lasts (frames)
#   cooldown     - minimum frames before next swing input is accepted
#   window       - frames after swing where the next combo input is accepted
#   arc          - total sweep angle in degrees (0 = thrust)
#   tolerance    - hit detection angle tolerance
#   damage_mult  - multiplier on the weapon's base damage for this step
#   reach_mult   - optional reach multiplier for this step (default 1.0)
#   windup       - frames of charge-up before the finisher fires (finisher only)
#   knockback_mult - optional knockback multiplier for this step (default 1.0)
#
# Animation types:
#   "sweep_right" - arc swing from left to right
#   "sweep_left"  - arc swing from right to left
#   "thrust"      - straight stab forward
#   "wide_sweep"  - very wide arc
#   "overhead"    - overhead smash (narrow but heavy)
#   "stab"        - quick narrow stab forward

WEAPONS = {
    "sword": {
        "name":              "Iron Sword",
        "type":              "melee",
        "damage":            25.0,
        "reach":             88,
        "knockback":         10.0,
        "stamina_cost":      14,
        "charge_damage_mult": 1.4,
        "color":             (210, 210, 230),
        "color_tip":         (240, 240, 255),
        "combo": [
            {   # Step 1: slash right
                "anim": "sweep_right",
                "swing_frames": 10, "cooldown": 18, "window": 28,
                "arc": 120, "tolerance": 42, "damage_mult": 1.0,
            },
            {   # Step 2: slash left
                "anim": "sweep_left",
                "swing_frames": 10, "cooldown": 18, "window": 28,
                "arc": 120, "tolerance": 42, "damage_mult": 1.0,
            },
            {   # Step 3: finisher thrust
                "anim": "thrust",
                "swing_frames": 10, "cooldown": 22, "window": 0,
                "arc": 0, "tolerance": 28, "damage_mult": 2.5,
                "windup": 16, "reach_mult": 1.3, "knockback_mult": 1.5,
            },
        ],
    },

    "dagger": {
        "name":              "Steel Dagger",
        "type":              "melee",
        "damage":            14.0,
        "reach":             50,
        "knockback":         5.0,
        "stamina_cost":      8,
        "charge_damage_mult": 1.2,
        "color":             (180, 190, 200),
        "color_tip":         (220, 230, 240),
        "combo": [
            {   # Step 1: quick stab
                "anim": "stab",
                "swing_frames": 6, "cooldown": 10, "window": 20,
                "arc": 40, "tolerance": 35, "damage_mult": 1.0,
            },
            {   # Step 2: quick stab
                "anim": "stab",
                "swing_frames": 6, "cooldown": 10, "window": 20,
                "arc": 40, "tolerance": 35, "damage_mult": 1.0,
            },
            {   # Step 3: quick stab
                "anim": "stab",
                "swing_frames": 6, "cooldown": 10, "window": 20,
                "arc": 40, "tolerance": 35, "damage_mult": 1.1,
            },
            {   # Step 4: quick stab
                "anim": "stab",
                "swing_frames": 6, "cooldown": 10, "window": 20,
                "arc": 40, "tolerance": 35, "damage_mult": 1.2,
            },
            {   # Step 5: finisher cross-slash
                "anim": "sweep_right",
                "swing_frames": 8, "cooldown": 16, "window": 0,
                "arc": 100, "tolerance": 40, "damage_mult": 2.0,
                "windup": 8, "reach_mult": 1.2, "knockback_mult": 1.3,
            },
        ],
    },

    "axe": {
        "name":              "War Axe",
        "type":              "melee",
        "damage":            40.0,
        "reach":             100,
        "knockback":         16.0,
        "stamina_cost":      22,
        "charge_damage_mult": 1.6,
        "color":             (160, 140, 120),
        "color_tip":         (200, 180, 150),
        "combo": [
            {   # Step 1: wide sweep
                "anim": "wide_sweep",
                "swing_frames": 14, "cooldown": 24, "window": 34,
                "arc": 160, "tolerance": 50, "damage_mult": 1.0,
                "knockback_mult": 1.3,
            },
            {   # Step 2: finisher overhead smash
                "anim": "overhead",
                "swing_frames": 14, "cooldown": 28, "window": 0,
                "arc": 60, "tolerance": 35, "damage_mult": 3.0,
                "windup": 24, "reach_mult": 1.15, "knockback_mult": 2.0,
            },
        ],
    },
}


SHIELDS = {
    "wooden_shield": {
        "name":               "Wooden Shield",
        "type":               "shield",
        "block_reduction":    0.70,
        "stamina_cost":       12.0,
        "stamina_cost_arrow": 8.0,
        "parry_window":       12,
        "parry_stagger":      60,
        "color":              (190, 150, 60),
        "color_rim":          (230, 185, 90),
    },
}


def get_weapon(name):
    """Get a melee weapon by key. Returns sword as fallback."""
    return WEAPONS.get(name, WEAPONS["sword"])


def get_shield(name):
    """Get a shield by key. Returns None if name is None or not found."""
    if name is None:
        return None
    return SHIELDS.get(name)


def combo_step_data(weapon, step):
    """Get the combo data for a specific step (1-indexed).
    Returns the last step's data if step exceeds combo length."""
    combo = weapon["combo"]
    idx = min(step - 1, len(combo) - 1)
    return combo[max(0, idx)]


def combo_length(weapon):
    """Total number of hits in this weapon's combo chain."""
    return len(weapon["combo"])


def is_finisher(weapon, step):
    """True if this step is the finisher (last hit in the combo)."""
    return step == len(weapon["combo"])
