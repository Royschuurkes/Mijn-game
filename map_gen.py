# map_gen.py - Arena-based map generation (BoI/Archero style)
import random, math, pygame
from constants import *

MAP_WIDTH  = 26
MAP_HEIGHT = 20


def _set_tile(tilemap, tx, ty, t):
    if 0 <= tx < MAP_WIDTH and 0 <= ty < MAP_HEIGHT:
        tilemap[ty][tx] = t


def _make_tile_getter(tilemap):
    def get_tile(tx, ty):
        if 0 <= tx < MAP_WIDTH and 0 <= ty < MAP_HEIGHT:
            return tilemap[ty][tx]
        return TREE
    return get_tile


def _tree_pillar(tilemap, cx, cy, radius=1):
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy <= radius * radius + 0.5:
                _set_tile(tilemap, cx + dx, cy + dy, TREE)


def _make_base():
    tilemap = [[GRASS] * MAP_WIDTH for _ in range(MAP_HEIGHT)]
    for tx in range(MAP_WIDTH):
        for d in range(2):
            _set_tile(tilemap, tx, d,               TREE)
            _set_tile(tilemap, tx, MAP_HEIGHT-1-d,  TREE)
    for ty in range(MAP_HEIGHT):
        for d in range(2):
            _set_tile(tilemap, d,             ty, TREE)
            _set_tile(tilemap, MAP_WIDTH-1-d, ty, TREE)
    return tilemap


# ── Room layouts ──────────────────────────────────────────────────────────────

def _layout_open_pillars(tilemap):
    mx = MAP_WIDTH // 2; my = MAP_HEIGHT // 2
    for ox, oy in [(-4, -3), (4, -3), (-4, 3), (4, 3)]:
        _tree_pillar(tilemap, mx + ox, my + oy, radius=1)


def _layout_chokepoint(tilemap):
    my = MAP_HEIGHT // 2
    for ty in range(2, MAP_HEIGHT - 2):
        if abs(ty - my) > 2:
            _set_tile(tilemap, MAP_WIDTH // 2 - 1, ty, TREE)
            _set_tile(tilemap, MAP_WIDTH // 2,     ty, TREE)
            _set_tile(tilemap, MAP_WIDTH // 2 + 1, ty, TREE)


def _layout_tree_corridor(tilemap):
    my = MAP_HEIGHT // 2
    for tx in range(4, MAP_WIDTH - 4):
        if random.random() < 0.65: _set_tile(tilemap, tx, my - 3, TREE)
        if random.random() < 0.65: _set_tile(tilemap, tx, my + 3, TREE)
    for tx in range(MAP_WIDTH // 3, 2 * MAP_WIDTH // 3):
        _set_tile(tilemap, tx, my - 3, GRASS)
        _set_tile(tilemap, tx, my + 3, GRASS)


def _layout_ruins(tilemap):
    for tx, ty in [
        (5, 4), (5, 5), (6, 4),
        (MAP_WIDTH-7, 4), (MAP_WIDTH-6, 4), (MAP_WIDTH-7, 5),
        (5, MAP_HEIGHT-6), (5, MAP_HEIGHT-5), (6, MAP_HEIGHT-5),
        (MAP_WIDTH-7, MAP_HEIGHT-5), (MAP_WIDTH-6, MAP_HEIGHT-5), (MAP_WIDTH-7, MAP_HEIGHT-6),
        (MAP_WIDTH//2-1, MAP_HEIGHT//2-1), (MAP_WIDTH//2, MAP_HEIGHT//2-1),
        (MAP_WIDTH//2-1, MAP_HEIGHT//2+1), (MAP_WIDTH//2, MAP_HEIGHT//2+1),
    ]:
        _set_tile(tilemap, tx, ty, TREE)


def _layout_arena(tilemap):
    cx = MAP_WIDTH // 2; cy = MAP_HEIGHT // 2
    r_outer = min(MAP_WIDTH, MAP_HEIGHT) // 2 - 2
    r_inner = r_outer - 3
    for ty in range(2, MAP_HEIGHT - 2):
        for tx in range(2, MAP_WIDTH - 2):
            dist = math.hypot(tx - cx, (ty - cy) * 1.4)
            if r_inner < dist < r_outer and random.random() < 0.7:
                _set_tile(tilemap, tx, ty, TREE)


def _layout_split(tilemap):
    mx = MAP_WIDTH // 2
    for ty in range(2, MAP_HEIGHT - 2):
        if ty < MAP_HEIGHT // 2 - 3 or ty > MAP_HEIGHT // 2 + 3:
            _set_tile(tilemap, mx,     ty, TREE)
            _set_tile(tilemap, mx + 1, ty, TREE)
    _tree_pillar(tilemap, mx // 2,          MAP_HEIGHT // 2, 1)
    _tree_pillar(tilemap, mx + mx // 2 + 1, MAP_HEIGHT // 2, 1)


LAYOUTS = [
    _layout_open_pillars,
    _layout_chokepoint,
    _layout_tree_corridor,
    _layout_ruins,
    _layout_arena,
    _layout_split,
]


# ── Map generation ────────────────────────────────────────────────────────────

def generate_arena(doors=None):
    """Open rectangular arena for boss fights — no obstacles."""
    if doors is None:
        doors = {"E"}
    tilemap = [[GRASS] * MAP_WIDTH for _ in range(MAP_HEIGHT)]
    for tx in range(MAP_WIDTH):
        for ty in range(MAP_HEIGHT):
            if tx < 2 or tx >= MAP_WIDTH - 2 or ty < 2 or ty >= MAP_HEIGHT - 2:
                tilemap[ty][tx] = TREE
    my = MAP_HEIGHT // 2
    mx = MAP_WIDTH  // 2
    spawn_positions = {}
    if "W" in doors:
        for dy in range(-2, 3):
            for dx in range(0, 4): tilemap[my+dy][dx] = GRASS
        spawn_positions["W"] = (2, my)
    if "E" in doors:
        for dy in range(-2, 3):
            for dx in range(MAP_WIDTH-4, MAP_WIDTH): tilemap[my+dy][dx] = GRASS
        spawn_positions["E"] = (MAP_WIDTH-3, my)
    if "N" in doors:
        for dx in range(-2, 3):
            for dy in range(0, 4): tilemap[dy][mx+dx] = GRASS
        spawn_positions["N"] = (mx, 2)
    if "S" in doors:
        for dx in range(-2, 3):
            for dy in range(MAP_HEIGHT-4, MAP_HEIGHT): tilemap[dy][mx+dx] = GRASS
        spawn_positions["S"] = (mx, MAP_HEIGHT-3)
    if not spawn_positions:
        spawn_positions["W"] = (MAP_WIDTH//2, MAP_HEIGHT//2)

    get_tile = _make_tile_getter(tilemap)
    trees = []; visited = set()
    for ty in range(MAP_HEIGHT):
        for tx in range(MAP_WIDTH):
            if tilemap[ty][tx] == TREE and (tx, ty) not in visited:
                trees.append((tx, ty, 1))
                visited.add((tx, ty))
    rng = random.Random(random.randint(0, 9999))
    palette_map = {(tx, ty): rng.choice(TREE_PALETTE) for tx, ty, _ in trees}
    return tilemap, trees, palette_map, spawn_positions, get_tile


def generate_forest(doors=None):
    if doors is None:
        doors = {"E"}
    tilemap = _make_base()
    random.choice(LAYOUTS)(tilemap)
    my = MAP_HEIGHT // 2
    mx = MAP_WIDTH  // 2
    spawn_positions = {}
    if "W" in doors:
        for dy in range(-2, 3):
            for dx in range(0, 4): _set_tile(tilemap, dx, my+dy, GRASS)
        spawn_positions["W"] = (2, my)
    if "E" in doors:
        for dy in range(-2, 3):
            for dx in range(MAP_WIDTH-4, MAP_WIDTH): _set_tile(tilemap, dx, my+dy, GRASS)
        spawn_positions["E"] = (MAP_WIDTH-3, my)
    if "N" in doors:
        for dx in range(-2, 3):
            for dy in range(0, 4): _set_tile(tilemap, mx+dx, dy, GRASS)
        spawn_positions["N"] = (mx, 2)
    if "S" in doors:
        for dx in range(-2, 3):
            for dy in range(MAP_HEIGHT-4, MAP_HEIGHT): _set_tile(tilemap, mx+dx, dy, GRASS)
        spawn_positions["S"] = (mx, MAP_HEIGHT-3)
    if not spawn_positions:
        spawn_positions["W"] = (MAP_WIDTH//2, MAP_HEIGHT//2)

    get_tile = _make_tile_getter(tilemap)
    trees = []; visited = set()
    for ty in range(MAP_HEIGHT):
        for tx in range(MAP_WIDTH):
            if tilemap[ty][tx] == TREE and (tx, ty) not in visited:
                size = 1
                if (tx+1 < MAP_WIDTH and ty+1 < MAP_HEIGHT
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