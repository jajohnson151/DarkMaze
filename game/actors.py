from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from game.maze import Facing

RollMode = Literal["normal", "advantage", "disadvantage"]


@dataclass
class MonsterTypeDef:
    id: str
    phrases: list[str]
    maze_proficiency: float = 0.5
    sound_homing: float = 0.5


@dataclass
class Actor:
    id: str
    kind: Literal["player", "monster"]
    x: int
    y: int
    facing: Facing
    perception_bonus: int = 0
    stealth_bonus: int = 0
    perception_roll_mode: RollMode = "normal"
    stealth_roll_mode: RollMode = "normal"
    action_pool: int = 0
    monster_type_id: str | None = None
    explored_cells: set[tuple[int, int]] = field(default_factory=set)
    last_sound_hint: tuple[int, int] | None = None
    partial_action_remaining: int = 0
    partial_action_kind: str | None = None

    def note_enter_cell(self, x: int, y: int) -> None:
        self.explored_cells.add((x, y))
