from game.maze import Maze, turn_left, turn_right


def test_empty_maze_outer_walls() -> None:
    m = Maze.empty(3, 3)
    assert m.can_step(1, 1, "north") is False
    assert m.can_step(1, 1, "south") is False
    assert m.can_step(1, 1, "east") is False
    assert m.can_step(1, 1, "west") is False


def test_turn_left_right() -> None:
    assert turn_left("north") == "west"
    assert turn_right("north") == "east"
