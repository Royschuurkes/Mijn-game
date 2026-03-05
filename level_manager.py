# level_manager.py - Beheert floor en kamer progressie (BoI-stijl)
import random
from opslaan import *

# ── Floor definities — pas hier aan om de opbouw te tweaken ─────────────────
# Elke floor heeft:
#   kamers_min/max  : hoeveel gewone gevechtskamers (random binnen range)
#   rust_na         : na hoeveel kamers een rustplaats verschijnt (0 = nooit)
#   vijanden        : lijst van vijandcomposities (random gekozen per kamer)
#   schade_mult     : hoe hard vijanden slaan op deze floor
#   hp_mult         : hoeveel HP vijanden hebben op deze floor

FLOOR_DEFINITIES = {
    1: {
        "kamers_min": 4, "kamers_max": 5,
        "rust_na": 3,
        "schade_mult": 1.0, "hp_mult": 1.0,
        # Groepen: (type, aantal, hp_mult) — spawnen geclusterd
        "vijanden": [
            [("wolf",   2, 1.0)],
            [("wolf",   3, 1.0)],
            [("wolf",   1, 1.0), ("ranged", 2, 1.0)],
            [("ranged", 2, 1.0)],
            [("wolf",   1, 1.0)],
        ],
    },
    2: {
        "kamers_min": 4, "kamers_max": 6,
        "rust_na": 3,
        "schade_mult": 1.1, "hp_mult": 1.2,
        "vijanden": [
            [("wolf",   2, 1.2), ("ranged", 1, 1.0)],
            [("wolf",   1, 1.2), ("ranged", 2, 1.0)],
            [("ranged", 3, 1.2)],
            [("wolf",   3, 1.2)],
        ],
    },
    3: {
        "kamers_min": 5, "kamers_max": 7,
        "rust_na": 4,
        "schade_mult": 1.2, "hp_mult": 1.5,
        "vijanden": [
            [("wolf",   3, 1.5), ("ranged", 1, 1.2)],
            [("wolf",   1, 1.5), ("ranged", 3, 1.2)],
            [("ranged", 2, 1.5), ("wolf",   2, 1.5)],
            [("wolf",   4, 1.5)],
        ],
    },
    4: {
        "kamers_min": 5, "kamers_max": 8,
        "rust_na": 4,
        "schade_mult": 1.4, "hp_mult": 1.8,
        "vijanden": [
            [("wolf",   2, 1.8), ("ranged", 2, 1.5)],
            [("ranged", 4, 1.8)],
            [("wolf",   3, 2.0), ("ranged", 1, 1.5)],
        ],
    },
}

MAX_FLOOR = max(FLOOR_DEFINITIES.keys())


def _floor_def(floor_nr):
    """Geeft floor definitie terug, na max_floor steeds zwaarder."""
    if floor_nr <= MAX_FLOOR:
        return FLOOR_DEFINITIES[floor_nr]
    # Na de laatste floor: herhaal laatste met oplopende schaling
    extra = 0.3 * (floor_nr - MAX_FLOOR)
    base = FLOOR_DEFINITIES[MAX_FLOOR]
    return {
        "kamers_min": base["kamers_min"],
        "kamers_max": base["kamers_max"],
        "rust_na":    base["rust_na"],
        "schade_mult": round(base["schade_mult"] + extra, 2),
        "hp_mult":    round(base["hp_mult"]     + extra, 2),
        "vijanden":   base["vijanden"],
    }



# Richtingen voor de kamergraph
TEGENOVER       = {"N":"S", "S":"N", "E":"W", "W":"E"}
RICHTING_DELTA  = {"E":(1,0), "W":(-1,0), "N":(0,-1), "S":(0,1)}


def genereer_floor_graph(floor_nr):
    fd = _floor_def(floor_nr)
    n_kamers = random.randint(fd["kamers_min"], fd["kamers_max"])

    grid     = {(0,0): True}
    volgorde = [(0,0)]
    frontier = [(0,0)]

    pogingen = 0
    while len(grid) < n_kamers and pogingen < 300:
        pogingen += 1
        if not frontier: break
        basis = random.choice(frontier)
        dirs  = list(RICHTING_DELTA.keys())
        random.shuffle(dirs)
        uitgebreid = False
        for r in dirs:
            dr, dc = RICHTING_DELTA[r]
            nieuw = (basis[0]+dr, basis[1]+dc)
            if nieuw not in grid:
                grid[nieuw] = True
                volgorde.append(nieuw)
                frontier.append(nieuw)
                uitgebreid = True
                break
        if not uitgebreid:
            frontier.remove(basis)

    # Start = eerste, Baas = laatste, Rust = ergens in het midden
    baas_pos = volgorde[-1]
    midden_kandidaten = volgorde[1:-1]
    rust_pos = random.choice(midden_kandidaten) if midden_kandidaten else None

    kamer_graph = {}
    for pos in volgorde:
        gx, gy = pos
        deuren = set(); buren = {}
        for r, (dr, dc) in RICHTING_DELTA.items():
            buur = (gx+dr, gy+dc)
            if buur in grid:
                deuren.add(r); buren[r] = buur

        if pos == baas_pos:
            ktype = "baas"
            hp    = round(fd["hp_mult"] * (1.0 + floor_nr * 0.2), 2)
            vijanden = [("baas", 1, hp)]   # groep van 1 baas
        elif pos == rust_pos:
            ktype = "rust"; vijanden = []
        else:
            ktype = "gevecht"
            comp  = random.choice(fd["vijanden"])
            # Nieuw formaat: (type, aantal, hp_mult) per groep
            vijanden = [(t, n, round(h * fd["hp_mult"], 2)) for t, n, h in comp]

        kamer_graph[pos] = {
            "type":             ktype,
            "deuren":           deuren,
            "buren":            buren,
            "vijanden_config":  vijanden,
            "schade_mult":      fd["schade_mult"],
            "gecleared":        ktype == "rust",
            "bezocht":          False,
            "fontein_gebruikt": False,
            "item_gepakt":      False,   # item al opgepakt in rustkamer
            "kaart_data":       None,
        }

    return kamer_graph, volgorde[0]


class LevelManager:
    def __init__(self):
        self.floor_nr = 1
        # kamer/is_* worden door BosScene bijgehouden via huidige kamer
        self.kamer = "gevecht"

    def volgende_floor(self):
        self.floor_nr += 1

    @property
    def is_rust(self):    return self.kamer == "rust"
    @property
    def is_baas(self):    return self.kamer == "baas"
    @property
    def is_gevecht(self): return self.kamer == "gevecht"

    def omschrijving(self, kamer_nr=None, totaal=None):
        if self.is_rust:  return f"Floor {self.floor_nr}  â  Rustplaats"
        if self.is_baas:  return f"Floor {self.floor_nr}  â  EINDBAAS!"
        if kamer_nr and totaal:
            return f"Floor {self.floor_nr}  â  Kamer {kamer_nr}/{totaal}"
        return f"Floor {self.floor_nr}"
