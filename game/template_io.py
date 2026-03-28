from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from game.actors import Actor, MonsterTypeDef
from game.maze import Cell, Facing, Maze
from game.protocol_models import PlayerBriefing
from game.tuning import TuningConfig


def load_template(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("template root must be a mapping")
    return data


def build_maze_from_template(data: dict[str, Any]) -> Maze:
    w, h = int(data["width"]), int(data["height"])
    grid = data.get("grid")
    if grid:
        cells: list[list[Cell]] = []
        for y in range(h):
            row = []
            for x in range(w):
                spec = grid[y][x]
                if isinstance(spec, dict):
                    row.append(
                        Cell(
                            n=bool(spec.get("n", False)),
                            e=bool(spec.get("e", False)),
                            s=bool(spec.get("s", False)),
                            w=bool(spec.get("w", False)),
                            hazard=spec.get("hazard"),
                            item=spec.get("item"),
                            is_exit=bool(spec.get("exit", False)),
                        )
                    )
                else:
                    n, e, s, wv = spec
                    row.append(Cell(n=bool(n), e=bool(e), s=bool(s), w=bool(wv)))
            cells.append(row)
        return Maze(w, h, cells)
    return Maze.empty(w, h, outer_walls=True)


def build_monster_types(data: dict[str, Any]) -> dict[str, MonsterTypeDef]:
    out: dict[str, MonsterTypeDef] = {}
    for tid, spec in (data.get("monster_types") or {}).items():
        out[str(tid)] = MonsterTypeDef(
            id=str(tid),
            phrases=list(spec.get("phrases") or ["rustle"]),
            maze_proficiency=float(spec.get("maze_proficiency", 0.5)),
            sound_homing=float(spec.get("sound_homing", 0.5)),
        )
    return out


def build_actors(data: dict[str, Any], maze: Maze) -> tuple[Actor, list[Actor]]:
    px, py = data["player_spawn"]
    pf: Facing = str(data.get("player_facing", "north"))  # type: ignore[assignment]
    player = Actor(
        id="player",
        kind="player",
        x=int(px),
        y=int(py),
        facing=pf,
        perception_bonus=0,
        stealth_bonus=0,
    )
    player.note_enter_cell(player.x, player.y)
    monsters: list[Actor] = []
    for m in data.get("monsters") or []:
        mx, my = m["cell"]
        mt = str(m["type"])
        mf: Facing = str(m.get("facing", "south"))  # type: ignore[assignment]
        monsters.append(
            Actor(
                id=str(m["id"]),
                kind="monster",
                x=int(mx),
                y=int(my),
                facing=mf,
                perception_bonus=int(m.get("perception_bonus", 0)),
                stealth_bonus=int(m.get("stealth_bonus", 0)),
                perception_roll_mode=m.get("perception_roll_mode", "normal"),
                stealth_roll_mode=m.get("stealth_roll_mode", "normal"),
                monster_type_id=mt,
            )
        )
        monsters[-1].note_enter_cell(monsters[-1].x, monsters[-1].y)
    ex, ey = data["exit"]
    maze.cell(int(ex), int(ey)).is_exit = True
    return player, monsters


def build_briefing(data: dict[str, Any]) -> PlayerBriefing | None:
    pb = data.get("player_briefing")
    if not pb:
        return None
    return PlayerBriefing(
        welcome=pb.get("welcome"),
        goals=pb.get("goals"),
        commandsHelp=pb.get("commands_help"),
    )


def build_tuning(data: dict[str, Any]) -> TuningConfig:
    t = data.get("tuning") or {}
    if not t:
        return TuningConfig()
    return TuningConfig.model_validate(t)


def validate_template(path: Path | str) -> None:
    data = load_template(path)
    for key in ("width", "height", "player_spawn", "exit"):
        if key not in data:
            raise ValueError(f"missing required key: {key}")
    maze = build_maze_from_template(data)
    build_monster_types(data)
    player, monsters = build_actors(data, maze)
    for mid, m in [(player.id, player)] + [(m.id, m) for m in monsters]:
        if not maze.in_bounds(m.x, m.y):
            raise ValueError(f"actor {mid} out of bounds")
    for m in monsters:
        if m.monster_type_id not in (data.get("monster_types") or {}):
            raise ValueError(f"monster {m.id} unknown type {m.monster_type_id}")
