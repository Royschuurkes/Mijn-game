# items.py - Item definitions and helpers
import random

ITEMS = {
    "fire_damage": {
        "name":        "Fire Sword",
        "description": "+25% damage\n30% chance to Burn\n(3x 8 damage over 6 sec)",
        "type":        "passive",
        "rarity":      "rare",
        "color":       (255, 80, 20),
        "color_dim":   (120, 40, 10),
    },
    "bloodthirst": {
        "name":        "Bloodthirst",
        "description": "Kill an enemy: +8 HP",
        "type":        "passive",
        "rarity":      "common",
        "color":       (180, 30, 50),
        "color_dim":   (80, 15, 25),
    },
    "berserker": {
        "name":        "Berserker",
        "description": "Lower HP = more damage\n(+80% near death)",
        "type":        "passive",
        "rarity":      "rare",
        "color":       (220, 40, 40),
        "color_dim":   (100, 20, 20),
    },
    "invis_potion": {
        "name":        "Immortality Potion",
        "description": "6 sec invulnerable\n[Q to use]",
        "type":        "active",
        "rarity":      "epic",
        "color":       (100, 200, 255),
        "color_dim":   (40, 80, 120),
        "charges":     1,
        "duration":    360,
    },
    "combo_master": {
        "name":        "Combo Master",
        "description": "Finisher deals +50% damage",
        "type":        "passive",
        "rarity":      "rare",
        "color":       (255, 200, 50),
        "color_dim":   (120, 90, 20),
    },
    "marathon_runner": {
        "name":        "Marathon Runner",
        "description": "Sprinting costs no stamina",
        "type":        "passive",
        "rarity":      "common",
        "color":       (80, 200, 120),
        "color_dim":   (30, 80, 50),
    },
    "fire_potion": {
        "name":        "Fire Potion",
        "description": "12 sec: +25% damage and Burn\n[Q to use]",
        "type":        "active",
        "rarity":      "common",
        "color":       (255, 140, 40),
        "color_dim":   (100, 55, 15),
        "charges":     1,
        "duration":    720,
    },
    "health_potion": {
        "name":        "Health Potion",
        "description": "Restore 35 HP\n3 charges\n[Q to use]",
        "type":        "active",
        "rarity":      "common",
        "color":       (60, 220, 80),
        "color_dim":   (25, 90, 35),
        "charges":     3,
        "heal":        35,
    },
}

RARITY_WEIGHT = {"common": 55, "rare": 30, "epic": 15}
RARITY_COLOR  = {
    "common": (160, 160, 160),
    "rare":   (60,  160, 255),
    "epic":   (200,  80, 255),
}
RARITY_NAME = {"common": "Common", "rare": "Rare", "epic": "Epic"}


def pick_items(n=3, existing_items=None, existing_charges=None):
    """Pick n random items, weighted by rarity."""
    if existing_items   is None: existing_items   = []
    if existing_charges is None: existing_charges = {}

    pool = []
    for key, item in ITEMS.items():
        if item["type"] == "passive" and key in existing_items:
            continue
        weight = RARITY_WEIGHT[item["rarity"]]
        pool.extend([key] * weight)

    if not pool:
        return []

    chosen     = []
    candidates = list(pool)
    while len(chosen) < n and candidates:
        k = random.choice(candidates)
        if k not in chosen:
            chosen.append(k)
        candidates = [c for c in candidates if c != k]
    return chosen
