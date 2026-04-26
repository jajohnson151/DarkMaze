"""In-memory template grid edits (parity with web GM maze canvas)."""

from __future__ import annotations

from typing import Any, Literal

from game.maze_gen import ALGORITHMS, generate_maze_with_algorithm
from game.template_io import (
    build_maze_from_template,
    maze_to_template_grid,
    minimal_template_dict,
)

WallDir = Literal["n", "e", "s", "w"]
FacingDir = Literal["north", "east", "south", "west"]


def _wall_get(cell: dict[str, Any], k: str) -> bool:
    v = cell.get(k)
    return v is True or v == 1


def _wall_set(cell: dict[str, Any], k: str, on: bool) -> None:
    cell[k] = 1 if on else 0


def _cell_to_edit_dict(cell: Any) -> dict[str, Any]:
    """Normalize one cell to a mutable dict with n/e/s/w as 0/1 ints."""
    out: dict[str, Any]
    if isinstance(cell, dict):
        out = {
            "n": int(_wall_get(cell, "n")),
            "e": int(_wall_get(cell, "e")),
            "s": int(_wall_get(cell, "s")),
            "w": int(_wall_get(cell, "w")),
        }
        for k in ("hazard", "item"):
            if k in cell and cell[k] is not None:
                out[k] = cell[k]
        if "surface_type" in cell and cell["surface_type"]:
            out["surface_type"] = str(cell["surface_type"])
        room_pois = cell.get("room_pois")
        if isinstance(room_pois, list):
            out["room_pois"] = [dict(p) for p in room_pois if isinstance(p, dict)]
        if cell.get("exit"):
            out["exit"] = True
    else:
        seq = list(cell)  # type: ignore[arg-type]
        n, e, s, wv = (int(bool(seq[i])) for i in range(4))
        out = {"n": n, "e": e, "s": s, "w": wv}
    return out


def _checked_cell(data: dict[str, Any], x: int, y: int) -> dict[str, Any]:
    grid = data.get("grid")
    if not isinstance(grid, list):
        raise ValueError("grid missing")
    w = int(data["width"])
    h = int(data["height"])
    if x < 0 or y < 0 or x >= w or y >= h:
        raise ValueError("cell out of bounds")
    cell = grid[y][x]
    if not isinstance(cell, dict):
        raise ValueError("cell not editable")
    return cell


def _checked_facing(facing: str) -> FacingDir:
    if facing not in ("north", "east", "south", "west"):
        raise ValueError(f"invalid facing: {facing}")
    return facing  # type: ignore[return-value]


def normalize_template_grid_for_edit(data: dict[str, Any]) -> None:
    """Ensure data['grid'] exists, matches width/height, and cells are edit dicts."""
    w, h = int(data["width"]), int(data["height"])
    grid = data.get("grid")
    valid = (
        isinstance(grid, list)
        and len(grid) == h
        and all(isinstance(row, list) and len(row) == w for row in grid)
    )
    if not valid:
        d2 = {k: v for k, v in data.items() if k != "grid"}
        data["grid"] = maze_to_template_grid(build_maze_from_template(d2))
        return
    for y in range(h):
        for x in range(w):
            data["grid"][y][x] = _cell_to_edit_dict(grid[y][x])
    edge_pois = data.get("edge_pois")
    if not isinstance(edge_pois, list):
        data["edge_pois"] = []
    else:
        data["edge_pois"] = [dict(p) for p in edge_pois if isinstance(p, dict)]
    surface_types = data.get("surface_types")
    if not isinstance(surface_types, dict):
        data["surface_types"] = {
            "smooth stone": {"noisiness": 0},
            "dirt": {"noisiness": 1},
            "crunchy gravel": {"noisiness": 2},
            "standing water": {"noisiness": 3},
        }
    else:
        fixed: dict[str, dict[str, int]] = {}
        for name, spec in surface_types.items():
            if not isinstance(name, str):
                continue
            noisiness = 0
            if isinstance(spec, dict):
                try:
                    noisiness = int(spec.get("noisiness", 0))
                except Exception:
                    noisiness = 0
            fixed[name] = {"noisiness": max(0, noisiness)}
        data["surface_types"] = fixed


def toggle_wall_at(data: dict[str, Any], x: int, y: int, direction: WallDir) -> None:
    """Toggle wall on shared edge; keeps adjacent cell consistent."""
    grid = data.get("grid")
    if not isinstance(grid, list):
        return
    w = int(data["width"])
    h = int(data["height"])
    if x < 0 or y < 0 or x >= w or y >= h:
        return
    row = grid[y]
    if not isinstance(row, list) or x >= len(row):
        return
    c = row[x]
    if not isinstance(c, dict):
        return

    if direction == "n":
        nxt = not _wall_get(c, "n")
        _wall_set(c, "n", nxt)
        if y > 0:
            north = grid[y - 1][x]
            if isinstance(north, dict):
                _wall_set(north, "s", nxt)
    elif direction == "s":
        nxt = not _wall_get(c, "s")
        _wall_set(c, "s", nxt)
        if y + 1 < h:
            south = grid[y + 1][x]
            if isinstance(south, dict):
                _wall_set(south, "n", nxt)
    elif direction == "e":
        nxt = not _wall_get(c, "e")
        _wall_set(c, "e", nxt)
        if x + 1 < w:
            east = grid[y][x + 1]
            if isinstance(east, dict):
                _wall_set(east, "w", nxt)
    else:
        nxt = not _wall_get(c, "w")
        _wall_set(c, "w", nxt)
        if x > 0:
            west = grid[y][x - 1]
            if isinstance(west, dict):
                _wall_set(west, "e", nxt)


def set_wall_at(data: dict[str, Any], x: int, y: int, direction: WallDir, on: bool) -> None:
    """Set wall on shared edge to explicit state; keeps adjacent cell consistent."""
    grid = data.get("grid")
    if not isinstance(grid, list):
        return
    w = int(data["width"])
    h = int(data["height"])
    if x < 0 or y < 0 or x >= w or y >= h:
        return
    row = grid[y]
    if not isinstance(row, list) or x >= len(row):
        return
    c = row[x]
    if not isinstance(c, dict):
        return

    if direction == "n":
        _wall_set(c, "n", on)
        if y > 0:
            north = grid[y - 1][x]
            if isinstance(north, dict):
                _wall_set(north, "s", on)
    elif direction == "s":
        _wall_set(c, "s", on)
        if y + 1 < h:
            south = grid[y + 1][x]
            if isinstance(south, dict):
                _wall_set(south, "n", on)
    elif direction == "e":
        _wall_set(c, "e", on)
        if x + 1 < w:
            east = grid[y][x + 1]
            if isinstance(east, dict):
                _wall_set(east, "w", on)
    else:
        _wall_set(c, "w", on)
        if x > 0:
            west = grid[y][x - 1]
            if isinstance(west, dict):
                _wall_set(west, "e", on)


def get_wall_at(data: dict[str, Any], x: int, y: int, direction: WallDir) -> bool:
    grid = data.get("grid")
    if not isinstance(grid, list):
        return False
    w = int(data["width"])
    h = int(data["height"])
    if x < 0 or y < 0 or x >= w or y >= h:
        return False
    row = grid[y]
    if not isinstance(row, list) or x >= len(row):
        return False
    c = row[x]
    if not isinstance(c, dict):
        return False
    return _wall_get(c, direction)


def set_surface_type_at(data: dict[str, Any], x: int, y: int, surface_type: str | None) -> None:
    grid = data.get("grid")
    if not isinstance(grid, list):
        return
    w = int(data["width"])
    h = int(data["height"])
    if x < 0 or y < 0 or x >= w or y >= h:
        return
    cell = grid[y][x]
    if not isinstance(cell, dict):
        return
    if surface_type:
        cell["surface_type"] = surface_type
    else:
        cell.pop("surface_type", None)


def set_surface_noisiness(data: dict[str, Any], surface_type: str, noisiness: int) -> None:
    if not surface_type.strip():
        return
    surface_types = data.setdefault("surface_types", {})
    if not isinstance(surface_types, dict):
        surface_types = {}
        data["surface_types"] = surface_types
    surface_types[surface_type] = {"noisiness": max(0, int(noisiness))}


def set_player_spawn(data: dict[str, Any], x: int, y: int) -> None:
    _checked_cell(data, x, y)
    data["player_spawn"] = [x, y]


def set_player_facing(data: dict[str, Any], facing: str) -> None:
    data["player_facing"] = _checked_facing(facing)


def set_exit_cell(data: dict[str, Any], x: int, y: int) -> None:
    _checked_cell(data, x, y)
    data["exit"] = [x, y]
    grid = data.get("grid")
    if isinstance(grid, list):
        for row in grid:
            if not isinstance(row, list):
                continue
            for cell in row:
                if isinstance(cell, dict):
                    cell.pop("exit", None)
        c = grid[y][x]
        if isinstance(c, dict):
            c["exit"] = True


def add_room_poi_at(data: dict[str, Any], x: int, y: int, poi_type: str, note: str | None = None) -> None:
    grid = data.get("grid")
    if not isinstance(grid, list):
        return
    w = int(data["width"])
    h = int(data["height"])
    if x < 0 or y < 0 or x >= w or y >= h:
        return
    cell = grid[y][x]
    if not isinstance(cell, dict):
        return
    pois = cell.setdefault("room_pois", [])
    if not isinstance(pois, list):
        pois = []
        cell["room_pois"] = pois
    item: dict[str, Any] = {"poi_type": poi_type}
    if note:
        item["note"] = note
    pois.append(item)


def add_edge_poi(data: dict[str, Any], x: int, y: int, direction: WallDir, poi_type: str, note: str | None = None) -> None:
    _checked_cell(data, x, y)
    edge_pois = data.setdefault("edge_pois", [])
    if not isinstance(edge_pois, list):
        edge_pois = []
        data["edge_pois"] = edge_pois
    item: dict[str, Any] = {"x": x, "y": y, "dir": direction, "poi_type": poi_type}
    if note:
        item["note"] = note
    edge_pois.append(item)


def remove_room_poi_at(data: dict[str, Any], x: int, y: int, index: int) -> None:
    cell = _checked_cell(data, x, y)
    pois = cell.get("room_pois")
    if not isinstance(pois, list):
        raise ValueError("room_pois missing")
    if index < 0 or index >= len(pois):
        raise ValueError("room_poi index out of bounds")
    pois.pop(index)


def remove_edge_poi(data: dict[str, Any], index: int) -> None:
    edge_pois = data.get("edge_pois")
    if not isinstance(edge_pois, list):
        raise ValueError("edge_pois missing")
    if index < 0 or index >= len(edge_pois):
        raise ValueError("edge_poi index out of bounds")
    edge_pois.pop(index)


def add_monster_instance(
    data: dict[str, Any],
    monster_id: str,
    monster_type: str,
    x: int,
    y: int,
    facing: str,
    perception_bonus: int = 0,
    stealth_bonus: int = 0,
) -> None:
    _checked_cell(data, x, y)
    if not monster_id.strip():
        raise ValueError("monster id required")
    monster_types = data.get("monster_types")
    if not isinstance(monster_types, dict) or monster_type not in monster_types:
        raise ValueError(f"unknown monster type: {monster_type}")
    monsters = data.setdefault("monsters", [])
    if not isinstance(monsters, list):
        raise ValueError("monsters must be a list")
    for m in monsters:
        if isinstance(m, dict) and str(m.get("id", "")) == monster_id:
            raise ValueError(f"monster id already exists: {monster_id}")
    monsters.append(
        {
            "id": monster_id,
            "type": monster_type,
            "cell": [x, y],
            "facing": _checked_facing(facing),
            "perception_bonus": int(perception_bonus),
            "stealth_bonus": int(stealth_bonus),
        }
    )


def update_monster_instance(
    data: dict[str, Any],
    monster_id: str,
    *,
    x: int | None = None,
    y: int | None = None,
    facing: str | None = None,
    monster_type: str | None = None,
    perception_bonus: int | None = None,
    stealth_bonus: int | None = None,
) -> None:
    monsters = data.get("monsters")
    if not isinstance(monsters, list):
        raise ValueError("monsters must be a list")
    target: dict[str, Any] | None = None
    for m in monsters:
        if isinstance(m, dict) and str(m.get("id", "")) == monster_id:
            target = m
            break
    if target is None:
        raise ValueError(f"unknown monster id: {monster_id}")
    nx = int(target.get("cell", [0, 0])[0]) if x is None else x
    ny = int(target.get("cell", [0, 0])[1]) if y is None else y
    _checked_cell(data, nx, ny)
    target["cell"] = [nx, ny]
    if facing is not None:
        target["facing"] = _checked_facing(facing)
    if monster_type is not None:
        monster_types = data.get("monster_types")
        if not isinstance(monster_types, dict) or monster_type not in monster_types:
            raise ValueError(f"unknown monster type: {monster_type}")
        target["type"] = monster_type
    if perception_bonus is not None:
        target["perception_bonus"] = int(perception_bonus)
    if stealth_bonus is not None:
        target["stealth_bonus"] = int(stealth_bonus)


def remove_monster_instance(data: dict[str, Any], monster_id: str) -> None:
    monsters = data.get("monsters")
    if not isinstance(monsters, list):
        raise ValueError("monsters must be a list")
    before = len(monsters)
    data["monsters"] = [
        m for m in monsters if not (isinstance(m, dict) and str(m.get("id", "")) == monster_id)
    ]
    if len(data["monsters"]) == before:
        raise ValueError(f"unknown monster id: {monster_id}")


def pick_wall_toggle_cell_dir(
    offset_x: float,
    offset_y: float,
    pad: float,
    cell_size: float,
    width: int,
    height: int,
    edge_px: float = 8.0,
) -> tuple[int, int, WallDir] | None:
    """
    Map canvas pixel (relative to canvas origin) to (cell_x, cell_y, wall_dir),
    matching web gm_maze_canvas.ts onPointer nearest-edge logic.
    """
    cs = cell_size
    p = pad
    fx = (offset_x - p) / cs
    fy = (offset_y - p) / cs
    if fx < 0 or fy < 0 or fx >= width or fy >= height:
        return None
    cell_x = int(fx)
    cell_y = int(fy)
    frac_x = fx - cell_x
    frac_y = fy - cell_y
    d_n = frac_y * cs
    d_s = (1.0 - frac_y) * cs
    d_w = frac_x * cs
    d_e = (1.0 - frac_x) * cs
    cands: list[tuple[WallDir, float]] = [
        ("n", d_n),
        ("s", d_s),
        ("w", d_w),
        ("e", d_e),
    ]
    cands.sort(key=lambda t: t[1])
    best_dir, best_d = cands[0]
    if best_d > edge_px:
        return None
    return (cell_x, cell_y, best_dir)


def apply_recursive_backtracker_maze(
    data: dict[str, Any],
    width: int,
    height: int,
    seed: int | None = None,
) -> None:
    """
    Replace maze topology with a new perfect maze; preserve monster_types,
    monsters, player_briefing, tuning. Spawn/exit reset like CLI autogen.
    """
    apply_generated_maze(
        data,
        width,
        height,
        algorithm="recursive_backtracker",
        seed=seed,
        params={},
    )


def apply_generated_maze(
    data: dict[str, Any],
    width: int,
    height: int,
    algorithm: str,
    seed: int | None = None,
    params: dict[str, int] | None = None,
) -> None:
    """
    Replace maze topology using selected algorithm; preserve monster_types,
    monsters, player_briefing, tuning. Spawn/exit reset like CLI autogen.
    """
    if width < 2 or height < 2:
        raise ValueError("width and height must be at least 2")
    if algorithm not in ALGORITHMS:
        raise ValueError(f"unknown maze algorithm: {algorithm}")
    maze = generate_maze_with_algorithm(width, height, algorithm, seed=seed, params=params or {})
    base = minimal_template_dict(width, height)
    data["width"] = width
    data["height"] = height
    data["player_spawn"] = list(base["player_spawn"])
    data["player_facing"] = base["player_facing"]
    data["exit"] = list(base["exit"])
    data["grid"] = maze_to_template_grid(maze)
    normalize_template_grid_for_edit(data)
