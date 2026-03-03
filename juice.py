# juice.py - Alle visuele "feel" effecten
import math, random
import pygame


# ── Screen Shake ──────────────────────────────────────────────────────────────
class ScreenShake:
    def __init__(self):
        self.timer = 0
        self.kracht = 0

    def start(self, kracht=6, duur=12):
        if kracht > self.kracht:
            self.kracht = kracht
            self.timer = duur

    def update(self):
        if self.timer > 0:
            self.timer -= 1
            verval = self.timer / 12
            ox = random.randint(-1,1) * int(self.kracht * verval)
            oy = random.randint(-1,1) * int(self.kracht * verval)
            if self.timer == 0: self.kracht = 0
            return ox, oy
        return 0, 0


# ── Freeze Frames ─────────────────────────────────────────────────────────────
class FreezeFrames:
    def __init__(self):
        self.timer = 0

    def start(self, frames=2):
        self.timer = max(self.timer, frames)

    def update(self):
        """Geeft True terug als het spel bevroren is."""
        if self.timer > 0:
            self.timer -= 1
            return True
        return False


# ── Particle ──────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, dx, dy, kleur, leven, radius=3, zwaartekracht=0.0):
        self.x = float(x); self.y = float(y)
        self.dx = dx; self.dy = dy
        self.kleur = kleur
        self.max_leven = leven
        self.leven = leven
        self.radius = radius
        self.zwaartekracht = zwaartekracht

    def update(self):
        self.x += self.dx
        self.y += self.dy
        self.dy += self.zwaartekracht
        self.dx *= 0.92
        self.dy *= 0.92
        self.leven -= 1
        return self.leven > 0

    def teken(self, surface, cam_x, cam_y):
        alpha = self.leven / self.max_leven
        r = max(1, int(self.radius * alpha))
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        # Vervaag kleur richting zwart
        kl = tuple(int(c * alpha) for c in self.kleur)
        pygame.draw.circle(surface, kl, (sx, sy), r)


# ── Particle Systeem ──────────────────────────────────────────────────────────
class PartikelSysteem:
    def __init__(self):
        self.deeltjes = []

    def update(self):
        self.deeltjes = [p for p in self.deeltjes if p.update()]

    def teken(self, surface, cam_x, cam_y):
        for p in self.deeltjes:
            p.teken(surface, cam_x, cam_y)

    def zwaard_vonken(self, x, y, richting_hoek):
        """Vonkjes bij een zwaardtreffer."""
        for _ in range(12):
            spread = random.uniform(-40, 40)
            hoek = math.radians(richting_hoek + spread)
            snelheid = random.uniform(2.5, 6.0)
            dx = math.cos(hoek) * snelheid
            dy = math.sin(hoek) * snelheid
            kl = random.choice([
                (255, 240, 100), (255, 200, 50),
                (255, 255, 200), (220, 180, 50)
            ])
            self.deeltjes.append(Particle(x, y, dx, dy, kl,
                leven=random.randint(10,20), radius=random.randint(2,4),
                zwaartekracht=0.15))

    def bloed_spat(self, x, y, richting_hoek):
        """Rode druppels bij schade aan speler."""
        for _ in range(10):
            spread = random.uniform(-60, 60)
            hoek = math.radians(richting_hoek + spread)
            snelheid = random.uniform(1.5, 4.5)
            dx = math.cos(hoek) * snelheid
            dy = math.sin(hoek) * snelheid
            kl = random.choice([
                (220, 30, 30), (180, 20, 20),
                (255, 60, 60), (200, 40, 40)
            ])
            self.deeltjes.append(Particle(x, y, dx, dy, kl,
                leven=random.randint(14,24), radius=random.randint(2,4),
                zwaartekracht=0.12))

    def dood_explosie(self, x, y, kleur):
        """Grote burst als vijand sterft."""
        for _ in range(25):
            hoek = random.uniform(0, math.pi*2)
            snelheid = random.uniform(2.0, 7.0)
            dx = math.cos(hoek) * snelheid
            dy = math.sin(hoek) * snelheid
            kl = random.choice([kleur,
                (255, 255, 200), (255, 200, 50), (255, 100, 50)])
            self.deeltjes.append(Particle(x, y, dx, dy, kl,
                leven=random.randint(20,35), radius=random.randint(3,6),
                zwaartekracht=0.08))
        # Grotere witte flash-deeltjes
        for _ in range(8):
            hoek = random.uniform(0, math.pi*2)
            snelheid = random.uniform(1.0, 3.0)
            dx = math.cos(hoek) * snelheid
            dy = math.sin(hoek) * snelheid
            self.deeltjes.append(Particle(x, y, dx, dy, (255,255,255),
                leven=10, radius=random.randint(4,8), zwaartekracht=0))

    def dodge_spoor(self, x, y, kleur=(100, 160, 255)):
        """Eén afterimage-deeltje voor dodge trail."""
        self.deeltjes.append(Particle(x, y, 0, 0, kleur,
            leven=10, radius=14, zwaartekracht=0))


# ── Floating Damage Numbers ───────────────────────────────────────────────────
class SchadeCijfer:
    def __init__(self, x, y, tekst, kleur, groot=False):
        self.x = float(x)
        self.y = float(y)
        self.tekst = tekst
        self.kleur = kleur
        self.leven = 55
        self.max_leven = 55
        self.dy = -1.8
        self.groot = groot
        self.font = pygame.font.SysFont("monospace", 22 if groot else 16, bold=groot)

    def update(self):
        self.y += self.dy
        self.dy *= 0.96
        self.leven -= 1
        return self.leven > 0

    def teken(self, surface, cam_x, cam_y):
        alpha = self.leven / self.max_leven
        kl = tuple(int(c * alpha) for c in self.kleur)
        t = self.font.render(self.tekst, True, kl)
        sx = int(self.x - cam_x) - t.get_width()//2
        sy = int(self.y - cam_y)
        surface.blit(t, (sx, sy))


class SchadeCijferSysteem:
    def __init__(self):
        self.cijfers = []

    def voeg_toe(self, x, y, schade, is_speler_schade=False, is_goud=False, is_xp=False, kleur_override=False):
        if kleur_override:
            self.cijfers.append(SchadeCijfer(x, y, str(schade), (255,220,50), groot=True))
        elif is_goud:
            self.cijfers.append(SchadeCijfer(x, y, f"+{schade}g", (220,200,50)))
        elif is_xp:
            self.cijfers.append(SchadeCijfer(x, y+20, f"+{schade}xp", (100,220,150)))
        elif is_speler_schade:
            self.cijfers.append(SchadeCijfer(x, y, f"-{int(schade)}", (255,80,80), groot=True))
        else:
            self.cijfers.append(SchadeCijfer(x, y, f"-{int(schade)}", (255,220,80)))

    def update(self):
        self.cijfers = [c for c in self.cijfers if c.update()]

    def teken(self, surface, cam_x, cam_y):
        for c in self.cijfers:
            c.teken(surface, cam_x, cam_y)


# ── Hit Flash ─────────────────────────────────────────────────────────────────
class HitFlash:
    """Wit overlay-flitje over het scherm bij een harde hit."""
    def __init__(self):
        self.timer = 0
        self.kracht = 0

    def start(self, kracht=80):
        self.kracht = kracht
        self.timer = 6

    def teken(self, surface):
        if self.timer > 0:
            alpha = int(self.kracht * (self.timer / 6))
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((255, 255, 255, alpha))
            surface.blit(overlay, (0, 0))
            self.timer -= 1
