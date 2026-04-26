"""Maze generation algorithms for template designer and GM tools."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from game.maze import Cell, Maze


@dataclass(frozen=True)
class AlgorithmParam:
    key: str
    label: str
    kind: str = "int"
    min_value: int | None = None
    max_value: int | None = None
    default: int | None = None
    help_text: str = ""


@dataclass(frozen=True)
class MazeAlgorithm:
    key: str
    label: str
    params: tuple[AlgorithmParam, ...]
    generator: Callable[[int, int, int | None, dict[str, int]], Maze]


LINEARITY_PARAM = AlgorithmParam(
    key="linearity",
    label="Linearity (0-100)",
    kind="int",
    min_value=0,
    max_value=100,
    default=50,
    help_text="Higher values prefer continuing straight paths.",
)


def _all_wall_cells(width: int, height: int) -> list[list[Cell]]:
    return [[Cell(n=True, e=True, s=True, w=True) for _ in range(width)] for _ in range(height)]


def _carve_between(cells: list[list[Cell]], x: int, y: int, nx: int, ny: int) -> None:
    c = cells[y][x]
    nc = cells[ny][nx]
    if nx == x and ny == y - 1:
        c.n = False
        nc.s = False
    elif nx == x + 1 and ny == y:
        c.e = False
        nc.w = False
    elif nx == x and ny == y + 1:
        c.s = False
        nc.n = False
    elif nx == x - 1 and ny == y:
        c.w = False
        nc.e = False
    else:
        raise ValueError("cells are not adjacent")


def _neighbors(width: int, height: int, x: int, y: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    if y > 0:
        out.append((x, y - 1))
    if x + 1 < width:
        out.append((x + 1, y))
    if y + 1 < height:
        out.append((x, y + 1))
    if x > 0:
        out.append((x - 1, y))
    return out


def _dir_between(x: int, y: int, nx: int, ny: int) -> str:
    if nx == x and ny == y - 1:
        return "n"
    if nx == x + 1 and ny == y:
        return "e"
    if nx == x and ny == y + 1:
        return "s"
    if nx == x - 1 and ny == y:
        return "w"
    raise ValueError("cells are not adjacent")


def _linearity_prob(params: dict[str, int] | None) -> float:
    if not params:
        return 0.5
    raw = int(params.get("linearity", 50))
    return max(0.0, min(1.0, raw / 100.0))


def _biased_choice(
    rng: random.Random,
    candidates: list[tuple[int, int]],
    prev_dir: str | None,
    x: int,
    y: int,
    linearity: float,
) -> tuple[int, int]:
    if not candidates:
        raise ValueError("no candidates")
    if prev_dir is None:
        return rng.choice(candidates)
    straight = [c for c in candidates if _dir_between(x, y, c[0], c[1]) == prev_dir]
    if straight and rng.random() < linearity:
        return straight[0]
    others = [c for c in candidates if c not in straight]
    if others:
        return rng.choice(others)
    return straight[0]


def _generate_recursive_backtracker(
    width: int,
    height: int,
    seed: int | None = None,
    _params: dict[str, int] | None = None,
) -> Maze:
    """Perfect maze on grid; outer boundary walls kept; interior carved."""
    rng = random.Random(seed)
    cells = _all_wall_cells(width, height)
    linearity = _linearity_prob(_params)
    visited = [[False] * width for _ in range(height)]

    def dfs(x: int, y: int, prev_dir: str | None = None) -> None:
        visited[y][x] = True
        while True:
            candidates = [(nx, ny) for nx, ny in _neighbors(width, height, x, y) if not visited[ny][nx]]
            if not candidates:
                break
            nx, ny = _biased_choice(rng, candidates, prev_dir, x, y, linearity)
            if visited[ny][nx]:
                continue
            _carve_between(cells, x, y, nx, ny)
            dfs(nx, ny, _dir_between(x, y, nx, ny))

    sx, sy = rng.randrange(width), rng.randrange(height)
    dfs(sx, sy)
    return Maze(width, height, cells)


def _generate_all_walls(
    width: int,
    height: int,
    _seed: int | None = None,
    _params: dict[str, int] | None = None,
) -> Maze:
    return Maze.all_walls(width, height)


def _generate_prim(width: int, height: int, seed: int | None = None, _params: dict[str, int] | None = None) -> Maze:
    rng = random.Random(seed)
    cells = _all_wall_cells(width, height)
    linearity = _linearity_prob(_params)
    visited = [[False] * width for _ in range(height)]

    sx, sy = rng.randrange(width), rng.randrange(height)
    visited[sy][sx] = True
    frontier: list[tuple[int, int, int, int, str | None]] = []
    for nx, ny in _neighbors(width, height, sx, sy):
        frontier.append((sx, sy, nx, ny, None))

    while frontier:
        weighted_idxs: list[int] = list(range(len(frontier)))
        rng.shuffle(weighted_idxs)
        idx = weighted_idxs[0]
        if frontier:
            for wi in weighted_idxs:
                x2, y2, nx2, ny2, prev_dir2 = frontier[wi]
                if prev_dir2 is None:
                    idx = wi
                    break
                if _dir_between(x2, y2, nx2, ny2) == prev_dir2 and rng.random() < linearity:
                    idx = wi
                    break
        x, y, nx, ny, prev_dir = frontier.pop(idx)
        if visited[ny][nx]:
            continue
        _carve_between(cells, x, y, nx, ny)
        visited[ny][nx] = True
        for fx, fy in _neighbors(width, height, nx, ny):
            if not visited[fy][fx]:
                frontier.append((nx, ny, fx, fy, _dir_between(x, y, nx, ny) if prev_dir is not None else _dir_between(x, y, nx, ny)))
    return Maze(width, height, cells)


def _generate_kruskal(
    width: int, height: int, seed: int | None = None, _params: dict[str, int] | None = None
) -> Maze:
    rng = random.Random(seed)
    cells = _all_wall_cells(width, height)
    parent = list(range(width * height))
    rank = [0] * (width * height)

    def idx(x: int, y: int) -> int:
        return y * width + x

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> bool:
        ra = find(a)
        rb = find(b)
        if ra == rb:
            return False
        if rank[ra] < rank[rb]:
            parent[ra] = rb
        elif rank[ra] > rank[rb]:
            parent[rb] = ra
        else:
            parent[rb] = ra
            rank[ra] += 1
        return True

    edges: list[tuple[int, int, int, int]] = []
    for y in range(height):
        for x in range(width):
            if x + 1 < width:
                edges.append((x, y, x + 1, y))
            if y + 1 < height:
                edges.append((x, y, x, y + 1))
    rng.shuffle(edges)
    for x, y, nx, ny in edges:
        if union(idx(x, y), idx(nx, ny)):
            _carve_between(cells, x, y, nx, ny)
    return Maze(width, height, cells)


def _generate_wilson(width: int, height: int, seed: int | None = None, _params: dict[str, int] | None = None) -> Maze:
    rng = random.Random(seed)
    cells = _all_wall_cells(width, height)
    linearity = _linearity_prob(_params)
    unvisited = {(x, y) for y in range(height) for x in range(width)}
    first = rng.choice(tuple(unvisited))
    unvisited.remove(first)

    while unvisited:
        start = rng.choice(tuple(unvisited))
        path = [start]
        path_index = {start: 0}
        cur = start
        prev_dir: str | None = None
        while cur in unvisited:
            neighs = _neighbors(width, height, cur[0], cur[1])
            nx, ny = _biased_choice(rng, neighs, prev_dir, cur[0], cur[1], linearity)
            nxt = (nx, ny)
            prev_dir = _dir_between(cur[0], cur[1], nx, ny)
            if nxt in path_index:
                cut = path_index[nxt]
                path = path[: cut + 1]
                path_index = {p: i for i, p in enumerate(path)}
            else:
                path.append(nxt)
                path_index[nxt] = len(path) - 1
            cur = nxt
        for i in range(len(path) - 1):
            x, y = path[i]
            nx, ny = path[i + 1]
            _carve_between(cells, x, y, nx, ny)
            if (x, y) in unvisited:
                unvisited.remove((x, y))
        tail = path[-1]
        if tail in unvisited:
            unvisited.remove(tail)
    return Maze(width, height, cells)


def _generate_binary_tree(
    width: int, height: int, seed: int | None = None, _params: dict[str, int] | None = None
) -> Maze:
    rng = random.Random(seed)
    cells = _all_wall_cells(width, height)
    linearity = _linearity_prob(_params)
    prefer_east = linearity >= 0.5
    for y in range(height):
        for x in range(width):
            cands: list[tuple[int, int]] = []
            if y > 0:
                cands.append((x, y - 1))
            if x + 1 < width:
                cands.append((x + 1, y))
            if cands:
                if len(cands) == 2:
                    p = linearity if prefer_east else (1.0 - linearity)
                    nx, ny = cands[1] if rng.random() < p else cands[0]
                else:
                    nx, ny = cands[0]
                _carve_between(cells, x, y, nx, ny)
    return Maze(width, height, cells)


def _generate_sidewinder(
    width: int, height: int, seed: int | None = None, _params: dict[str, int] | None = None
) -> Maze:
    rng = random.Random(seed)
    cells = _all_wall_cells(width, height)
    linearity = _linearity_prob(_params)
    for y in range(height):
        run: list[int] = []
        for x in range(width):
            run.append(x)
            at_east = x == width - 1
            at_north = y == 0
            carve_east = not at_east and (at_north or rng.random() < linearity)
            if carve_east:
                _carve_between(cells, x, y, x + 1, y)
            else:
                if not at_north:
                    carve_x = rng.choice(run)
                    _carve_between(cells, carve_x, y, carve_x, y - 1)
                run = []
    return Maze(width, height, cells)


ALGORITHMS: dict[str, MazeAlgorithm] = {
    "recursive_backtracker": MazeAlgorithm(
        key="recursive_backtracker",
        label="Recursive backtracker",
        params=(LINEARITY_PARAM,),
        generator=_generate_recursive_backtracker,
    ),
    "all_walls": MazeAlgorithm(
        key="all_walls",
        label="All walls",
        params=(),
        generator=_generate_all_walls,
    ),
    "prim": MazeAlgorithm(
        key="prim",
        label="Prim",
        params=(LINEARITY_PARAM,),
        generator=_generate_prim,
    ),
    "kruskal": MazeAlgorithm(
        key="kruskal",
        label="Kruskal",
        params=(),
        generator=_generate_kruskal,
    ),
    "wilson": MazeAlgorithm(
        key="wilson",
        label="Wilson",
        params=(LINEARITY_PARAM,),
        generator=_generate_wilson,
    ),
    "binary_tree": MazeAlgorithm(
        key="binary_tree",
        label="Binary tree",
        params=(LINEARITY_PARAM,),
        generator=_generate_binary_tree,
    ),
    "sidewinder": MazeAlgorithm(
        key="sidewinder",
        label="Sidewinder",
        params=(LINEARITY_PARAM,),
        generator=_generate_sidewinder,
    ),
}


def generate_maze_with_algorithm(
    width: int,
    height: int,
    algorithm: str,
    seed: int | None = None,
    params: dict[str, int] | None = None,
) -> Maze:
    algo = ALGORITHMS.get(algorithm)
    if algo is None:
        raise ValueError(f"unknown maze algorithm: {algorithm}")
    return algo.generator(width, height, seed, params or {})


def generate_maze(width: int, height: int, seed: int | None = None) -> Maze:
    """Backward-compatible default generator."""
    return generate_maze_with_algorithm(width, height, "recursive_backtracker", seed=seed, params={})
