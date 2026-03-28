from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import WebSocket

from game.resolver import PlayState, play_state_from_template_dict
from game.template_io import load_template, validate_template


@dataclass
class TableSession:
    session_id: str
    state: PlayState | None = None
    template_path: Path | None = None
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
        return st

    def start_play(self, session_id: str, seed: int | None = None) -> PlayState:
        sess = self.get(session_id)
        if sess.template_path is None and sess.state is None:
            raise ValueError("no template loaded")
        path = sess.template_path
        if path is None:
            raise ValueError("no template path")
        validate_template(path)
        data = load_template(path)
        st = play_state_from_template_dict(data, seed=seed)
        st.mode = "play"
        st.paused = False
        st.player_stats_ready = False
        sess.state = st
        return st

    def stop_play(self, session_id: str) -> None:
        sess = self.get(session_id)
        if sess.template_path:
            data = load_template(sess.template_path)
            st = play_state_from_template_dict(data)
            st.mode = "design"
            sess.state = st
        else:
            sess.state = None


sessions = SessionManager()
