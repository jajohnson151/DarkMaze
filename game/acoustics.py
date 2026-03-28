from __future__ import annotations

import math
import random

from game.maze import DX, DY, Facing, Maze, turn_right
from game.tuning import TuningConfig


def bfs_shortest_path_len(maze: Maze, ax: int, ay: int, bx: int, by: int) -> int | None:
    if (ax, ay) == (bx, by):
        return 0
    w, h = maze.width, maze.height
    dist = [[10**9] * w for _ in range(h)]
    dist[ay][ax] = 0
    q = [(ax, ay)]
    head = 0
    while head < len(q):
        x, y = q[head]
        head += 1
        d0 = dist[y][x]
        for f in ("north", "east", "south", "west"):
            nxt = maze.step_from(x, y, f)
            if nxt is None:
                continue
            nx, ny = nxt
            if dist[ny][nx] <= d0 + 1:
                continue
            dist[ny][nx] = d0 + 1
            q.append((nx, ny))
    d = dist[by][bx]
    return None if d >= 10**8 else d


def propagation_modifier(maze: Maze, ex: int, ey: int, lx: int, ly: int, tuning: TuningConfig) -> int:
    path = bfs_shortest_path_len(maze, ex, ey, lx, ly)
    if path is None:
        return 0
    mod = tuning.propagation_base - path * tuning.propagation_per_step
    return max(0, mod)


def rel_direction8(lx: int, ly: int, lf: Facing, sx: int, sy: int) -> int:
    dx, dy = sx - lx, sy - ly
    if dx == 0 and dy == 0:
        return 0
    fx, fy = DX[lf], DY[lf]
    rx, ry = DX[turn_right(lf)], DY[turn_right(lf)]
    fu = dx * fx + dy * fy
    ru = dx * rx + dy * ry
    ang = math.atan2(ru, fu)
    deg = math.degrees(ang) % 360
    sector = int((deg + 22.5) // 45) % 8
    return sector


def roll_d20(rng: random.Random, mode: str) -> int:
    if mode == "advantage":
        return max(rng.randint(1, 20), rng.randint(1, 20))
    if mode == "disadvantage":
        return min(rng.randint(1, 20), rng.randint(1, 20))
    return rng.randint(1, 20)


def hearing_contest(
    rng: random.Random,
    listener_perception_bonus: int,
    listener_roll_mode: str,
    listener_extra: int,
    emitter_stealth_bonus: int,
    emitter_roll_mode: str,
    emitter_extra: int,
    propagation_mod: int,
) -> tuple[bool, int, int]:
    p_roll = roll_d20(rng, listener_roll_mode)
    s_roll = roll_d20(rng, emitter_roll_mode)
    p_total = p_roll + listener_perception_bonus + listener_extra
    s_total = s_roll + emitter_stealth_bonus + emitter_extra - propagation_mod
    return p_total >= s_total, p_roll, s_roll


def distance_band_index(margin: int, thresholds: list[int]) -> int:
    for i, t in enumerate(thresholds):
        if margin < t:
            return i
    return len(thresholds)


def pick_distance_label(rng: random.Random, tuning: TuningConfig, margin: int) -> str:
    bi = distance_band_index(margin, tuning.distance_band_thresholds)
    bi = min(bi, len(tuning.distance_band_labels) - 1)
    opts = tuning.distance_band_labels[bi]
    return rng.choice(opts)
