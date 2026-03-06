# weapons.py - Weapon definitions
# Single source of truth for all weapon values.
# The player currently uses sword + shield.
# Add new weapons here when expanding the combat system.

WEAPONS = {
    "shield": {
        "name":            "Wooden Shield",
        "type":            "shield",
        "special":         "block",
        "block_reduction": 0.70,
        "color":           (190, 150, 60),
    },
}

def get_weapon(name):
    return WEAPONS.get(name, WEAPONS["shield"])