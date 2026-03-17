# level_manager.py - Manages floor and room progression (BoI style)
import random
from constants import *

# ── Floor definitions — tweak combat difficulty here ─────────────────────────
# Each floor has:
#   rooms_min/max  : number of combat rooms (random within range)
#   rest_after     : rest room appears after this many rooms
#   enemies        : list of enemy group compositions (one picked per room)
#   damage_mult    : how hard enemies hit on this floor
#   hp_mult        : enemy HP multiplier on this floor
#   room_sizes     : weighted list of (size_name, weight) for combat rooms

FLOOR_DEFINITIONS = {
    1: {
        "rooms_min": 3, "rooms_max": 4,
        "rest_after": 2,
        "damage_mult": 1.0, "hp_mult": 1.0,
        "enemies": [
            [("wolf",   2, 1.0)],
            [("wolf",   3, 1.0)],
            [("wolf",   1, 1.0), ("ranged", 2, 1.0)],
            [("ranged", 2, 1.0)],
            [("wolf",   1, 1.0)],
        ],
        "room_sizes": [("small", 0.7), ("medium", 0.3)],
    },
    2: {
        "rooms_min": 4, "rooms_max": 5,
        "rest_after": 3,
        "damage_mult": 1.1, "hp_mult": 1.2,
        "enemies": [
            [("wolf",   2, 1.2), ("ranged", 1, 1.0)],
            [("wolf",   1, 1.2), ("ranged", 2, 1.0)],
            [("ranged", 3, 1.2)],
            [("wolf",   3, 1.2)],
        ],
        "room_sizes": [("small", 0.4), ("medium", 0.6)],
    },
    3: {
        "rooms_min": 5, "rooms_max": 6,
        "rest_after": 4,
        "damage_mult": 1.2, "hp_mult": 1.5,
        "enemies": [
            [("wolf",   3, 1.5), ("ranged", 1, 1.2)],
            [("wolf",   1, 1.5), ("ranged", 3, 1.2)],
            [("ranged", 2, 1.5), ("wolf",   2, 1.5)],
            [("wolf",   4, 1.5)],
        ],
        "room_sizes": [("small", 0.1), ("medium", 0.5), ("large", 0.4)],
    },
    4: {
        "rooms_min": 5, "rooms_max": 8,
        "rest_after": 4,
        "damage_mult": 1.4, "hp_mult": 1.8,
        "enemies": [
            [("wolf",   2, 1.8), ("ranged", 2, 1.5)],
            [("ranged", 4, 1.8)],
            [("wolf",   3, 2.0), ("ranged", 1, 1.5)],
        ],
        "room_sizes": [("medium", 0.4), ("large", 0.6)],
    },
}

MAX_FLOOR = max(FLOOR_DEFINITIONS.keys())


def _get_floor_def(floor_num):
    """Returns floor definition. After max floor, keeps scaling up."""
    if floor_num <= MAX_FLOOR:
        return FLOOR_DEFINITIONS[floor_num]
    extra = 0.3 * (floor_num - MAX_FLOOR)
    base  = FLOOR_DEFINITIONS[MAX_FLOOR]
    return {
        "rooms_min":   base["rooms_min"],
        "rooms_max":   base["rooms_max"],
        "rest_after":  base["rest_after"],
        "damage_mult": round(base["damage_mult"] + extra, 2),
        "hp_mult":     round(base["hp_mult"]     + extra, 2),
        "enemies":     base["enemies"],
        "room_sizes":  base["room_sizes"],
    }


def _pick_room_size(fd):
    """Pick a room size based on weighted probabilities from floor def."""
    sizes = fd.get("room_sizes", [("medium", 1.0)])
    names, weights = zip(*sizes)
    return random.choices(names, weights=weights, k=1)[0]


OPPOSITE        = {"N": "S", "S": "N", "E": "W", "W": "E"}
DIRECTION_DELTA = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}


def generate_floor_graph(floor_num, npc_key=None):
    fd         = _get_floor_def(floor_num)
    room_count = random.randint(fd["rooms_min"], fd["rooms_max"])

    grid     = {(0, 0): True}
    order    = [(0, 0)]
    frontier = [(0, 0)]

    attempts = 0
    while len(grid) < room_count and attempts < 300:
        attempts += 1
        if not frontier:
            break
        base = random.choice(frontier)
        dirs = list(DIRECTION_DELTA.keys())
        random.shuffle(dirs)
        expanded = False
        for d in dirs:
            dr, dc = DIRECTION_DELTA[d]
            new = (base[0] + dr, base[1] + dc)
            if new not in grid:
                grid[new] = True
                order.append(new)
                frontier.append(new)
                expanded = True
                break
        if not expanded:
            frontier.remove(base)

    boss_pos          = order[-1]
    middle_candidates = order[1:-1]
    rest_pos          = random.choice(middle_candidates) if middle_candidates else None

    room_graph = {}
    for pos in order:
        gx, gy    = pos
        doors     = set()
        neighbors = {}
        for d, (dr, dc) in DIRECTION_DELTA.items():
            neighbor = (gx + dr, gy + dc)
            if neighbor in grid:
                doors.add(d)
                neighbors[d] = neighbor

        if pos == boss_pos:
            room_type    = "boss"
            hp           = round(fd["hp_mult"] * (1.0 + floor_num * 0.2), 2)
            enemy_config = [("boss", 1, hp)]
            room_size    = "medium"  # boss always medium
        elif pos == rest_pos:
            room_type    = "rest"
            enemy_config = []
            room_size    = "small"   # rest rooms are cozy
        else:
            room_type    = "combat"
            comp         = random.choice(fd["enemies"])
            enemy_config = [(t, n, round(h * fd["hp_mult"], 2)) for t, n, h in comp]
            room_size    = _pick_room_size(fd)

        room_graph[pos] = {
            "type":          room_type,
            "doors":         doors,
            "neighbors":     neighbors,
            "enemy_config":  enemy_config,
            "damage_mult":   fd["damage_mult"],
            "cleared":       room_type == "rest",
            "visited":       False,
            "fountain_used": False,
            "item_taken":    False,
            "map_data":      None,
            "size":          room_size,
        }

    # Insert NPC room if requested (floor 2+)
    if npc_key and floor_num >= 2:
        middle_combat = [p for p in order[1:-1]
                         if room_graph[p]["type"] == "combat"]
        min_rooms = 2 if npc_key == "edric" else 1
        if len(middle_combat) >= min_rooms:
            npc_pos = random.choice(middle_combat)
            room_graph[npc_pos].update({
                "type":         "npc",
                "npc_key":      npc_key,
                "npc_state":    "caged",
                "npc_talked":   False,
                "enemy_config": [],
                "cleared":      True,
                "size":         "small",
            })
            # Edric needs an Iron Warden to hold his key
            if npc_key == "edric":
                remaining  = [p for p in middle_combat if p != npc_pos]
                warden_pos = random.choice(remaining)
                room_graph[warden_pos]["enemy_config"].append(
                    ("iron_warden", 1, fd["hp_mult"])
                )

    return room_graph, order[0]


class LevelManager:
    def __init__(self):
        self.floor_num = 1
        self.room_type = "combat"

    def next_floor(self):
        self.floor_num += 1

    @property
    def is_rest(self):   return self.room_type == "rest"
    @property
    def is_boss(self):   return self.room_type == "boss"
    @property
    def is_combat(self): return self.room_type == "combat"
    @property
    def is_npc(self):    return self.room_type == "npc"

    def description(self, room_num=None, total=None):
        if self.is_rest: return f"Floor {self.floor_num}  -  Rest Room"
        if self.is_boss: return f"Floor {self.floor_num}  -  BOSS!"
        if self.is_npc:  return f"Floor {self.floor_num}  -  ???"
        if room_num and total:
            return f"Floor {self.floor_num}  -  Room {room_num}/{total}"
        return f"Floor {self.floor_num}"
