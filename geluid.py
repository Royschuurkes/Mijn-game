# geluid.py - Procedureel gegenereerde geluidseffecten
# Geen externe bestanden nodig — alles wordt met wiskunde gemaakt!
import pygame
import math
import array
import random

SAMPLE_RATE = 44100
pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)


def _maak_geluid(samples):
    """Zet een lijst van floats (-1.0 tot 1.0) om naar een pygame Sound (stereo)."""
    int_s = [max(-32767, min(32767, int(s * 32767))) for s in samples]
    stereo = array.array('h', [v for v in int_s for _ in range(2)])
    geluid = pygame.sndarray.make_sound(stereo)
    return geluid


def _sinus(freq, duur, volume=0.5, verval=True):
    """Simpele sinusgolf met optioneel verval."""
    n = int(SAMPLE_RATE * duur)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        verval_factor = (1.0 - i/n) if verval else 1.0
        samples.append(math.sin(2 * math.pi * freq * t) * volume * verval_factor)
    return samples


def _ruis(duur, volume=0.3, verval=True):
    """Witte ruis met optioneel verval."""
    n = int(SAMPLE_RATE * duur)
    samples = []
    for i in range(n):
        verval_factor = (1.0 - i/n) if verval else 1.0
        samples.append(random.uniform(-1.0, 1.0) * volume * verval_factor)
    return samples


def _mix(*lijsten):
    """Meng meerdere sample-lijsten samen."""
    lengte = max(len(l) for l in lijsten)
    resultaat = []
    for i in range(lengte):
        s = sum(l[i] if i < len(l) else 0.0 for l in lijsten)
        resultaat.append(max(-1.0, min(1.0, s)))
    return resultaat


def _sweep(freq_start, freq_eind, duur, volume=0.5, verval=True):
    """Frequentie sweep van laag naar hoog of omgekeerd."""
    n = int(SAMPLE_RATE * duur)
    samples = []
    fase = 0.0
    for i in range(n):
        t = i / n
        freq = freq_start + (freq_eind - freq_start) * t
        verval_factor = (1.0 - t) if verval else 1.0
        fase += 2 * math.pi * freq / SAMPLE_RATE
        samples.append(math.sin(fase) * volume * verval_factor)
    return samples


# ── Geluid generatoren ────────────────────────────────────────────────────────

def _gen_zwaard_zwaai():
    """Whoosh geluid — sweep van hoog naar laag met ruis."""
    sweep = _sweep(800, 200, 0.18, volume=0.4)
    ruis  = _ruis(0.18, volume=0.25)
    return _mix(sweep, ruis)


def _gen_zwaard_hit():
    """Metaalklank — korte hoge toon + impact ruis."""
    klang = _sweep(600, 300, 0.12, volume=0.5)
    impact = _ruis(0.08, volume=0.5)
    n_pad = int(SAMPLE_RATE * 0.04)  # kleine vertraging
    impact_padded = [0.0] * n_pad + impact
    return _mix(klang, impact_padded[:len(klang)])


def _gen_speler_geraakt():
    """Zware dreun — lage toon + veel ruis."""
    dreun = _sweep(180, 80, 0.25, volume=0.6)
    ruis  = _ruis(0.2, volume=0.55)
    return _mix(dreun, ruis)


def _gen_dodge():
    """Luchtige whoosh — snel, hoog naar midden."""
    sweep = _sweep(500, 250, 0.12, volume=0.3)
    ruis  = _ruis(0.10, volume=0.15)
    return _mix(sweep, ruis)


def _gen_schild_blok():
    """Metaalklank — hoge klap."""
    klang  = _sinus(900, 0.06, volume=0.5)
    klang2 = _sinus(1200, 0.04, volume=0.3)
    n_pad  = int(SAMPLE_RATE * 0.01)
    klang2_p = [0.0]*n_pad + klang2
    return _mix(klang, klang2_p[:len(klang)])


def _gen_vijand_dood():
    """Explosie-achtig — sweep omlaag + zware ruis."""
    sweep = _sweep(400, 60, 0.3, volume=0.5)
    ruis  = _ruis(0.25, volume=0.6)
    return _mix(sweep, ruis)


def _gen_baas_dood():
    """Grote explosie — langer en zwaarder."""
    sweep1 = _sweep(300, 50,  0.5, volume=0.5)
    sweep2 = _sweep(500, 100, 0.4, volume=0.4)
    ruis   = _ruis(0.5, volume=0.65)
    n_pad  = int(SAMPLE_RATE * 0.05)
    sweep2_p = [0.0]*n_pad + sweep2
    return _mix(sweep1, sweep2_p[:len(sweep1)], ruis)


def _gen_fontein():
    """Bubbelig watergeluid — meerdere hoge tonen."""
    samples = []
    for freq in [800, 1000, 1200, 900, 1100]:
        s = _sinus(freq, 0.06, volume=0.25)
        pauze = [0.0] * int(SAMPLE_RATE * 0.04)
        samples += s + pauze
    return samples


def _gen_level_up():
    """Oplopende tonen — overwinningsgeluidje."""
    tonen = []
    for freq in [400, 500, 600, 800]:
        toon = _sinus(freq, 0.1, volume=0.4)
        pauze = [0.0] * int(SAMPLE_RATE * 0.02)
        tonen += toon + pauze
    return tonen


def _gen_struik():
    """Krakend geluid voor struiken."""
    ruis = _ruis(0.08, volume=0.2)
    return ruis


def _gen_fase2():
    """Zware dreun + oplopende toon bij fase 2 overgang."""
    dreun  = _sinus(55,  0.25, volume=0.9, verval=False)
    dreun2 = _sinus(80,  0.15, volume=0.6, verval=True)
    ruis   = _ruis(0.08, volume=0.3)
    sweep  = _sweep(200, 600,  0.4, volume=0.5)
    basis  = _mix(dreun, dreun2[:len(dreun)])
    basis  = _mix(basis, ruis[:len(basis)])
    extra  = [0.0] * int(SAMPLE_RATE * 0.1) + sweep
    return _mix(basis, extra[:len(basis)])


def _gen_finisher_charge():
    """Oplaadtoon voor finisher windup — hoog en gespannen."""
    sweep = _sweep(300, 900, 0.18, volume=0.35, verval=False)
    ruis  = _ruis(0.18, volume=0.12)
    return _mix(sweep, ruis[:len(sweep)])


def _gen_stap():
    """Zachte voetstap."""
    ruis = _ruis(0.05, volume=0.12)
    dreun = _sinus(120, 0.05, volume=0.1)
    return _mix(ruis, dreun)


# ── Geluid Manager ────────────────────────────────────────────────────────────

class GeluidManager:
    def __init__(self):
        if not pygame.mixer.get_init():
            pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)

        print("Geluiden laden...")
        self.geluiden = {
            "zwaard_zwaai":   _maak_geluid(_gen_zwaard_zwaai()),
            "zwaard_hit":     _maak_geluid(_gen_zwaard_hit()),
            "speler_geraakt": _maak_geluid(_gen_speler_geraakt()),
            "dodge":          _maak_geluid(_gen_dodge()),
            "schild_blok":    _maak_geluid(_gen_schild_blok()),
            "vijand_dood":    _maak_geluid(_gen_vijand_dood()),
            "baas_dood":      _maak_geluid(_gen_baas_dood()),
            "fontein":        _maak_geluid(_gen_fontein()),
            "fase2":          _maak_geluid(_gen_fase2()),
            "finisher_charge":_maak_geluid(_gen_finisher_charge()),
            "level_up":       _maak_geluid(_gen_level_up()),
            "struik":         _maak_geluid(_gen_struik()),
            "stap":           _maak_geluid(_gen_stap()),
        }

        # Volume per geluid (0.0 tot 1.0)
        volumes = {
            "zwaard_zwaai":   0.6,
            "zwaard_hit":     0.8,
            "speler_geraakt": 0.9,
            "dodge":          0.5,
            "schild_blok":    0.7,
            "vijand_dood":    0.7,
            "baas_dood":      1.0,
            "fontein":        0.6,
            "fase2":          1.0,
            "finisher_charge":0.5,
            "level_up":       0.8,
            "struik":         0.4,
            "stap":           0.5,
        }
        for naam, vol in volumes.items():
            self.geluiden[naam].set_volume(vol)

        # Cooldowns om geluiden niet te spammen (in frames)
        self.cooldowns = {}
        self.cooldown_duur = {
            "stap":   18,
            "struik": 20,
        }
        print("Geluiden geladen!")

    def speel(self, naam, toonhoogte_variatie=0.0):
        """
        Speel een geluid af. toonhoogte_variatie voegt kleine willekeurige
        variatie toe zodat herhaalde geluiden minder robotisch klinken.
        """
        if naam not in self.geluiden:
            return

        # Cooldown check
        cd = self.cooldown_duur.get(naam, 0)
        if cd > 0:
            if self.cooldowns.get(naam, 0) > 0:
                return
            self.cooldowns[naam] = cd

        self.geluiden[naam].play()

    def update(self):
        """Tick cooldowns — roep elke frame aan."""
        for naam in list(self.cooldowns.keys()):
            self.cooldowns[naam] -= 1
            if self.cooldowns[naam] <= 0:
                del self.cooldowns[naam]


# Globale instantie — wordt eenmalig aangemaakt in main.py
_manager = None

def init_geluid():
    global _manager
    _manager = GeluidManager()

def speel(naam):
    if _manager:
        _manager.speel(naam)

def update_geluid():
    if _manager:
        _manager.update()
