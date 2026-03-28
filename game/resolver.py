from __future__ import annotations

import random
from dataclasses import dataclass, field
from game.acoustics import (
    hearing_contest,
    pick_distance_label,
    propagation_modifier,
    rel_direction8,
)
from game.actors import Actor, MonsterTypeDef
from game.maze import Facing, Maze, turn_left, turn_right
from game.protocol_models import (
    GMMonsterView,
    GMView,
    HeardCueModel,
    PlayerBriefing,
    PlayerView,
    SessionMode,
    WallMask,
)
from game.template_io import build_actors, build_briefing, build_maze_from_template, build_monster_types, build_tuning
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
    tuning: TuningConfig
    rng: random.Random
    briefing: PlayerBriefing | None = None
    mode: str = "design"
    paused: bool = False
    player_stats_ready: bool = False
    pending_heard: list[HeardInternal] = field(default_factory=list)
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
    tuning = build_tuning(data)
    briefing = build_briefing(data)
    rng = random.Random(seed if seed is not None else 0)
    return PlayState(
        maze=maze,
        player=player,
        monsters=monsters,
        monster_types=mt,
        tuning=tuning,
        rng=rng,
        briefing=briefing,
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
        nxt = state.maze.step_from(m.x, m.y, m.facing)
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


def _run_micro_increments(state: PlayState, k: int, player_used_wait: bool) -> None:
    t = state.tuning
    for _ in range(k):
        for m in sorted(state.monsters, key=lambda x: x.id):
            m.action_pool += t.pool_credit_per_increment
        for m in sorted(state.monsters, key=lambda x: x.id):
            ex, ey, phrase = _monster_ai_tick(state, m)
            if phrase is not None:
                wb = t.wait_listen_bonus if player_used_wait else 0
                _player_hears_emitter(state, ex, ey, m, phrase, 0, wb)
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
        for m in state.monsters:
            _monster_hears_player(state, m, pace_ste)
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


def pending_to_models(state: PlayState) -> list[HeardCueModel]:
    out: list[HeardCueModel] = []
    for h in state.pending_heard:
        r8 = rel_direction8(state.player.x, state.player.y, state.player.facing, h.sx, h.sy)
        out.append(
            HeardCueModel(relDirection8=r8, phrase=h.phrase, distanceLabel=h.distance_label)
        )
    return out


def build_player_view(state: PlayState) -> PlayerView:
    c = state.maze.cell(state.player.x, state.player.y)
    briefing = state.briefing if state.mode == "play" else None
    sm: SessionMode = "play" if state.mode == "play" else "design"
    return PlayerView(
        sessionMode=sm,
        paused=state.paused,
        playerStatsReady=state.player_stats_ready,
        briefing=briefing,
        walls=_wall_mask(state.maze, state.player.x, state.player.y, state.player.facing),
        hazard=c.hazard,
        item=c.item,
        pendingHeardCues=pending_to_models(state),
        gameOver=state.game_over,
    )


def build_gm_view(state: PlayState) -> GMView:
    sm: SessionMode = "play" if state.mode == "play" else "design"
    return GMView(
        sessionMode=sm,
        paused=state.paused,
        width=state.maze.width,
        height=state.maze.height,
        player={"x": state.player.x, "y": state.player.y, "facing": state.player.facing},
        monsters=[
            GMMonsterView(
                id=m.id,
                x=m.x,
                y=m.y,
                facing=m.facing,
                actionPool=m.action_pool,
                monsterTypeId=m.monster_type_id,
            )
            for m in state.monsters
        ],
        exitCell=state.exit_cell,
        lastHearDebug=list(state.last_hear_debug),
    )


