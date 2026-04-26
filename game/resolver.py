from __future__ import annotations

import random
from typing import Any
from dataclasses import dataclass, field
from game.acoustics import (
    hearing_contest,
    pick_distance_label,
    propagation_modifier,
    rel_direction8,
)
from game.actors import Actor, MonsterGoalMode, MonsterTypeDef
from game.maze import Facing, Maze, turn_left, turn_right
from game.protocol_models import (
    GMMonsterView,
    GMView,
    HeardCueModel,
    MonsterMirrorView,
    PlayerBriefing,
    PlayerView,
    SessionMode,
    WallMask,
)
from game.template_io import (
    build_actors,
    build_briefing,
    build_maze_from_template,
    build_monster_types,
    build_tuning,
    maze_to_template_grid,
)
from game.tuning import TuningConfig, k_for_player_forward, k_for_player_wait


@dataclass
class HeardInternal:
    """Server-only: source cell for bearing recompute on player turn."""

    sx: int
    sy: int
    phrase: str
    distance_label: str


@dataclass
class PlayState:
    maze: Maze
    player: Actor
    monsters: list[Actor]
    monster_types: dict[str, MonsterTypeDef]
    surface_types: dict[str, dict[str, int]]
    tuning: TuningConfig
    rng: random.Random
    briefing: PlayerBriefing | None = None
    mode: str = "design"
    paused: bool = False
    player_stats_ready: bool = False
    pending_heard: list[HeardInternal] = field(default_factory=list)
    edge_pois: list[dict[str, Any]] = field(default_factory=list)
    room_pois_by_cell: dict[tuple[int, int], list[str]] = field(default_factory=dict)
    game_over: str | None = None
    last_hear_debug: list[dict] = field(default_factory=list)

    @property
    def exit_cell(self) -> tuple[int, int]:
        for y in range(self.maze.height):
            for x in range(self.maze.width):
                if self.maze.cell(x, y).is_exit:
                    return (x, y)
        return (0, 0)


def play_state_from_template_dict(data: dict, seed: int | None = None) -> PlayState:
    maze = build_maze_from_template(data)
    player, monsters = build_actors(data, maze)
    mt = build_monster_types(data)
    raw_surfaces = data.get("surface_types") if isinstance(data.get("surface_types"), dict) else {}
    surface_types: dict[str, dict[str, int]] = {}
    for name, spec in raw_surfaces.items():
        if not isinstance(name, str):
            continue
        noisiness = 0
        if isinstance(spec, dict):
            try:
                noisiness = int(spec.get("noisiness", 0))
            except Exception:
                noisiness = 0
        surface_types[name] = {"noisiness": max(0, noisiness)}
    tuning = build_tuning(data)
    briefing = build_briefing(data)
    rng = random.Random(seed if seed is not None else 0)
    room_pois_by_cell: dict[tuple[int, int], list[str]] = {}
    grid = data.get("grid")
    if isinstance(grid, list):
        for y, row in enumerate(grid):
            if not isinstance(row, list):
                continue
            for x, cell in enumerate(row):
                if not isinstance(cell, dict):
                    continue
                pois = cell.get("room_pois")
                if not isinstance(pois, list):
                    continue
                labels: list[str] = []
                for p in pois:
                    if not isinstance(p, dict):
                        continue
                    poi_type = str(p.get("poi_type", "")).strip()
                    if not poi_type:
                        continue
                    note = str(p.get("note", "")).strip()
                    labels.append(f"{poi_type}: {note}" if note else poi_type)
                if labels:
                    room_pois_by_cell[(x, y)] = labels
    return PlayState(
        maze=maze,
        player=player,
        monsters=monsters,
        monster_types=mt,
        surface_types=surface_types,
        tuning=tuning,
        rng=rng,
        briefing=briefing,
        edge_pois=[dict(p) for p in (data.get("edge_pois") or []) if isinstance(p, dict)],
        room_pois_by_cell=room_pois_by_cell,
        mode="design",
        paused=False,
        player_stats_ready=False,
    )


def _wall_mask(maze: Maze, x: int, y: int, facing: Facing) -> WallMask:
    c = maze.cell(x, y)
    abs_walls = {"north": c.n, "east": c.e, "south": c.s, "west": c.w}
    back_f = turn_left(turn_left(facing))
    return WallMask(
        left=abs_walls[turn_left(facing)],
        right=abs_walls[turn_right(facing)],
        forward=abs_walls[facing],
        behind=abs_walls[back_f],
    )


def _phrase_for_monster(state: PlayState, m: Actor) -> str:
    tid = m.monster_type_id or "default"
    mt = state.monster_types.get(tid)
    phrases = mt.phrases if mt else ["rustle"]
    return state.rng.choice(phrases)


def _player_hears_emitter(
    state: PlayState,
    ex: int,
    ey: int,
    emitter: Actor,
    phrase: str,
    emitter_pace_stealth: int,
    wait_bonus: int,
) -> None:
    prop = propagation_modifier(state.maze, ex, ey, state.player.x, state.player.y, state.tuning)
    ok, pr, sr = hearing_contest(
        state.rng,
        state.player.perception_bonus,
        state.player.perception_roll_mode,
        wait_bonus,
        emitter.stealth_bonus,
        emitter.stealth_roll_mode,
        emitter_pace_stealth,
        prop,
    )
    margin = pr + state.player.perception_bonus + wait_bonus - (
        sr + emitter.stealth_bonus + emitter_pace_stealth - prop
    )
    state.last_hear_debug.append(
        {
            "listener": "player",
            "emitter": emitter.id,
            "pRoll": pr,
            "sRoll": sr,
            "propagationModifier": prop,
            "success": ok,
        }
    )
    if ok:
        label = pick_distance_label(state.rng, state.tuning, margin)
        state.pending_heard.append(
            HeardInternal(sx=ex, sy=ey, phrase=phrase, distance_label=label)
        )


def _monster_hears_player(
    state: PlayState,
    monster: Actor,
    player_stealth_extra: int,
) -> None:
    prop = propagation_modifier(
        state.maze, state.player.x, state.player.y, monster.x, monster.y, state.tuning
    )
    ok, pr, sr = hearing_contest(
        state.rng,
        monster.perception_bonus,
        monster.perception_roll_mode,
        0,
        state.player.stealth_bonus,
        state.player.stealth_roll_mode,
        player_stealth_extra,
        prop,
    )
    state.last_hear_debug.append(
        {
            "listener": monster.id,
            "emitter": "player",
            "pRoll": pr,
            "sRoll": sr,
            "propagationModifier": prop,
            "success": ok,
        }
    )
    if ok:
        monster.last_sound_hint = (state.player.x, state.player.y)


def _surface_noisiness_penalty(state: PlayState, actor: Actor) -> int:
    cell = state.maze.cell(actor.x, actor.y)
    st = cell.surface_type
    if not st:
        return 0
    spec = state.surface_types.get(st)
    if not isinstance(spec, dict):
        return 0
    try:
        return max(0, int(spec.get("noisiness", 0)))
    except Exception:
        return 0


def _check_lose(state: PlayState) -> None:
    for m in state.monsters:
        if m.x == state.player.x and m.y == state.player.y:
            state.game_over = "lose"


def _check_win(state: PlayState) -> None:
    c = state.maze.cell(state.player.x, state.player.y)
    if c.is_exit:
        state.game_over = "win"


def _monster_ai_tick(state: PlayState, m: Actor) -> tuple[int, int, str | None]:
    """Returns (emit_x, emit_y, phrase) if monster made noise this tick, else (m.x,m.y,None)."""
    t = state.tuning
    if m.partial_action_remaining > 0:
        m.partial_action_remaining -= 1
        if m.partial_action_kind == "forward" and m.partial_action_remaining == 0:
            nxt = state.maze.step_from(m.x, m.y, m.facing)
            if nxt:
                m.x, m.y = nxt
                m.note_enter_cell(m.x, m.y)
            phrase = _phrase_for_monster(state, m)
            return m.x, m.y, phrase
        return m.x, m.y, None

    if m.action_pool < t.action_cost_forward:
        return m.x, m.y, None

    r = state.rng.random()
    if r < 0.35:
        nxt = _goal_step(state, m)
        if nxt and m.action_pool >= t.action_cost_forward:
            m.action_pool -= t.action_cost_forward
            need = t.monster_forward_micro_increments
            if need <= 1:
                m.x, m.y = nxt
                m.note_enter_cell(m.x, m.y)
                return m.x, m.y, _phrase_for_monster(state, m)
            m.partial_action_remaining = need - 1
            m.partial_action_kind = "forward"
            return m.x, m.y, None
    elif r < 0.55:
        if m.action_pool >= t.action_cost_turn:
            m.action_pool -= t.action_cost_turn
            m.facing = turn_left(m.facing)
    elif r < 0.75:
        if m.action_pool >= t.action_cost_turn:
            m.action_pool -= t.action_cost_turn
            m.facing = turn_right(m.facing)
    else:
        if m.action_pool >= t.action_cost_wait:
            m.action_pool -= t.action_cost_wait
            return m.x, m.y, _phrase_for_monster(state, m)
    return m.x, m.y, None


def _goal_target_for_monster(state: PlayState, m: Actor) -> tuple[int, int] | None:
    mode: MonsterGoalMode = m.goal_mode
    if mode == "catch_player":
        return (state.player.x, state.player.y)
    if mode == "find_bones":
        if m.goal_target is not None:
            return m.goal_target
        for y in range(state.maze.height):
            for x in range(state.maze.width):
                c = state.maze.cell(x, y)
                if c.item and "bone" in c.item.lower():
                    return (x, y)
        return None
    if m.spawn_x is not None and m.spawn_y is not None:
        return (m.spawn_x, m.spawn_y)
    return None


def _goal_step(state: PlayState, m: Actor) -> tuple[int, int] | None:
    target = _goal_target_for_monster(state, m)
    if target is None:
        return state.maze.step_from(m.x, m.y, m.facing)
    tx, ty = target
    choices: list[tuple[int, int, Facing]] = []
    for facing in ("north", "east", "south", "west"):
        nxt = state.maze.step_from(m.x, m.y, facing)  # type: ignore[arg-type]
        if nxt is None:
            continue
        nx, ny = nxt
        dist = abs(tx - nx) + abs(ty - ny)
        choices.append((dist, state.rng.randrange(1000000), facing))  # randomized tie-break
    if not choices:
        return None
    choices.sort(key=lambda t: (t[0], t[1]))
    best_facing = choices[0][2]
    m.facing = best_facing
    return state.maze.step_from(m.x, m.y, m.facing)


def _run_micro_increments(state: PlayState, k: int, player_used_wait: bool) -> None:
    t = state.tuning
    for _ in range(k):
        for m in sorted(state.monsters, key=lambda x: x.id):
            m.action_pool += t.pool_credit_per_increment
        for m in sorted(state.monsters, key=lambda x: x.id):
            ex, ey, phrase = _monster_ai_tick(state, m)
            if phrase is not None:
                wb = t.wait_listen_bonus if player_used_wait else 0
                _player_hears_emitter(state, ex, ey, m, phrase, _surface_noisiness_penalty(state, m), wb)
        _check_lose(state)
        if state.game_over:
            return


def resolve_player_action(state: PlayState, kind: str, pace: str = "normal") -> str | None:
    if state.mode != "play":
        return "not_in_play_mode"
    if state.paused:
        return "paused"
    if not state.player_stats_ready:
        return "player_stats_required"
    if state.game_over:
        return "game_over"

    p = state.player
    t = state.tuning

    if kind in ("turn_left", "turn_right"):
        if kind == "turn_left":
            p.facing = turn_left(p.facing)
        else:
            p.facing = turn_right(p.facing)
        return None

    if kind == "forward":
        state.pending_heard.clear()
        state.last_hear_debug.clear()
        pace_ste = t.pace_stealth_penalty.get(pace, 1)
        nxt = state.maze.step_from(p.x, p.y, p.facing)
        if nxt:
            p.x, p.y = nxt
            p.note_enter_cell(p.x, p.y)
        surface_ste = _surface_noisiness_penalty(state, p)
        for m in state.monsters:
            _monster_hears_player(state, m, pace_ste + surface_ste)
        k = k_for_player_forward(pace)
        _run_micro_increments(state, k, player_used_wait=False)
        _check_win(state)
        _check_lose(state)
        return None

    if kind == "wait":
        state.pending_heard.clear()
        state.last_hear_debug.clear()
        for m in state.monsters:
            _monster_hears_player(state, m, player_stealth_extra=0)
        k = k_for_player_wait()
        _run_micro_increments(state, k, player_used_wait=True)
        _check_win(state)
        _check_lose(state)
        return None

    return "unknown_action"


def pending_heard_for_listener(
    state: PlayState, x: int, y: int, facing: Facing
) -> list[HeardCueModel]:
    out: list[HeardCueModel] = []
    for h in state.pending_heard:
        r8 = rel_direction8(x, y, facing, h.sx, h.sy)
        out.append(
            HeardCueModel(relDirection8=r8, phrase=h.phrase, distanceLabel=h.distance_label)
        )
    return out


def pending_to_models(state: PlayState) -> list[HeardCueModel]:
    return pending_heard_for_listener(state, state.player.x, state.player.y, state.player.facing)


def _heard_buckets(cues: list[HeardCueModel]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {
        "front": [],
        "frontRight": [],
        "right": [],
        "backRight": [],
        "behind": [],
        "backLeft": [],
        "left": [],
        "frontLeft": [],
    }
    rel_to_bucket = {
        0: "front",
        1: "frontRight",
        2: "right",
        3: "backRight",
        4: "behind",
        5: "backLeft",
        6: "left",
        7: "frontLeft",
    }
    for cue in cues:
        b = rel_to_bucket.get(cue.rel_direction8)
        if not b:
            continue
        out[b].append(f"{cue.distance_label} ({cue.phrase})")
    return out


def _edge_poi_buckets(state: PlayState) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"front": [], "right": [], "behind": [], "left": []}
    raw = state.__dict__.get("edge_pois", [])
    if not isinstance(raw, list):
        return out
    facing_to_idx = {"north": 0, "east": 1, "south": 2, "west": 3}
    dir_to_idx = {"n": 0, "e": 1, "s": 2, "w": 3}
    base = facing_to_idx.get(state.player.facing, 0)
    idx_to_bucket = {0: "front", 1: "right", 2: "behind", 3: "left"}
    for poi in raw:
        if not isinstance(poi, dict):
            continue
        try:
            x = int(poi.get("x"))
            y = int(poi.get("y"))
        except Exception:
            continue
        if x != state.player.x or y != state.player.y:
            continue
        d = str(poi.get("dir", "")).lower()
        if d not in dir_to_idx:
            continue
        rel = (dir_to_idx[d] - base) % 4
        bucket = idx_to_bucket[rel]
        poi_type = str(poi.get("poi_type", "")).strip()
        if not poi_type:
            continue
        note = str(poi.get("note", "")).strip()
        out[bucket].append(f"{poi_type}: {note}" if note else poi_type)
    return out


def build_monster_mirror_view(state: PlayState, m: Actor) -> MonsterMirrorView:
    c = state.maze.cell(m.x, m.y)
    return MonsterMirrorView(
        id=m.id,
        walls=_wall_mask(state.maze, m.x, m.y, m.facing),
        hazard=c.hazard,
        item=c.item,
        pendingHeardCues=pending_heard_for_listener(state, m.x, m.y, m.facing),
    )


def build_player_view(state: PlayState) -> PlayerView:
    c = state.maze.cell(state.player.x, state.player.y)
    briefing = state.briefing if state.mode == "play" else None
    sm: SessionMode = "play" if state.mode == "play" else "design"
    cues = pending_to_models(state)
    return PlayerView(
        sessionMode=sm,
        paused=state.paused,
        playerStatsReady=state.player_stats_ready,
        briefing=briefing,
        walls=_wall_mask(state.maze, state.player.x, state.player.y, state.player.facing),
        hazard=c.hazard,
        item=c.item,
        pendingHeardCues=cues,
        heardBuckets=_heard_buckets(cues),
        edgePoiBuckets=_edge_poi_buckets(state),
        centerSurface=c.surface_type,
        centerRoomPois=list(state.room_pois_by_cell.get((state.player.x, state.player.y), [])),
        gameOver=state.game_over,
    )


def build_gm_view(state: PlayState) -> GMView:
    sm: SessionMode = "play" if state.mode == "play" else "design"
    mt_payload: dict[str, dict[str, Any]] = {}
    for tid, mt in state.monster_types.items():
        mt_payload[tid] = {
            "phrases": list(mt.phrases),
            "maze_proficiency": mt.maze_proficiency,
            "sound_homing": mt.sound_homing,
        }
    return GMView(
        sessionMode=sm,
        paused=state.paused,
        width=state.maze.width,
        height=state.maze.height,
        grid=maze_to_template_grid(state.maze),
        monsterTypes=mt_payload,
        player={"x": state.player.x, "y": state.player.y, "facing": state.player.facing},
        monsters=[
            GMMonsterView(
                id=m.id,
                x=m.x,
                y=m.y,
                facing=m.facing,
                actionPool=m.action_pool,
                monsterTypeId=m.monster_type_id,
                goalMode=m.goal_mode,
                goalTarget=list(m.goal_target) if m.goal_target is not None else None,
            )
            for m in state.monsters
        ],
        exitCell=state.exit_cell,
        lastHearDebug=list(state.last_hear_debug),
        monsterMirrors=[build_monster_mirror_view(state, m) for m in state.monsters],
    )


def play_state_to_template_dict(state: PlayState) -> dict[str, Any]:
    """Round-trip current play state to a template dict for persistence / play start."""
    data: dict[str, Any] = {
        "version": 1,
        "width": state.maze.width,
        "height": state.maze.height,
        "player_spawn": [state.player.x, state.player.y],
        "player_facing": state.player.facing,
        "exit": list(state.exit_cell),
        "grid": maze_to_template_grid(state.maze),
        "monster_types": {
            tid: {
                "phrases": list(mt.phrases),
                "maze_proficiency": mt.maze_proficiency,
                "sound_homing": mt.sound_homing,
            }
            for tid, mt in state.monster_types.items()
        },
        "monsters": [
            {
                "id": m.id,
                "type": m.monster_type_id,
                "cell": [m.x, m.y],
                "facing": m.facing,
                "perception_bonus": m.perception_bonus,
                "stealth_bonus": m.stealth_bonus,
                "perception_roll_mode": m.perception_roll_mode,
                "stealth_roll_mode": m.stealth_roll_mode,
                "goal_mode": m.goal_mode,
                "goal_target": list(m.goal_target) if m.goal_target is not None else None,
            }
            for m in state.monsters
        ],
        "surface_types": dict(state.surface_types),
        "edge_pois": [dict(p) for p in state.edge_pois],
    }
    if state.briefing:
        data["player_briefing"] = {
            "welcome": state.briefing.welcome,
            "goals": state.briefing.goals,
            "commands_help": state.briefing.commands_help,
        }
    data["tuning"] = state.tuning.model_dump()
    return data


