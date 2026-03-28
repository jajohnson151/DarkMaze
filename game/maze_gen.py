"""Recursive backtracker maze generation (carve passages)."""

from __future__ import annotations

import random

from game.maze import Cell, Maze


def generate_maze(width: int, height: int, seed: int | None = None) -> Maze:
    """Perfect maze on grid; outer boundary walls kept; interior carved."""
    rng = random.Random(seed)
    cells: list[list[Cell]] = [
        [Cell(n=True, e=True, s=True, w=True) for _ in range(width)] for _ in range(height)
    ]
    for x in range(width):
        cells[0][x].n = True
        cells[height - 1][x].s = True
    for y in range(height):
        cells[y][0].w = True
        cells[y][width - 1].e = True

    visited = [[False] * width for _ in range(height)]

    def neighbors(cx: int, cy: int) -> list[tuple[int, int, str, str]]:
        opts: list[tuple[int, int, str, str]] = []
        if cy > 0:
            opts.append((cx, cy - 1, "n", "s"))
        if cx < width - 1:
            opts.append((cx + 1, cy, "e", "w"))
        if cy < height - 1:
            opts.append((cx, cy + 1, "s", "n"))
        if cx > 0:
            opts.append((cx - 1, cy, "w", "e"))
        rng.shuffle(opts)
        return opts

    stack: list[tuple[int, int]] = []

    def dfs(x: int, y: int) -> None:
        visited[y][x] = True
        stack.append((x, y))
        for nx, ny, dir_out, dir_in in neighbors(x, y):
            if visited[ny][nx]:
                continue
            c = cells[y][x]
            nc = cells[ny][nx]
            if dir_out == "n":
                c.n = False
                nc.s = False
            elif dir_out == "s":
                c.s = False
                nc.n = False
            elif dir_out == "e":
                c.e = False
                nc.w = False
            else:
                c.w = False
                nc.e = False
            dfs(nx, ny)
        stack.pop()

    sx, sy = rng.randrange(width), rng.randrange(height)
    dfs(sx, sy)
    for x in range(width):
        cells[0][x].n = True
        cells[height - 1][x].s = True
    for y in range(height):
        cells[y][0].w = True
        cells[y][width - 1].e = True
    return Maze(width, height, cells)
