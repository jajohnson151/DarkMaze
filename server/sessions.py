from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import WebSocket

from game.maze_gen import generate_maze
from game.resolver import PlayState, play_state_from_template_dict, play_state_to_template_dict
from game.template_io import (
    load_template,
    maze_to_template_grid,
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

    def get(self, session_id: str) -> TableSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = TableSession(session_id=session_id)
        return self._sessions[session_id]

    def load_template_into_design(self, session_id: str, path: Path) -> PlayState:
        validate_template(path)
        data = load_template(path)
        st = play_state_from_template_dict(data)
        st.mode = "design"
        sess = self.get(session_id)
        sess.state = st
        sess.template_path = path
        sess.design_template = dict(data)
        return st

    def apply_template_dict(self, session_id: str, data: dict[str, Any]) -> PlayState:
        validate_template_data(data)
        st = play_state_from_template_dict(data)
        st.mode = "design"
        sess = self.get(session_id)
        sess.state = st
        sess.template_path = None
        sess.design_template = dict(data)
        return st

    def generate_maze_design(
        self,
        session_id: str,
        width: int,
        height: int,
        algorithm: str,
        seed: int | None,
    ) -> PlayState:
        if algorithm != "recursive_backtracker":
            raise ValueError(f"unknown algorithm: {algorithm}")
        if width < 2 or height < 2:
            raise ValueError("width and height must be at least 2")
        maze = generate_maze(width, height, seed=seed)
        data = minimal_template_dict(width, height)
        data["grid"] = maze_to_template_grid(maze)
        return self.apply_template_dict(session_id, data)

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


sessions = SessionManager()
