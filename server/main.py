from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from game.protocol_models import PROTOCOL_VERSION, Pace, PlayerActionKind
from game.resolver import (
    build_gm_view,
    build_player_view,
    resolve_player_action,
)
from server.sessions import sessions

app = FastAPI(title="Dark Maze")

_DEFAULT_TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "example.yaml"


@app.on_event("startup")
async def _startup_load_template() -> None:
    if _DEFAULT_TEMPLATE.is_file():
        try:
            sessions.load_template_into_design("default", _DEFAULT_TEMPLATE)
        except Exception:
            pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _json(obj: Any) -> str:
    return json.dumps(obj, default=str)


async def _send(ws: WebSocket, payload: dict[str, Any]) -> None:
    await ws.send_text(_json(payload))


async def _broadcast_session(session_id: str) -> None:
    sess = sessions.get(session_id)
    st = sess.state
    if st is None:
        return
    pv = build_player_view(st).model_dump(by_alias=True)
    gv = build_gm_view(st).model_dump(by_alias=True)
    if sess.player_ws:
        try:
            await _send(sess.player_ws, {"type": "state.player_view", **pv})
        except Exception:
            pass
    for gws in list(sess.gm_sockets):
        try:
            gm_payload: dict[str, Any] = {"type": "state.gm_view", **gv, "playerView": pv}
            if st.mode == "design" and isinstance(sess.design_template, dict):
                gm_payload["designTemplate"] = sess.design_template
            await _send(gws, gm_payload)
        except Exception:
            pass


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    sess = sessions.get(session_id)
    role: str | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            mtype = msg.get("type")
            if mtype == "hello":
                role = msg.get("role", "player")
                if role == "player":
                    sess.player_ws = websocket
                elif websocket not in sess.gm_sockets:
                    sess.gm_sockets.append(websocket)
                st = sess.state
                if role == "player":
                    if st is None or st.mode != "play":
                        await _send(
                            websocket,
                            {
                                "type": "session.waiting",
                                "protocol": PROTOCOL_VERSION,
                                "message": "Session not in play mode yet.",
                            },
                        )
                    elif st:
                        await _send(
                            websocket,
                            {
                                "type": "state.player_view",
                                **build_player_view(st).model_dump(by_alias=True),
                            },
                        )
                elif st:
                    gm_payload: dict[str, Any] = {
                        "type": "state.gm_view",
                        **build_gm_view(st).model_dump(by_alias=True),
                    }
                    if st.mode == "design" and isinstance(sess.design_template, dict):
                        gm_payload["designTemplate"] = sess.design_template
                    await _send(
                        websocket,
                        gm_payload,
                    )
                continue

            if mtype == "gm.design.apply_template":
                if role != "gm":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "gm only"},
                    )
                    continue
                tmpl = msg.get("template")
                if not isinstance(tmpl, dict):
                    await _send(
                        websocket,
                        {
                            "type": "error",
                            "protocol": PROTOCOL_VERSION,
                            "message": "template must be an object",
                        },
                    )
                    continue
                try:
                    sessions.apply_template_dict(session_id, tmpl)
                    await _broadcast_session(session_id)
                except Exception as e:
                    await _send(
                        websocket,
                        {
                            "type": "error",
                            "protocol": PROTOCOL_VERSION,
                            "message": str(e),
                        },
                    )
                continue

            if mtype == "gm.design.generate_maze":
                if role != "gm":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "gm only"},
                    )
                    continue
                try:
                    width = int(msg["width"])
                    height = int(msg["height"])
                    algorithm = str(msg.get("algorithm", "recursive_backtracker"))
                    raw_seed = msg.get("seed")
                    seed = int(raw_seed) if raw_seed is not None else None
                    sessions.generate_maze_design(session_id, width, height, algorithm, seed)
                    await _broadcast_session(session_id)
                except (KeyError, ValueError) as e:
                    await _send(
                        websocket,
                        {
                            "type": "error",
                            "protocol": PROTOCOL_VERSION,
                            "message": str(e),
                        },
                    )
                except Exception as e:
                    await _send(
                        websocket,
                        {
                            "type": "error",
                            "protocol": PROTOCOL_VERSION,
                            "message": str(e),
                        },
                    )
                continue

            if mtype == "gm.design.set_wall":
                if role != "gm":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "gm only"},
                    )
                    continue
                try:
                    x = int(msg.get("x"))
                    y = int(msg.get("y"))
                    direction = str(msg.get("dir", ""))
                    on = bool(msg.get("on"))
                    sessions.set_design_wall(session_id, x, y, direction, on)
                    await _broadcast_session(session_id)
                except Exception as e:
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": str(e)},
                    )
                continue

            if mtype == "gm.design.set_spawn":
                if role != "gm":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "gm only"},
                    )
                    continue
                try:
                    x = int(msg.get("x"))
                    y = int(msg.get("y"))
                    facing = msg.get("facing")
                    sessions.set_design_spawn(
                        session_id, x, y, facing=str(facing) if facing is not None else None
                    )
                    await _broadcast_session(session_id)
                except Exception as e:
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": str(e)},
                    )
                continue

            if mtype == "gm.design.set_exit":
                if role != "gm":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "gm only"},
                    )
                    continue
                try:
                    x = int(msg.get("x"))
                    y = int(msg.get("y"))
                    sessions.set_design_exit(session_id, x, y)
                    await _broadcast_session(session_id)
                except Exception as e:
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": str(e)},
                    )
                continue

            if mtype == "gm.design.set_surface":
                if role != "gm":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "gm only"},
                    )
                    continue
                try:
                    x = int(msg.get("x"))
                    y = int(msg.get("y"))
                    raw_surface = msg.get("surfaceType")
                    surface = str(raw_surface) if raw_surface not in (None, "") else None
                    sessions.set_design_surface(session_id, x, y, surface)
                    await _broadcast_session(session_id)
                except Exception as e:
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": str(e)},
                    )
                continue

            if mtype == "gm.design.set_surface_noisiness":
                if role != "gm":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "gm only"},
                    )
                    continue
                try:
                    surface_type = str(msg.get("surfaceType", ""))
                    noisiness = int(msg.get("noisiness", 0))
                    sessions.set_design_surface_noisiness(session_id, surface_type, noisiness)
                    await _broadcast_session(session_id)
                except Exception as e:
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": str(e)},
                    )
                continue

            if mtype == "gm.design.add_room_poi":
                if role != "gm":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "gm only"},
                    )
                    continue
                try:
                    x = int(msg.get("x"))
                    y = int(msg.get("y"))
                    poi_type = str(msg.get("poiType", ""))
                    note = msg.get("note")
                    sessions.add_design_room_poi(
                        session_id, x, y, poi_type, str(note) if isinstance(note, str) else None
                    )
                    await _broadcast_session(session_id)
                except Exception as e:
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": str(e)},
                    )
                continue

            if mtype == "gm.design.add_edge_poi":
                if role != "gm":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "gm only"},
                    )
                    continue
                try:
                    x = int(msg.get("x"))
                    y = int(msg.get("y"))
                    direction = str(msg.get("dir", ""))
                    poi_type = str(msg.get("poiType", ""))
                    note = msg.get("note")
                    sessions.add_design_edge_poi(
                        session_id,
                        x,
                        y,
                        direction,
                        poi_type,
                        str(note) if isinstance(note, str) else None,
                    )
                    await _broadcast_session(session_id)
                except Exception as e:
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": str(e)},
                    )
                continue

            if mtype == "gm.design.add_monster":
                if role != "gm":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "gm only"},
                    )
                    continue
                try:
                    sessions.add_design_monster(
                        session_id,
                        monster_id=str(msg.get("monsterId", "")),
                        monster_type=str(msg.get("monsterType", "")),
                        x=int(msg.get("x")),
                        y=int(msg.get("y")),
                        facing=str(msg.get("facing", "south")),
                        perception_bonus=int(msg.get("perceptionBonus", 0)),
                        stealth_bonus=int(msg.get("stealthBonus", 0)),
                    )
                    await _broadcast_session(session_id)
                except Exception as e:
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": str(e)},
                    )
                continue

            if mtype == "gm.design.update_monster":
                if role != "gm":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "gm only"},
                    )
                    continue
                try:
                    fields: dict[str, Any] = {}
                    if "x" in msg:
                        fields["x"] = int(msg.get("x"))
                    if "y" in msg:
                        fields["y"] = int(msg.get("y"))
                    if "facing" in msg:
                        fields["facing"] = str(msg.get("facing"))
                    if "monsterType" in msg:
                        fields["monster_type"] = str(msg.get("monsterType"))
                    if "perceptionBonus" in msg:
                        fields["perception_bonus"] = int(msg.get("perceptionBonus"))
                    if "stealthBonus" in msg:
                        fields["stealth_bonus"] = int(msg.get("stealthBonus"))
                    sessions.update_design_monster(session_id, str(msg.get("monsterId", "")), **fields)
                    await _broadcast_session(session_id)
                except Exception as e:
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": str(e)},
                    )
                continue

            if mtype == "gm.design.remove_monster":
                if role != "gm":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "gm only"},
                    )
                    continue
                try:
                    sessions.remove_design_monster(session_id, str(msg.get("monsterId", "")))
                    await _broadcast_session(session_id)
                except Exception as e:
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": str(e)},
                    )
                continue

            st = sess.state
            if st is None:
                await _send(
                    websocket,
                    {"type": "error", "protocol": PROTOCOL_VERSION, "message": "no session state"},
                )
                continue

            if mtype == "gm.load_template":
                path = Path(msg["path"])
                sessions.load_template_into_design(session_id, path)
                await _broadcast_session(session_id)
                continue

            if mtype == "gm.play.start":
                seed = msg.get("seed")
                sessions.start_play(session_id, seed=int(seed) if seed is not None else None)
                await _broadcast_session(session_id)
                continue

            if mtype == "gm.play.stop":
                sessions.stop_play(session_id)
                await _broadcast_session(session_id)
                continue

            if mtype == "gm.play.pause":
                if st.mode == "play":
                    st.paused = True
                await _broadcast_session(session_id)
                continue

            if mtype == "gm.play.resume":
                if st.mode == "play":
                    st.paused = False
                await _broadcast_session(session_id)
                continue

            if mtype == "gm.monster.set_goal":
                if role != "gm":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "gm only"},
                    )
                    continue
                try:
                    monster_id = str(msg.get("monsterId", ""))
                    goal_mode = str(msg.get("goalMode", ""))
                    raw_target = msg.get("goalTarget")
                    goal_target: tuple[int, int] | None = None
                    if isinstance(raw_target, list) and len(raw_target) == 2:
                        goal_target = (int(raw_target[0]), int(raw_target[1]))
                    sessions.set_monster_goal(session_id, monster_id, goal_mode, goal_target)
                    await _broadcast_session(session_id)
                except Exception as e:
                    await _send(
                        websocket,
                        {
                            "type": "error",
                            "protocol": PROTOCOL_VERSION,
                            "message": str(e),
                        },
                    )
                continue

            if mtype == "player.set_stats":
                if st.mode != "play":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "not in play"},
                    )
                    continue
                st.player.perception_bonus = int(msg.get("perception_bonus", 0))
                st.player.stealth_bonus = int(msg.get("stealth_bonus", 0))
                st.player_stats_ready = True
                await _broadcast_session(session_id)
                continue

            if mtype == "player.action":
                if role != "player":
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "player only"},
                    )
                    continue
                if st.paused:
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": "paused"},
                    )
                    continue
                kind: PlayerActionKind = msg.get("kind", "wait")
                pace: Pace = msg.get("pace", "normal")
                err = resolve_player_action(st, kind, pace)
                if err:
                    await _send(
                        websocket,
                        {"type": "error", "protocol": PROTOCOL_VERSION, "message": err},
                    )
                await _broadcast_session(session_id)
                continue

            await _send(
                websocket,
                {"type": "error", "protocol": PROTOCOL_VERSION, "message": f"unknown type {mtype}"},
            )

    except WebSocketDisconnect:
        if sess.player_ws is websocket:
            sess.player_ws = None
        if websocket in sess.gm_sockets:
            sess.gm_sockets.remove(websocket)
