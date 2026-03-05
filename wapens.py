# wapens.py - Wapen definities
# Momenteel: ridder start altijd met zwaard + schild.
# Dit bestand blijft bestaan als fundament voor toekomstige items/builds.

WAPENS = {
    "schild": {
        "naam":            "Houten Schild",
        "type":            "schild",
        "schade":          0,
        "zwaard_frames":   0,
        "bereik":          0,
        "hoek":            0,
        "zwaard_cd":       0,
        "special":         "blok",
        "special_stamina": 0,
        "blok_reductie":   0.70,
        "kleur":           (190, 150, 60),
    },
}

def get_wapen(naam):
    return WAPENS.get(naam, WAPENS["schild"])
