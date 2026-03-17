# map_gen.py - Arena-based map generation (BoI/Archero style)
# Supports variable room sizes: small (18×14), medium (26×20), large (34×26)
import random, math, pygame
from constants import *

# Default (medium) room size — used as fallback
MAP_WIDTH  = 26
MAP_HEIGHT = 20

# Room size presets
ROOM_SIZES = {
    "small":  (18, 14),
    "medium": (26, 20),
    "large":  (34, 26),
}


def _set_tile(tilemap, tx, ty, t, w=None, h=None):
    if w is None: w = len(tilemap[0]) if tilemap else MAP_WIDTH
    if h is None: h = len(tilemap)
    if 0 <= tx < w and 0 <= ty < h:
        tilemap[ty][tx] = t


def _make_tile_getter(tilemap):
    h = len(tilemap)
    w = len(tilemap[0]) if h > 0 else 0
    def get_tile(tx, ty):
        if 0 <= tx < w and 0 <= ty < h:
            return tilemap[ty][tx]
        return TREE
    return get_tile


def _tree_pillar(tilemap, cx, cy, radius=1):
    w = len(tilemap[0]) if tilemap else 0
    h = len(tilemap)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy <= radius * radius + 0.5:
                _set_tile(tilemap, cx + dx, cy + dy, TREE, w, h)


def _make_base(w, h):
    tilemap = [[GRASS] * w for _ in range(h)]
    for tx in range(w):
        for d in range(2):
            _set_tile(tilemap, tx, d,       TREE, w, h)
            _set_tile(tilemap, tx, h-1-d,   TREE, w, h)
    for ty in range(h):
        for d in range(2):
            _set_tile(tilemap, d,     ty, TREE, w, h)
            _set_tile(tilemap, w-1-d, ty, TREE, w, h)
    return tilemap


# ── Room layouts ──────────────────────────────────────────────────────────────
# All layouts receive (tilemap, w, h) so they adapt to any room size.

def _layout_open_pillars(tilemap, w, h):
    mx = w // 2; my = h // 2
    # Scale pillar offsets relative to room size
    ox = max(3, w // 6); oy = max(2, h // 6)
    for sx, sy in [(-ox, -oy), (ox, -oy), (-ox, oy), (ox, oy)]:
        _tree_pillar(tilemap, mx + sx, my + sy, radius=1)


def _layout_chokepoint(tilemap, w, h):
    my = h // 2
    for ty in range(2, h - 2):
        if abs(ty - my) > 2:
            _set_tile(tilemap, w // 2 - 1, ty, TREE, w, h)
            _set_tile(tilemap, w // 2,     ty, TREE, w, h)
            _set_tile(tilemap, w // 2 + 1, ty, TREE, w, h)


def _layout_tree_corridor(tilemap, w, h):
    my = h // 2
    row_off = max(2, h // 6)
    for tx in range(4, w - 4):
        if random.random() < 0.65: _set_tile(tilemap, tx, my - row_off, TREE, w, h)
        if random.random() < 0.65: _set_tile(tilemap, tx, my + row_off, TREE, w, h)
    for tx in range(w // 3, 2 * w // 3):
        _set_tile(tilemap, tx, my - row_off, GRASS, w, h)
        _set_tile(tilemap, tx, my + row_off, GRASS, w, h)


def _layout_ruins(tilemap, w, h):
    # Corner clusters + center obstacles, scaled to room size
    margin = max(4, min(5, w // 5))
    corners = [
        (margin, margin), (margin, margin+1), (margin+1, margin),
        (w-margin-1, margin), (w-margin, margin), (w-margin-1, margin+1),
        (margin, h-margin-1), (margin, h-margin), (margin+1, h-margin),
        (w-margin-1, h-margin), (w-margin, h-margin), (w-margin-1, h-margin-1),
        (w//2-1, h//2-1), (w//2, h//2-1),
        (w//2-1, h//2+1), (w//2, h//2+1),
    ]
    for tx, ty in corners:
        _set_tile(tilemap, tx, ty, TREE, w, h)


def _layout_arena(tilemap, w, h):
    cx = w // 2; cy = h // 2
    r_outer = min(w, h) // 2 - 2
    r_inner = r_outer - 3
    for ty in range(2, h - 2):
        for tx in range(2, w - 2):
            dist = math.hypot(tx - cx, (ty - cy) * 1.4)
            if r_inner < dist < r_outer and random.random() < 0.7:
                _set_tile(tilemap, tx, ty, TREE, w, h)


def _layout_split(tilemap, w, h):
    mx = w // 2
    for ty in range(2, h - 2):
        if ty < h // 2 - 3 or ty > h // 2 + 3:
            _set_tile(tilemap, mx,     ty, TREE, w, h)
            _set_tile(tilemap, mx + 1, ty, TREE, w, h)
    _tree_pillar(tilemap, mx // 2,          h // 2, 1)
    _tree_pillar(tilemap, mx + mx // 2 + 1, h // 2, 1)


LAYOUTS = [
    _layout_open_pillars,
    _layout_chokepoint,
    _layout_tree_corridor,
    _layout_ruins,
    _layout_arena,
    _layout_split,
]


# ── Map generation ────────────────────────────────────────────────────────────

def generate_arena(doors=None, width=MAP_WIDTH, height=MAP_HEIGHT):
    """Compact forest arena for boss fights — thick tree border, small clearing."""
    if doors is None:
        doors = {"E"}
    w, h = width, height
    BORDER = 5
    tilemap = [[TREE] * w for _ in range(h)]
    mx = w  // 2
    my = h // 2
    for ty in range(BORDER, h - BORDER):
        for tx in range(BORDER, w - BORDER):
            dx = (tx - mx) / max(1, w // 2 - BORDER)
            dy = (ty - my) / max(1, h // 2 - BORDER)
            if dx * dx + dy * dy < 1.05:
                tilemap[ty][tx] = GRASS
    rng_local = random.Random(42)
    for _ in range(12):
        tx = rng_local.randint(BORDER + 1, w - BORDER - 2)
        ty = rng_local.randint(BORDER + 1, h - BORDER - 2)
        if tilemap[ty][tx] == GRASS:
            tilemap[ty][tx] = PATH
    spawn_positions = {}
    if "W" in doors:
        for dy in range(-2, 3):
            for dx in range(0, BORDER + 2): _set_tile(tilemap, dx, my + dy, GRASS, w, h)
        spawn_positions["W"] = (2, my)
    if "E" in doors:
        for dy in range(-2, 3):
            for dx in range(w - BORDER - 2, w): _set_tile(tilemap, dx, my + dy, GRASS, w, h)
        spawn_positions["E"] = (w - 3, my)
    if "N" in doors:
        for dx in range(-2, 3):
            for dy in range(0, BORDER + 2): _set_tile(tilemap, mx + dx, dy, GRASS, w, h)
        spawn_positions["N"] = (mx, 2)
    if "S" in doors:
        for dx in range(-2, 3):
            for dy in range(h - BORDER - 2, h): _set_tile(tilemap, mx + dx, dy, GRASS, w, h)
        spawn_positions["S"] = (mx, h - 3)
    if not spawn_positions:
        spawn_positions["W"] = (mx, my)

    get_tile = _make_tile_getter(tilemap)
    trees = []; visited = set()
    for ty in range(h):
        for tx in range(w):
            if tilemap[ty][tx] == TREE and (tx, ty) not in visited:
                trees.append((tx, ty, 1))
                visited.add((tx, ty))
    rng = random.Random(random.randint(0, 9999))
    palette_map = {(tx, ty): rng.choice(TREE_PALETTE) for tx, ty, _ in trees}
    return tilemap, trees, palette_map, spawn_positions, get_tile


def _clear_zone(tilemap, cx, cy, radius, w, h):
    """Remove all tree tiles within radius tiles of (cx, cy)."""
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy <= radius * radius:
                _set_tile(tilemap, cx + dx, cy + dy, GRASS, w, h)


def generate_forest(doors=None, width=MAP_WIDTH, height=MAP_HEIGHT, clear_center=False):
    if doors is None:
        doors = {"E"}
    w, h = width, height
    tilemap = _make_base(w, h)
    random.choice(LAYOUTS)(tilemap, w, h)
    if clear_center:
        _clear_zone(tilemap, w // 2, h // 2, 4, w, h)
    my = h // 2
    mx = w  // 2
    spawn_positions = {}
    if "W" in doors:
        for dy in range(-2, 3):
            for dx in range(0, 4): _set_tile(tilemap, dx, my+dy, GRASS, w, h)
        spawn_positions["W"] = (2, my)
    if "E" in doors:
        for dy in range(-2, 3):
            for dx in range(w-4, w): _set_tile(tilemap, dx, my+dy, GRASS, w, h)
        spawn_positions["E"] = (w-3, my)
    if "N" in doors:
        for dx in range(-2, 3):
            for dy in range(0, 4): _set_tile(tilemap, mx+dx, dy, GRASS, w, h)
        spawn_positions["N"] = (mx, 2)
    if "S" in doors:
        for dx in range(-2, 3):
            for dy in range(h-4, h): _set_tile(tilemap, mx+dx, dy, GRASS, w, h)
        spawn_positions["S"] = (mx, h-3)
    if not spawn_positions:
        spawn_positions["W"] = (w//2, h//2)

    get_tile = _make_tile_getter(tilemap)
    trees = []; visited = set()
    for ty in range(h):
        for tx in range(w):
            if tilemap[ty][tx] == TREE and (tx, ty) not in visited:
                size = 1
                if (tx+1 < w and ty+1 < h
                        and tilemap[ty][tx+1]   == TREE
                        and tilemap[ty+1][tx]   == TREE
                        and tilemap[ty+1][tx+1] == TREE
                        and (tx+1, ty)   not in visited
                        and (tx,   ty+1) not in visited):
                    size = 2
                    visited.update([(tx, ty), (tx+1, ty), (tx, ty+1), (tx+1, ty+1)])
                else:
                    visited.add((tx, ty))
                trees.append((tx, ty, size))

    rng = random.Random(random.randint(0, 9999))
    palette_map = {(tx, ty): rng.choice(TREE_PALETTE) for tx, ty, _ in trees}
    return tilemap, trees, palette_map, spawn_positions, get_tile


# ── Tile and tree drawing ─────────────────────────────────────────────────────

def draw_tile(surface, tx, ty, sx, sy, get_tile):
    t = get_tile(tx, ty)
    r = pygame.Rect(sx, sy, TILE, TILE)
    if t in (GRASS, TREE, PATH, BUSH):
        pygame.draw.rect(surface, C_GRASS if (tx + ty) % 2 == 0 else C_GRASS_D, r)


def draw_tree(surface, tx, ty, size, palette, cam_x, cam_y):
    trunk_color, leaf_color, rim_color = palette
    pw = size * TILE
    cx = tx * TILE - cam_x + pw // 2
    cy = ty * TILE - cam_y + pw // 2
    pygame.draw.ellipse(surface, (15, 25, 15),
        (cx - pw//2 + 8, cy + pw//4 - 4, pw - 8, pw // 3))
    sb = max(6, size * 5)
    pygame.draw.rect(surface, trunk_color, (cx - sb//2, cy, sb, pw // 2))
    rh = int(pw * 0.52)
    pygame.draw.circle(surface, leaf_color, (cx, cy - pw // 6), rh)
    rng = random.Random(tx * 1000 + ty)
    for _ in range(size * 3):
        ox = rng.randint(-rh // 2, rh // 2)
        oy = rng.randint(-rh // 2, rh // 2)
        rb = rng.randint(rh // 4, rh // 2)
        pygame.draw.circle(surface, leaf_color, (cx + ox, cy - pw // 6 + oy), rb)
    pygame.draw.circle(surface, rim_color, (cx, cy - pw // 6), rh, 3)
