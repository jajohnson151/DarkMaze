from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import WebSocket
import yaml

from game.resolver import PlayState, play_state_from_template_dict, play_state_to_template_dict
from game.template_edit import (
    add_edge_poi,
    add_monster_instance,
    add_room_poi_at,
    apply_generated_maze,
    normalize_template_grid_for_edit,
    remove_monster_instance,
    set_exit_cell,
    set_player_facing,
    set_player_spawn,
    set_surface_noisiness,
    set_surface_type_at,
    set_wall_at,
    update_monster_instance,
)
from game.template_io import (
    load_template,
    minimal_template_dict,
    validate_template,
    validate_template_data,
)


@dataclass
class TableSession:
    session_id: str
    state: PlayState | None = None
    template_path: Path | None = None
    """Last template applied from JSON (when not loaded from a server file path)."""
    design_template: dict[str, Any] | None = None
    player_ws: WebSocket | None = None
    gm_sockets: list[WebSocket] = field(default_factory=list)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, TableSession] = {}
        self._monster_types_path = Path(__file__).resolve().parent.parent / "config" / "monster_types.yaml"
        self._persisted_monster_types = self._load_monster_types_file()

    def _load_monster_types_file(self) -> dict[str, Any]:
        p = self._monster_types_path
        if not p.is_file():
            return {}
        with open(p, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        if isinstance(raw, dict) and isinstance(raw.get("monster_types"), dict):
            out = raw.get("monster_types", {})
        elif isinstance(raw, dict):
            out = raw
        else:
            out = {}
        fixed: dict[str, Any] = {}
        for k, v in out.items():
            if isinstance(k, str) and isinstance(v, dict):
                fixed[k] = dict(v)
        return fixed

    def _save_monster_types_file(self, monster_types: dict[str, Any]) -> None:
        p = self._monster_types_path
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "monster_types": {k: monster_types[k] for k in sorted(monster_types.keys())},
        }
        tmp = p.with_suffix(p.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=False)
        tmp.replace(p)
        self._persisted_monster_types = dict(payload["monster_types"])

    def _merge_monster_types(self, data: dict[str, Any]) -> None:
        mt = data.get("monster_types")
        if not isinstance(mt, dict):
            mt = {}
            data["monster_types"] = mt
        for k, v in self._persisted_monster_types.items():
            if k not in mt:
                mt[k] = dict(v)

    def get(self, session_id: str) -> TableSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = TableSession(session_id=session_id)
        return self._sessions[session_id]

    def load_template_into_design(self, session_id: str, path: Path) -> PlayState:
        validate_template(path)
        data = load_template(path)
        self._merge_monster_types(data)
        st = play_state_from_template_dict(data)
        st.mode = "design"
        sess = self.get(session_id)
        sess.state = st
        sess.template_path = path
        sess.design_template = dict(data)
        return st

    def apply_template_dict(self, session_id: str, data: dict[str, Any]) -> PlayState:
        self._merge_monster_types(data)
        validate_template_data(data)
        st = play_state_from_template_dict(data)
        st.mode = "design"
        sess = self.get(session_id)
        sess.state = st
        sess.template_path = None
        sess.design_template = dict(data)
        mt = data.get("monster_types")
        if isinstance(mt, dict):
            self._save_monster_types_file(mt)
        return st

    def generate_maze_design(
        self,
        session_id: str,
        width: int,
        height: int,
        algorithm: str,
        seed: int | None,
    ) -> PlayState:
        sess = self.get(session_id)
        data = dict(sess.design_template) if isinstance(sess.design_template, dict) else minimal_template_dict(width, height)
        normalize_template_grid_for_edit(data)
        apply_generated_maze(data, width, height, algorithm=algorithm, seed=seed, params={})
        return self.apply_template_dict(session_id, data)

    def _get_design_template(self, session_id: str) -> dict[str, Any]:
        sess = self.get(session_id)
        st = sess.state
        if st is not None and st.mode != "design":
            raise ValueError("design edits are only allowed in design mode")
        if isinstance(sess.design_template, dict):
            data = dict(sess.design_template)
        elif st is not None:
            data = play_state_to_template_dict(st)
        else:
            data = minimal_template_dict(8, 8)
        self._merge_monster_types(data)
        normalize_template_grid_for_edit(data)
        return data

    def _apply_design_mutation(self, session_id: str, mutate: Any) -> PlayState:
        data = self._get_design_template(session_id)
        mutate(data)
        return self.apply_template_dict(session_id, data)

    def set_design_wall(self, session_id: str, x: int, y: int, direction: str, on: bool) -> PlayState:
        if direction not in ("n", "e", "s", "w"):
            raise ValueError("direction must be one of n/e/s/w")
        return self._apply_design_mutation(session_id, lambda d: set_wall_at(d, x, y, direction, on))

    def set_design_spawn(self, session_id: str, x: int, y: int, facing: str | None = None) -> PlayState:
        def mutate(d: dict[str, Any]) -> None:
            set_player_spawn(d, x, y)
            if facing:
                set_player_facing(d, facing)

        return self._apply_design_mutation(session_id, mutate)

    def set_design_exit(self, session_id: str, x: int, y: int) -> PlayState:
        return self._apply_design_mutation(session_id, lambda d: set_exit_cell(d, x, y))

    def set_design_surface(self, session_id: str, x: int, y: int, surface_type: str | None) -> PlayState:
        return self._apply_design_mutation(session_id, lambda d: set_surface_type_at(d, x, y, surface_type))

    def set_design_surface_noisiness(self, session_id: str, surface_type: str, noisiness: int) -> PlayState:
        return self._apply_design_mutation(
            session_id, lambda d: set_surface_noisiness(d, surface_type, noisiness)
        )

    def add_design_room_poi(
        self, session_id: str, x: int, y: int, poi_type: str, note: str | None
    ) -> PlayState:
        return self._apply_design_mutation(session_id, lambda d: add_room_poi_at(d, x, y, poi_type, note))

    def add_design_edge_poi(
        self, session_id: str, x: int, y: int, direction: str, poi_type: str, note: str | None
    ) -> PlayState:
        if direction not in ("n", "e", "s", "w"):
            raise ValueError("direction must be one of n/e/s/w")
        return self._apply_design_mutation(session_id, lambda d: add_edge_poi(d, x, y, direction, poi_type, note))

    def add_design_monster(
        self,
        session_id: str,
        monster_id: str,
        monster_type: str,
        x: int,
        y: int,
        facing: str,
        perception_bonus: int = 0,
        stealth_bonus: int = 0,
    ) -> PlayState:
        return self._apply_design_mutation(
            session_id,
            lambda d: add_monster_instance(
                d, monster_id, monster_type, x, y, facing, perception_bonus, stealth_bonus
            ),
        )

    def update_design_monster(self, session_id: str, monster_id: str, **fields: Any) -> PlayState:
        return self._apply_design_mutation(
            session_id,
            lambda d: update_monster_instance(
                d,
                monster_id,
                x=fields.get("x"),
                y=fields.get("y"),
                facing=fields.get("facing"),
                monster_type=fields.get("monster_type"),
                perception_bonus=fields.get("perception_bonus"),
                stealth_bonus=fields.get("stealth_bonus"),
            ),
        )

    def remove_design_monster(self, session_id: str, monster_id: str) -> PlayState:
        return self._apply_design_mutation(session_id, lambda d: remove_monster_instance(d, monster_id))

    def start_play(self, session_id: str, seed: int | None = None) -> PlayState:
        sess = self.get(session_id)
        data: dict[str, Any] | None = None
        if sess.template_path is not None:
            validate_template(sess.template_path)
            data = load_template(sess.template_path)
        elif sess.design_template is not None:
            validate_template_data(sess.design_template)
            data = dict(sess.design_template)
        elif sess.state is not None:
            data = play_state_to_template_dict(sess.state)
            validate_template_data(data)
        else:
            raise ValueError("no template loaded")
        st = play_state_from_template_dict(data, seed=seed)
        st.mode = "play"
        st.paused = False
        st.player_stats_ready = False
        sess.state = st
        return st

    def stop_play(self, session_id: str) -> None:
        sess = self.get(session_id)
        if sess.template_path is not None:
            data = load_template(sess.template_path)
            st = play_state_from_template_dict(data)
            st.mode = "design"
            sess.state = st
        elif sess.design_template is not None:
            st = play_state_from_template_dict(dict(sess.design_template))
            st.mode = "design"
            sess.state = st
        else:
            sess.state = None

    def set_monster_goal(
        self,
        session_id: str,
        monster_id: str,
        goal_mode: str,
        goal_target: tuple[int, int] | None = None,
    ) -> PlayState:
        sess = self.get(session_id)
        st = sess.state
        if st is None:
            raise ValueError("no session state")
        if st.mode != "play":
            raise ValueError("goals can only be changed during play")
        if goal_mode not in ("catch_player", "find_bones", "return_start"):
            raise ValueError(f"unknown goal mode: {goal_mode}")
        monster = next((m for m in st.monsters if m.id == monster_id), None)
        if monster is None:
            raise ValueError(f"unknown monster id: {monster_id}")
        if goal_target is not None and not st.maze.in_bounds(goal_target[0], goal_target[1]):
            raise ValueError("goal_target out of bounds")
        monster.goal_mode = goal_mode  # type: ignore[assignment]
        monster.goal_target = goal_target
        return st


sessions = SessionManager()
