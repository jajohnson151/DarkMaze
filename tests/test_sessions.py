from pathlib import Path

import pytest
import yaml

from server.sessions import SessionManager


def _example_template() -> Path:
    return Path(__file__).resolve().parent.parent / "templates" / "example.yaml"


def test_set_monster_goal_requires_play_mode() -> None:
    sm = SessionManager()
    sm.load_template_into_design("s1", _example_template())
    with pytest.raises(ValueError):
        sm.set_monster_goal("s1", "skel1", "catch_player", None)


def test_set_monster_goal_updates_live_state() -> None:
    sm = SessionManager()
    sm.load_template_into_design("s1", _example_template())
    sm.start_play("s1", seed=1)
    st = sm.set_monster_goal("s1", "skel1", "find_bones", (1, 1))
    m = next(mm for mm in st.monsters if mm.id == "skel1")
    assert m.goal_mode == "find_bones"
    assert m.goal_target == (1, 1)


def test_generate_maze_design_preserves_monster_types() -> None:
    sm = SessionManager()
    sm.load_template_into_design("s1", _example_template())
    st = sm.generate_maze_design("s1", 9, 7, "recursive_backtracker", seed=42)
    assert st.maze.width == 9
    assert st.maze.height == 7
    assert st.monster_types


def test_monster_types_persist_to_config(tmp_path: Path) -> None:
    p = tmp_path / "monster_types.yaml"
    sm = SessionManager()
    sm._monster_types_path = p
    sm._persisted_monster_types = {}
    sm.load_template_into_design("s1", _example_template())
    payload = dict(sm.get("s1").design_template or {})
    payload["monster_types"]["new_t"] = {
        "phrases": ["tap"],
        "maze_proficiency": 0.7,
        "sound_homing": 0.4,
    }
    sm.apply_template_dict("s1", payload)
    saved = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert "monster_types" in saved
    assert "new_t" in saved["monster_types"]


def test_monster_types_loaded_from_config(tmp_path: Path) -> None:
    p = tmp_path / "monster_types.yaml"
    p.write_text(
        "monster_types:\n  persisted:\n    phrases: [hum]\n    maze_proficiency: 0.2\n    sound_homing: 0.9\n",
        encoding="utf-8",
    )
    sm = SessionManager()
    sm._monster_types_path = p
    sm._persisted_monster_types = sm._load_monster_types_file()
    sm.load_template_into_design("s1", _example_template())
    tpl = sm.get("s1").design_template or {}
    assert "persisted" in (tpl.get("monster_types") or {})
