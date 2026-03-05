# items.py - Item definities en hulpfuncties
import random

ITEMS = {
    "fire_damage": {
        "naam":        "Vuurzwaard",
        "beschrijving": "+25% schade\n30% kans op Burning\n(3× 8 schade in 6 sec)",
        "type":        "passief",
        "rarity":      "zeldzaam",
        "kleur":       (255, 80, 20),
        "kleur_dim":   (120, 40, 10),
    },
    "bloodthirst": {
        "naam":        "Bloeddorst",
        "beschrijving": "Vijand verslaan: +8 HP",
        "type":        "passief",
        "rarity":      "gewoon",
        "kleur":       (180, 30, 50),
        "kleur_dim":   (80, 15, 25),
    },
    "berserker": {
        "naam":        "Berserker",
        "beschrijving": "Minder HP = meer schade\n(+80% schade bij bijna dood)",
        "type":        "passief",
        "rarity":      "zeldzaam",
        "kleur":       (220, 40, 40),
        "kleur_dim":   (100, 20, 20),
    },
    "invis_potion": {
        "naam":        "Onsterfelijkheidsdrankje",
        "beschrijving": "6 sec onkwetsbaar\n[Q om te gebruiken]",
        "type":        "actief",
        "rarity":      "episch",
        "kleur":       (100, 200, 255),
        "kleur_dim":   (40, 80, 120),
        "charges":     1,
        "duur":        360,   # frames
    },
    "combo_master": {
        "naam":        "Combo Meester",
        "beschrijving": "Finisher doet +50% schade",
        "type":        "passief",
        "rarity":      "zeldzaam",
        "kleur":       (255, 200, 50),
        "kleur_dim":   (120, 90, 20),
    },
    "marathon_runner": {
        "naam":        "Marathonloper",
        "beschrijving": "Sprinten kost geen stamina",
        "type":        "passief",
        "rarity":      "gewoon",
        "kleur":       (80, 200, 120),
        "kleur_dim":   (30, 80, 50),
    },
    "fire_potion": {
        "naam":        "Vuurdrankje",
        "beschrijving": "12 sec: +25% schade en Burning\n[Q om te gebruiken]",
        "type":        "actief",
        "rarity":      "gewoon",
        "kleur":       (255, 140, 40),
        "kleur_dim":   (100, 55, 15),
        "charges":     1,
        "duur":        720,   # frames
    },
    "health_potion": {
        "naam":        "Gezondheidsdrankje",
        "beschrijving": "Herstel 35 HP\n3 charges\n[Q om te gebruiken]",
        "type":        "actief",
        "rarity":      "gewoon",
        "kleur":       (60, 220, 80),
        "kleur_dim":   (25, 90, 35),
        "charges":     3,
        "heal":        35,
    },
}

RARITY_GEWICHT = {"gewoon": 55, "zeldzaam": 30, "episch": 15}
RARITY_KLEUR   = {
    "gewoon":   (160, 160, 160),
    "zeldzaam": (60,  160, 255),
    "episch":   (200,  80, 255),
}
RARITY_NAAM = {"gewoon": "Gewoon", "zeldzaam": "Zeldzaam", "episch": "Episch"}


def kies_items(n=3, bestaande_items=None, bestaande_charges=None):
    """Kies n willekeurige items, gewogen naar rarity."""
    if bestaande_items  is None: bestaande_items   = []
    if bestaande_charges is None: bestaande_charges = {}

    pool = []
    for key, item in ITEMS.items():
        # Passieve items maar 1× per run
        if item["type"] == "passief" and key in bestaande_items:
            continue
        gewicht = RARITY_GEWICHT[item["rarity"]]
        pool.extend([key] * gewicht)

    if not pool:
        return []

    gekozen = []
    kandidaten = list(pool)
    while len(gekozen) < n and kandidaten:
        k = random.choice(kandidaten)
        if k not in gekozen:
            gekozen.append(k)
        kandidaten = [c for c in kandidaten if c != k]
    return gekozen
