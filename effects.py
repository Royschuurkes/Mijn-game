# effects.py - Visual "game feel" effects
import math, random
import pygame


# ── Screen Shake ──────────────────────────────────────────────────────────────
class ScreenShake:
    def __init__(self):
        self.timer    = 0
        self.strength = 0

    def start(self, strength=6, duration=12):
        if strength > self.strength:
            self.strength = strength
            self.timer    = duration

    def update(self):
        if self.timer > 0:
            self.timer -= 1
            decay = self.timer / 12
            ox = random.randint(-1, 1) * int(self.strength * decay)
            oy = random.randint(-1, 1) * int(self.strength * decay)
            if self.timer == 0:
                self.strength = 0
            return ox, oy
        return 0, 0


# ── Freeze Frames ─────────────────────────────────────────────────────────────
class FreezeFrames:
    def __init__(self):
        self.timer = 0

    def start(self, frames=2):
        self.timer = max(self.timer, frames)

    def update(self):
        if self.timer > 0:
            self.timer -= 1
            return True
        return False


# ── Particle ──────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, dx, dy, color, lifetime, radius=3, gravity=0.0):
        self.x = float(x); self.y = float(y)
        self.dx = dx; self.dy = dy
        self.color        = color
        self.max_lifetime = lifetime
        self.lifetime     = lifetime
        self.radius  = radius
        self.gravity = gravity

    def update(self):
        self.x  += self.dx
        self.y  += self.dy
        self.dy += self.gravity
        self.dx *= 0.92
        self.dy *= 0.92
        self.lifetime -= 1
        return self.lifetime > 0

    def draw(self, surface, cam_x, cam_y):
        alpha = self.lifetime / self.max_lifetime
        r  = max(1, int(self.radius * alpha))
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        kl = tuple(int(c * alpha) for c in self.color)
        pygame.draw.circle(surface, kl, (sx, sy), r)


# ── Particle System ───────────────────────────────────────────────────────────
class ParticleSystem:
    def __init__(self):
        self.particles = []

    def update(self):
        self.particles = [p for p in self.particles if p.update()]

    def draw(self, surface, cam_x, cam_y):
        for p in self.particles:
            p.draw(surface, cam_x, cam_y)

    def sword_sparks(self, x, y, angle):
        for _ in range(12):
            spread = random.uniform(-40, 40)
            rad    = math.radians(angle + spread)
            speed  = random.uniform(2.5, 6.0)
            dx = math.cos(rad) * speed
            dy = math.sin(rad) * speed
            color = random.choice([
                (255, 240, 100), (255, 200, 50),
                (255, 255, 200), (220, 180, 50)
            ])
            self.particles.append(Particle(x, y, dx, dy, color,
                lifetime=random.randint(10, 20),
                radius=random.randint(2, 4),
                gravity=0.15))

    def blood_splatter(self, x, y, angle):
        for _ in range(10):
            spread = random.uniform(-60, 60)
            rad    = math.radians(angle + spread)
            speed  = random.uniform(1.5, 4.5)
            dx = math.cos(rad) * speed
            dy = math.sin(rad) * speed
            color = random.choice([
                (220, 30, 30), (180, 20, 20),
                (255, 60, 60), (200, 40, 40)
            ])
            self.particles.append(Particle(x, y, dx, dy, color,
                lifetime=random.randint(14, 24),
                radius=random.randint(2, 4),
                gravity=0.12))

    def death_explosion(self, x, y, color):
        for _ in range(25):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(2.0, 7.0)
            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed
            kl = random.choice([color, (255, 255, 200), (255, 200, 50), (255, 100, 50)])
            self.particles.append(Particle(x, y, dx, dy, kl,
                lifetime=random.randint(20, 35),
                radius=random.randint(3, 6),
                gravity=0.08))
        for _ in range(8):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(1.0, 3.0)
            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed
            self.particles.append(Particle(x, y, dx, dy, (255, 255, 255),
                lifetime=10, radius=random.randint(4, 8), gravity=0))

    def dodge_burst(self, x, y):
        """Expanding ring of white sparks on dodge start."""
        for _ in range(16):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(3.5, 7.0)
            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed
            color = random.choice([
                (255, 255, 255), (180, 220, 255),
                (140, 200, 255), (220, 240, 255)
            ])
            self.particles.append(Particle(x, y, dx, dy, color,
                lifetime=random.randint(6, 14),
                radius=random.randint(2, 4),
                gravity=0))

    def dodge_trail(self, x, y, color=(100, 160, 255)):
        self.particles.append(Particle(x, y, 0, 0, color,
            lifetime=10, radius=14, gravity=0))


# ── Floating Damage Numbers ───────────────────────────────────────────────────
class DamageNumber:
    def __init__(self, x, y, text, color, large=False):
        self.x = float(x); self.y = float(y)
        self.text         = text
        self.color        = color
        self.lifetime     = 55
        self.max_lifetime = 55
        self.dy    = -1.8
        self.large = large
        self.font  = pygame.font.SysFont("monospace", 22 if large else 16, bold=large)

    def update(self):
        self.y  += self.dy
        self.dy *= 0.96
        self.lifetime -= 1
        return self.lifetime > 0

    def draw(self, surface, cam_x, cam_y):
        alpha = self.lifetime / self.max_lifetime
        kl = tuple(int(c * alpha) for c in self.color)
        t  = self.font.render(self.text, True, kl)
        sx = int(self.x - cam_x) - t.get_width() // 2
        sy = int(self.y - cam_y)
        surface.blit(t, (sx, sy))


class DamageNumberSystem:
    def __init__(self):
        self.numbers = []

    def add(self, x, y, damage, is_player_damage=False,
            color_override=False, override_color=(255, 220, 50)):
        if color_override:
            self.numbers.append(DamageNumber(x, y, str(damage), override_color, large=True))
        elif is_player_damage:
            self.numbers.append(DamageNumber(x, y, f"-{int(damage)}", (255, 80, 80), large=True))
        else:
            self.numbers.append(DamageNumber(x, y, f"-{int(damage)}", (255, 220, 80)))

    def update(self):
        self.numbers = [n for n in self.numbers if n.update()]

    def draw(self, surface, cam_x, cam_y):
        for n in self.numbers:
            n.draw(surface, cam_x, cam_y)


# ── Hit Flash ─────────────────────────────────────────────────────────────────
class HitFlash:
    def __init__(self):
        self.timer    = 0
        self.strength = 0

    def start(self, strength=80):
        self.strength = strength
        self.timer    = 6

    def draw(self, surface):
        if self.timer > 0:
            alpha   = int(self.strength * (self.timer / 6))
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((255, 255, 255, alpha))
            surface.blit(overlay, (0, 0))
            self.timer -= 1