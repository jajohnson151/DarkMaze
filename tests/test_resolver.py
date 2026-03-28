from pathlib import Path

import pytest

from game.resolver import build_player_view, play_state_from_template_dict, resolve_player_action
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
