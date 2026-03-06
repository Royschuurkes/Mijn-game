# sound.py - Procedurally generated sound effects
import pygame
import math
import random

SAMPLE_RATE = 44100


def _make_sound(samples):
    import numpy as np
    int_s  = np.array([max(-32767, min(32767, int(s * 32767))) for s in samples], dtype=np.int16)
    stereo = np.column_stack([int_s, int_s])
    return pygame.sndarray.make_sound(stereo)


def _sine(freq, duration, volume=0.5, decay=True):
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        decay_factor = (1.0 - i / n) if decay else 1.0
        samples.append(math.sin(2 * math.pi * freq * t) * volume * decay_factor)
    return samples


def _noise(duration, volume=0.3, decay=True):
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        decay_factor = (1.0 - i / n) if decay else 1.0
        samples.append(random.uniform(-1.0, 1.0) * volume * decay_factor)
    return samples


def _mix(*lists):
    length = max(len(l) for l in lists)
    result = []
    for i in range(length):
        s = sum(l[i] if i < len(l) else 0.0 for l in lists)
        result.append(max(-1.0, min(1.0, s)))
    return result


def _sweep(freq_start, freq_end, duration, volume=0.5, decay=True):
    n = int(SAMPLE_RATE * duration)
    samples = []
    phase = 0.0
    for i in range(n):
        t = i / n
        freq = freq_start + (freq_end - freq_start) * t
        decay_factor = (1.0 - t) if decay else 1.0
        phase += 2 * math.pi * freq / SAMPLE_RATE
        samples.append(math.sin(phase) * volume * decay_factor)
    return samples


# ── Sound generators ──────────────────────────────────────────────────────────

def _gen_sword_swing_1():
    """Step 1 — lower pitch, medium weight."""
    sweep = _sweep(650, 160, 0.18, volume=0.4)
    noise = _noise(0.18, volume=0.22)
    return _mix(sweep, noise)

def _gen_sword_swing_2():
    """Step 2 — higher pitch, snappier."""
    sweep = _sweep(900, 230, 0.16, volume=0.42)
    noise = _noise(0.16, volume=0.20)
    return _mix(sweep, noise)

def _gen_sword_miss():
    """Soft whoosh when swing hits nothing."""
    sweep = _sweep(380, 90, 0.14, volume=0.18)
    noise = _noise(0.12, volume=0.10)
    return _mix(sweep, noise)

def _gen_sword_hit():
    clang         = _sweep(600, 300, 0.12, volume=0.5)
    impact        = _noise(0.08, volume=0.5)
    pad           = [0.0] * int(SAMPLE_RATE * 0.04)
    impact_padded = pad + impact
    return _mix(clang, impact_padded[:len(clang)])

def _gen_player_hit():
    thud  = _sweep(180, 80, 0.25, volume=0.6)
    noise = _noise(0.2, volume=0.55)
    return _mix(thud, noise)

def _gen_dodge():
    sweep = _sweep(500, 250, 0.12, volume=0.3)
    noise = _noise(0.10, volume=0.15)
    return _mix(sweep, noise)

def _gen_shield_block():
    clang1   = _sine(900, 0.06, volume=0.5)
    clang2   = _sine(1200, 0.04, volume=0.3)
    pad      = [0.0] * int(SAMPLE_RATE * 0.01)
    clang2_p = pad + clang2
    return _mix(clang1, clang2_p[:len(clang1)])

def _gen_enemy_death():
    sweep = _sweep(400, 60, 0.3, volume=0.5)
    noise = _noise(0.25, volume=0.6)
    return _mix(sweep, noise)

def _gen_boss_death():
    sweep1   = _sweep(300, 50,  0.5, volume=0.5)
    sweep2   = _sweep(500, 100, 0.4, volume=0.4)
    noise    = _noise(0.5, volume=0.65)
    pad      = [0.0] * int(SAMPLE_RATE * 0.05)
    sweep2_p = pad + sweep2
    return _mix(sweep1, sweep2_p[:len(sweep1)], noise)

def _gen_fountain():
    samples = []
    for freq in [800, 1000, 1200, 900, 1100]:
        s     = _sine(freq, 0.06, volume=0.25)
        pause = [0.0] * int(SAMPLE_RATE * 0.04)
        samples += s + pause
    return samples

def _gen_level_up():
    tones = []
    for freq in [400, 500, 600, 800]:
        tone  = _sine(freq, 0.1, volume=0.4)
        pause = [0.0] * int(SAMPLE_RATE * 0.02)
        tones += tone + pause
    return tones

def _gen_phase2():
    thud1  = _sine(55,  0.25, volume=0.9, decay=False)
    thud2  = _sine(80,  0.15, volume=0.6, decay=True)
    noise  = _noise(0.08, volume=0.3)
    sweep  = _sweep(200, 600, 0.4, volume=0.5)
    base   = _mix(thud1, thud2[:len(thud1)])
    base   = _mix(base, noise[:len(base)])
    extra  = [0.0] * int(SAMPLE_RATE * 0.1) + sweep
    return _mix(base, extra[:len(base)])

def _gen_finisher_charge():
    sweep = _sweep(300, 900, 0.18, volume=0.35, decay=False)
    noise = _noise(0.18, volume=0.12)
    return _mix(sweep, noise[:len(sweep)])

def _gen_footstep():
    noise = _noise(0.05, volume=0.12)
    thud  = _sine(120, 0.05, volume=0.1)
    return _mix(noise, thud)


# ── Sound manager ─────────────────────────────────────────────────────────────

class SoundManager:
    def __init__(self):
        print("Loading sounds...")
        self.sounds = {
            "sword_swing_1":   _make_sound(_gen_sword_swing_1()),
            "sword_swing_2":   _make_sound(_gen_sword_swing_2()),
            "sword_miss":      _make_sound(_gen_sword_miss()),
            "sword_hit":       _make_sound(_gen_sword_hit()),
            "player_hit":      _make_sound(_gen_player_hit()),
            "dodge":           _make_sound(_gen_dodge()),
            "shield_block":    _make_sound(_gen_shield_block()),
            "enemy_death":     _make_sound(_gen_enemy_death()),
            "boss_death":      _make_sound(_gen_boss_death()),
            "fountain":        _make_sound(_gen_fountain()),
            "phase2":          _make_sound(_gen_phase2()),
            "finisher_charge": _make_sound(_gen_finisher_charge()),
            "level_up":        _make_sound(_gen_level_up()),
            "footstep":        _make_sound(_gen_footstep()),
        }
        volumes = {
            "sword_swing_1":   0.55,
            "sword_swing_2":   0.65,
            "sword_miss":      0.30,
            "sword_hit":       0.8,
            "player_hit":      0.9,
            "dodge":           0.5,
            "shield_block":    0.7,
            "enemy_death":     0.7,
            "boss_death":      1.0,
            "fountain":        0.6,
            "phase2":          1.0,
            "finisher_charge": 0.5,
            "level_up":        0.8,
            "footstep":        0.5,
        }
        for name, vol in volumes.items():
            self.sounds[name].set_volume(vol)
        self.cooldowns = {}
        self.cooldown_duration = {"footstep": 18, "sword_miss": 8}
        print("Sounds loaded!")

    def play(self, name):
        if name not in self.sounds:
            return
        cd = self.cooldown_duration.get(name, 0)
        if cd > 0:
            if self.cooldowns.get(name, 0) > 0:
                return
            self.cooldowns[name] = cd
        self.sounds[name].play()

    def update(self):
        for name in list(self.cooldowns.keys()):
            self.cooldowns[name] -= 1
            if self.cooldowns[name] <= 0:
                del self.cooldowns[name]


# ── Module-level interface ────────────────────────────────────────────────────
_manager = None

def init_sound():
    global _manager
    pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
    pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
    _manager = SoundManager()

def play(name):
    if _manager:
        _manager.play(name)

def update():
    if _manager:
        _manager.update()