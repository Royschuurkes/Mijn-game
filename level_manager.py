# level_manager.py - Beheert level progressie en kamer types
import random
from opslaan import *


def kamer_type(level_nr):
    """Bepaal het type kamer op basis van het level nummer."""
    if level_nr == 1:
        return "gevecht"
    if level_nr % 5 == 0:
        return "baas"
    if level_nr % 3 == 0:
        return "rust"
    return "gevecht"


def vijand_config(level_nr, kamer):
    """
    Geeft een lijst van (type, hp_multiplier) terug voor de vijanden in dit level.
    """
    if kamer == "rust":
        return []

    if kamer == "baas":
        # Één grote baas
        hp_mult = 1.0 + (level_nr * 0.3)
        return [("baas", hp_mult)]

    # Normaal gevecht: schaal aantal en sterkte met level
    basis_aantal = min(3 + level_nr, 12)
    hp_mult = 1.0 + (level_nr - 1) * 0.15

    vijanden = []
    for _ in range(basis_aantal):
        # Meer ranged vijanden op hogere levels
        ranged_kans = min(0.2 + level_nr * 0.04, 0.5)
        t = "ranged" if random.random() < ranged_kans else "melee"
        vijanden.append((t, hp_mult))

    return vijanden


def schade_multiplier(level_nr):
    """Vijanden doen meer schade op hogere levels."""
    return 1.0 + (level_nr - 1) * 0.1


class LevelManager:
    def __init__(self):
        self.level_nr = 1
        self.kamer = kamer_type(1)
        self.vijanden_config = vijand_config(1, self.kamer)
        self.schade_mult = schade_multiplier(1)

    def volgende_level(self):
        self.level_nr += 1
        self.kamer = kamer_type(self.level_nr)
        self.vijanden_config = vijand_config(self.level_nr, self.kamer)
        self.schade_mult = schade_multiplier(self.level_nr)

    @property
    def is_rust(self):   return self.kamer == "rust"
    @property
    def is_baas(self):   return self.kamer == "baas"
    @property
    def is_gevecht(self): return self.kamer == "gevecht"

    def omschrijving(self):
        if self.is_rust:  return f"Kamer {self.level_nr} — Rustplaats"
        if self.is_baas:  return f"Kamer {self.level_nr} — EINDBAAS!"
        return f"Kamer {self.level_nr}"
