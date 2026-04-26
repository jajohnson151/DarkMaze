from pathlib import Path

import pytest

from game.resolver import build_gm_view, build_player_view, play_state_from_template_dict, resolve_player_action
from game.template_io import load_template


@pytest.fixture
def example_data() -> dict:
    root = Path(__file__).resolve().parent.parent / "templates" / "example.yaml"
    return load_template(root)


def test_play_state_from_template(example_data: dict) -> None:
    st = play_state_from_template_dict(example_data, seed=42)
    assert st.maze.width == 5
    assert st.player.x == 1 and st.player.y == 1


def test_turn_no_time_advance(example_data: dict) -> None:
    st = play_state_from_template_dict(example_data, seed=1)
    st.mode = "play"
    st.player_stats_ready = True
    facing_before = st.player.facing
    err = resolve_player_action(st, "turn_left", "normal")
    assert err is None
    assert st.player.facing != facing_before


def test_player_view_no_coords_leak(example_data: dict) -> None:
    st = play_state_from_template_dict(example_data, seed=1)
    st.mode = "play"
    st.player_stats_ready = True
    pv = build_player_view(st)
    dumped = pv.model_dump(by_alias=True)
    assert "x" not in dumped
    assert "pendingHeardCues" in dumped
    assert "heardBuckets" in dumped
    assert "edgePoiBuckets" in dumped


def test_player_view_center_surface_and_room_pois() -> None:
    data = {
        "version": 1,
        "width": 3,
        "height": 3,
        "player_spawn": [1, 1],
        "player_facing": "north",
        "exit": [2, 2],
        "monster_types": {"default": {"phrases": ["rustle"], "maze_proficiency": 0.5, "sound_homing": 0.5}},
        "monsters": [],
        "grid": [
            [{"n": 1, "e": 0, "s": 0, "w": 1}, {"n": 1, "e": 0, "s": 0, "w": 0}, {"n": 1, "e": 1, "s": 0, "w": 0}],
            [
                {"n": 0, "e": 0, "s": 0, "w": 1},
                {
                    "n": 0,
                    "e": 0,
                    "s": 0,
                    "w": 0,
                    "surface_type": "dirt",
                    "room_pois": [{"poi_type": "bones", "note": "old"}],
                },
                {"n": 0, "e": 1, "s": 0, "w": 0},
            ],
            [{"n": 0, "e": 0, "s": 1, "w": 1}, {"n": 0, "e": 0, "s": 1, "w": 0}, {"n": 0, "e": 1, "s": 1, "w": 0}],
        ],
        "edge_pois": [{"x": 1, "y": 1, "dir": "n", "poi_type": "engraving", "note": "fresh"}],
    }
    st = play_state_from_template_dict(data, seed=1)
    st.mode = "play"
    st.player_stats_ready = True
    pv = build_player_view(st).model_dump(by_alias=True)
    assert pv["centerSurface"] == "dirt"
    assert pv["centerRoomPois"] == ["bones: old"]
    assert pv["edgePoiBuckets"]["front"] == ["engraving: fresh"]


def test_surface_noisiness_penalizes_player_stealth(example_data: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    data = dict(example_data)
    grid = data.get("grid") or []
    if not grid:
        # Build a simple explicit grid if template has none.
        w = int(data["width"])
        h = int(data["height"])
        data["grid"] = [[{"n": 0, "e": 0, "s": 0, "w": 0} for _ in range(w)] for _ in range(h)]
        grid = data["grid"]
    data["surface_types"] = {"standing water": {"noisiness": 4}}
    px, py = data["player_spawn"]
    grid[py][px]["surface_type"] = "standing water"
    if py > 0:
        grid[py - 1][px]["surface_type"] = "standing water"

    captured: dict[str, int] = {}

    def fake_hearing_contest(
        _rng: object,
        _listener_bonus: int,
        _listener_roll_mode: str,
        _wait_bonus: int,
        _emitter_bonus: int,
        _emitter_roll_mode: str,
        emitter_pace_stealth: int,
        _prop: int,
    ) -> tuple[bool, int, int]:
        captured["emitter_pace_stealth"] = max(captured.get("emitter_pace_stealth", 0), emitter_pace_stealth)
        return (False, 1, 1)

    monkeypatch.setattr("game.resolver.hearing_contest", fake_hearing_contest)
    st = play_state_from_template_dict(data, seed=1)
    st.mode = "play"
    st.player_stats_ready = True
    resolve_player_action(st, "forward", "normal")
    assert captured["emitter_pace_stealth"] >= 4


def test_gm_view_includes_monster_goal_fields(example_data: dict) -> None:
    st = play_state_from_template_dict(example_data, seed=1)
    st.mode = "play"
    st.player_stats_ready = True
    st.monsters[0].goal_mode = "return_start"
    st.monsters[0].goal_target = (0, 0)
    gv = build_gm_view(st).model_dump(by_alias=True)
    assert gv["monsters"][0]["goalMode"] == "return_start"
    assert gv["monsters"][0]["goalTarget"] == [0, 0]


def test_gm_view_includes_monster_mirrors(example_data: dict) -> None:
    st = play_state_from_template_dict(example_data, seed=1)
    st.mode = "play"
    st.player_stats_ready = True
    gv = build_gm_view(st).model_dump(by_alias=True)
    mirrors = gv["monsterMirrors"]
    assert len(mirrors) == len(gv["monsters"])
    for mm in mirrors:
        assert "id" in mm
        w = mm["walls"]
        assert set(w.keys()) == {"left", "right", "forward", "behind"}
        assert "pendingHeardCues" in mm


def test_return_start_goal_moves_toward_spawn(example_data: dict) -> None:
    st = play_state_from_template_dict(example_data, seed=2)
    st.mode = "play"
    st.player_stats_ready = True
    m = st.monsters[0]
    m.spawn_x, m.spawn_y = m.x, m.y
    # Move monster away from spawn and set return goal.
    m.x, m.y = max(0, m.x - 1), min(st.maze.height - 1, m.y + 1)
    m.goal_mode = "return_start"
    before = abs(m.x - (m.spawn_x or 0)) + abs(m.y - (m.spawn_y or 0))
    for _ in range(4):
        resolve_player_action(st, "wait", "normal")
    after = abs(m.x - (m.spawn_x or 0)) + abs(m.y - (m.spawn_y or 0))
    assert after <= before
