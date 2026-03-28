"""Rectangular grid maze with N/E/S/W walls per cell."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Facing = Literal["north", "east", "south", "west"]

FACINGS: tuple[Facing, ...] = ("north", "east", "south", "west")
DX = {"north": 0, "east": 1, "south": 0, "west": -1}
DY = {"north": -1, "east": 0, "south": 1, "west": 0}
LEFT: dict[Facing, Facing] = {"north": "west", "west": "south", "south": "east", "east": "north"}
RIGHT: dict[Facing, Facing] = {v: k for k, v in LEFT.items()}


def turn_left(f: Facing) -> Facing:
    return LEFT[f]


def turn_right(f: Facing) -> Facing:
    return RIGHT[f]


@dataclass
class Cell:
    n: bool = True
    e: bool = True
    s: bool = True
    w: bool = True
    hazard: str | None = None
    item: str | None = None
    is_exit: bool = False


@dataclass
class Maze:
    width: int
    height: int
    cells: list[list[Cell]] = field(repr=False)

    @staticmethod
    def empty(width: int, height: int, outer_walls: bool = True) -> Maze:
        cells: list[list[Cell]] = []
        for y in range(height):
            row = []
            for x in range(width):
                n = outer_walls and y == 0
                s = outer_walls and y == height - 1
                w = outer_walls and x == 0
                e = outer_walls and x == width - 1
                row.append(Cell(n=n, e=e, s=s, w=w))
            cells.append(row)
        return Maze(width, height, cells)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def cell(self, x: int, y: int) -> Cell:
        return self.cells[y][x]

    def can_step(self, x: int, y: int, facing: Facing) -> bool:
        c = self.cell(x, y)
        if facing == "north":
            return not c.n
        if facing == "east":
            return not c.e
        if facing == "south":
            return not c.s
        return not c.w

    def step_from(self, x: int, y: int, facing: Facing) -> tuple[int, int] | None:
        if not self.can_step(x, y, facing):
            return None
        nx, ny = x + DX[facing], y + DY[facing]
        if not self.in_bounds(nx, ny):
            return None
        return nx, ny
