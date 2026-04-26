from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

PROTOCOL_VERSION = 1

Pace = Literal["cautious", "normal", "fast"]
PlayerActionKind = Literal["turn_left", "turn_right", "forward", "wait"]
SessionMode = Literal["design", "play"]


class HeardCueModel(BaseModel):
    rel_direction8: int = Field(..., ge=0, le=7, alias="relDirection8")
    phrase: str
    distance_label: str = Field(alias="distanceLabel")

    model_config = {"populate_by_name": True}


class WallMask(BaseModel):
    left: bool
    right: bool
    forward: bool
    behind: bool


class PlayerBriefing(BaseModel):
    welcome: str | None = None
    goals: str | None = None
    commands_help: str | None = Field(None, alias="commandsHelp")

    model_config = {"populate_by_name": True}


class PlayerView(BaseModel):
    protocol: int = PROTOCOL_VERSION
    session_mode: SessionMode = Field(alias="sessionMode")
    paused: bool = False
    player_stats_ready: bool = Field(False, alias="playerStatsReady")
    briefing: PlayerBriefing | None = None
    walls: WallMask
    hazard: str | None = None
    item: str | None = None
    pending_heard_cues: list[HeardCueModel] = Field(default_factory=list, alias="pendingHeardCues")
    heard_buckets: dict[str, list[str]] = Field(
        default_factory=dict,
        alias="heardBuckets",
        description="Directional perceived sounds by relative sectors.",
    )
    edge_poi_buckets: dict[str, list[str]] = Field(
        default_factory=dict,
        alias="edgePoiBuckets",
        description="Directional edge POIs by cardinal relative sectors.",
    )
    center_surface: str | None = Field(None, alias="centerSurface")
    center_room_pois: list[str] = Field(default_factory=list, alias="centerRoomPois")
    game_over: str | None = Field(None, alias="gameOver")

    model_config = {"populate_by_name": True}


class GMMonsterView(BaseModel):
    id: str
    x: int
    y: int
    facing: str
    action_pool: int = Field(alias="actionPool")
    monster_type_id: str | None = Field(None, alias="monsterTypeId")
    goal_mode: str = Field("catch_player", alias="goalMode")
    goal_target: list[int] | None = Field(None, alias="goalTarget")


class MonsterMirrorView(BaseModel):
    """GM-only: walls and heard cues from a monster’s cell and facing (like player view, no coords)."""

    id: str
    walls: WallMask
    hazard: str | None = None
    item: str | None = None
    pending_heard_cues: list[HeardCueModel] = Field(default_factory=list, alias="pendingHeardCues")

    model_config = {"populate_by_name": True}


class GMView(BaseModel):
    protocol: int = PROTOCOL_VERSION
    session_mode: SessionMode = Field(alias="sessionMode")
    paused: bool = False
    width: int
    height: int
    """Per-cell wall data and optional hazard/item/exit; same shape as YAML grid."""
    grid: list[list[dict[str, Any]]] = Field(default_factory=list)
    monster_types: dict[str, dict[str, Any]] = Field(default_factory=dict, alias="monsterTypes")
    player: dict[str, Any]
    monsters: list[GMMonsterView]
    exit_cell: tuple[int, int] = Field(alias="exitCell")
    last_hear_debug: list[dict[str, Any]] = Field(default_factory=list, alias="lastHearDebug")
    monster_mirrors: list[MonsterMirrorView] = Field(default_factory=list, alias="monsterMirrors")

    model_config = {"populate_by_name": True}


def envelope(msg_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": msg_type, "protocol": PROTOCOL_VERSION, **payload}
