from pydantic import BaseModel, Field


class TuningConfig(BaseModel):
    pool_credit_per_increment: int = 1
    action_cost_turn: int = 1
    action_cost_forward: int = 1
    action_cost_wait: int = 1
    monster_forward_micro_increments: int = 1
    wait_listen_bonus: int = 2
    pace_stealth_penalty: dict[str, int] = Field(
        default_factory=lambda: {"cautious": 0, "normal": 1, "fast": 2}
    )
    pace_perception_penalty: dict[str, int] = Field(
        default_factory=lambda: {"cautious": 0, "normal": 1, "fast": 2}
    )
    propagation_base: int = 12
    propagation_per_step: int = 2
    distance_band_thresholds: list[int] = Field(default_factory=lambda: [2, 6, 12])
    distance_band_labels: list[list[str]] = Field(
        default_factory=lambda: [
            ["distant", "far-off"],
            ["muffled", "faint"],
            ["near", "close"],
            ["very near!", "right on top of you"],
        ]
    )


def k_for_player_forward(pace: str) -> int:
    return {"cautious": 3, "normal": 2, "fast": 1}.get(pace, 2)


def k_for_player_wait() -> int:
    return 3
