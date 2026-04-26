from __future__ import annotations

import pytest

from game.maze_gen import ALGORITHMS
from game.template_edit import (
    add_edge_poi,
    add_monster_instance,
    add_room_poi_at,
    apply_generated_maze,
    apply_recursive_backtracker_maze,
    get_wall_at,
    normalize_template_grid_for_edit,
    pick_wall_toggle_cell_dir,
    set_exit_cell,
    set_player_spawn,
    set_surface_type_at,
    set_wall_at,
    toggle_wall_at,
    update_monster_instance,
)
from game.template_io import minimal_template_dict, validate_template_data


def test_normalize_list_cells_to_dict() -> None:
    data = {
        "version": 1,
        "width": 2,
        "height": 2,
        "player_spawn": [0, 0],
        "player_facing": "east",
        "exit": [1, 1],
        "monster_types": {},
        "monsters": [],
        "grid": [[[1, 0, 0, 1], [1, 1, 0, 0]], [[0, 0, 1, 1], [0, 1, 1, 0]]],
    }
    normalize_template_grid_for_edit(data)
    assert all(isinstance(data["grid"][y][x], dict) for y in range(2) for x in range(2))
    assert data["grid"][0][0]["n"] == 1
    validate_template_data(data)


def test_toggle_wall_shared_edge() -> None:
    data = minimal_template_dict(2, 2)
    normalize_template_grid_for_edit(data)
    g = data["grid"]
    before = g[0][0]["s"]
    toggle_wall_at(data, 0, 0, "s")
    assert g[0][0]["s"] != before
    assert g[1][0]["n"] == g[0][0]["s"]


def test_pick_wall_toggle_near_north() -> None:
    picked = pick_wall_toggle_cell_dir(
        offset_x=34.0,
        offset_y=22.0,
        pad=20.0,
        cell_size=28.0,
        width=5,
        height=5,
        edge_px=8.0,
    )
    assert picked is not None
    cx, cy, d = picked
    assert (cx, cy) == (0, 0)
    assert d == "n"


def test_apply_recursive_backtracker_preserves_monster_types() -> None:
    data = minimal_template_dict(3, 3)
    data["monster_types"] = {"x": {"phrases": ["a"], "maze_proficiency": 0.1, "sound_homing": 0.2}}
    data["monsters"] = []
    normalize_template_grid_for_edit(data)
    apply_recursive_backtracker_maze(data, 4, 4, seed=1)
    assert data["width"] == 4 and data["height"] == 4
    assert "x" in data["monster_types"]
    validate_template_data(data)


def test_apply_generated_maze_all_walls() -> None:
    data = minimal_template_dict(3, 3)
    normalize_template_grid_for_edit(data)
    apply_generated_maze(data, 4, 4, algorithm="all_walls", seed=123, params={})
    assert data["width"] == 4 and data["height"] == 4
    for row in data["grid"]:
        for cell in row:
            assert cell["n"] == 1
            assert cell["e"] == 1
            assert cell["s"] == 1
            assert cell["w"] == 1


def test_apply_generated_maze_recursive_backtracker_dispatch() -> None:
    data = minimal_template_dict(3, 3)
    normalize_template_grid_for_edit(data)
    apply_generated_maze(data, 4, 4, algorithm="recursive_backtracker", seed=1, params={})
    opened = 0
    for row in data["grid"]:
        for cell in row:
            opened += int(cell["n"] == 0) + int(cell["e"] == 0) + int(cell["s"] == 0) + int(cell["w"] == 0)
    assert opened > 0


def test_set_wall_at_and_get_wall_at_shared_edge() -> None:
    data = minimal_template_dict(2, 2)
    normalize_template_grid_for_edit(data)
    set_wall_at(data, 0, 0, "e", False)
    assert get_wall_at(data, 0, 0, "e") is False
    assert data["grid"][0][1]["w"] == 0
    set_wall_at(data, 0, 0, "e", True)
    assert get_wall_at(data, 0, 0, "e") is True
    assert data["grid"][0][1]["w"] == 1


@pytest.mark.parametrize("algorithm", ["prim", "kruskal", "wilson", "binary_tree", "sidewinder"])
def test_apply_generated_maze_selected_algorithms_validate(algorithm: str) -> None:
    data = minimal_template_dict(5, 5)
    normalize_template_grid_for_edit(data)
    apply_generated_maze(data, 5, 5, algorithm=algorithm, seed=7, params={})
    validate_template_data(data)
    opened = 0
    for row in data["grid"]:
        for cell in row:
            opened += int(cell["n"] == 0) + int(cell["e"] == 0) + int(cell["s"] == 0) + int(cell["w"] == 0)
    assert opened > 0


def test_set_wall_path_like_drag_stays_consistent() -> None:
    data = minimal_template_dict(3, 3)
    normalize_template_grid_for_edit(data)
    # Simulate a drag path: (0,0) -> (1,0) -> (1,1), opening passages.
    set_wall_at(data, 0, 0, "e", False)
    set_wall_at(data, 1, 0, "s", False)
    assert data["grid"][0][0]["e"] == 0
    assert data["grid"][0][1]["w"] == 0
    assert data["grid"][0][1]["s"] == 0
    assert data["grid"][1][1]["n"] == 0
    # Close them again (ctrl-drag style).
    set_wall_at(data, 0, 0, "e", True)
    set_wall_at(data, 1, 0, "s", True)
    assert data["grid"][0][0]["e"] == 1
    assert data["grid"][0][1]["w"] == 1
    assert data["grid"][0][1]["s"] == 1
    assert data["grid"][1][1]["n"] == 1


def test_linearity_param_present_for_applicable_algorithms() -> None:
    for key in ("recursive_backtracker", "prim", "wilson", "binary_tree", "sidewinder"):
        algo = ALGORITHMS[key]
        assert any(p.key == "linearity" for p in algo.params)


def test_linearity_influences_generation() -> None:
    data_lo = minimal_template_dict(10, 10)
    data_hi = minimal_template_dict(10, 10)
    normalize_template_grid_for_edit(data_lo)
    normalize_template_grid_for_edit(data_hi)
    apply_generated_maze(data_lo, 10, 10, algorithm="recursive_backtracker", seed=42, params={"linearity": 0})
    apply_generated_maze(data_hi, 10, 10, algorithm="recursive_backtracker", seed=42, params={"linearity": 100})
    assert data_lo["grid"] != data_hi["grid"]


def test_surface_and_poi_metadata_persist_through_normalize() -> None:
    data = minimal_template_dict(3, 3)
    normalize_template_grid_for_edit(data)
    set_surface_type_at(data, 1, 1, "dirt")
    add_room_poi_at(data, 1, 1, "dip_floor")
    add_edge_poi(data, 1, 1, "n", "engraving_wall")
    normalize_template_grid_for_edit(data)
    assert data["grid"][1][1]["surface_type"] == "dirt"
    assert isinstance(data["grid"][1][1]["room_pois"], list)
    assert data["grid"][1][1]["room_pois"][0]["poi_type"] == "dip_floor"
    assert isinstance(data["edge_pois"], list)
    assert data["edge_pois"][0]["poi_type"] == "engraving_wall"


def test_set_spawn_and_exit() -> None:
    data = minimal_template_dict(4, 4)
    normalize_template_grid_for_edit(data)
    set_player_spawn(data, 2, 1)
    set_exit_cell(data, 3, 0)
    assert data["player_spawn"] == [2, 1]
    assert data["exit"] == [3, 0]
    assert data["grid"][3][3].get("exit") is None
    assert data["grid"][0][3].get("exit") is True


def test_monster_add_and_update() -> None:
    data = minimal_template_dict(4, 4)
    data["monster_types"] = {"skeletal": {"phrases": ["clack"], "maze_proficiency": 0.5, "sound_homing": 0.5}}
    normalize_template_grid_for_edit(data)
    add_monster_instance(data, "sk2", "skeletal", 1, 2, "south")
    update_monster_instance(data, "sk2", x=3, y=3, facing="west", perception_bonus=2)
    m = data["monsters"][0]
    assert m["id"] == "sk2"
    assert m["cell"] == [3, 3]
    assert m["facing"] == "west"
    assert m["perception_bonus"] == 2
