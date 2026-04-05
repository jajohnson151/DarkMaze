from game.maze import Maze, turn_left, turn_right


def test_empty_maze_outer_boundary() -> None:
    """Outer ring has walls; (0,0) cannot leave north/west."""
    m = Maze.empty(3, 3)
    assert m.can_step(0, 0, "north") is False
    assert m.can_step(0, 0, "west") is False


def test_empty_maze_interior_passages() -> None:
    """Interior cells connect (no interior walls in Maze.empty)."""
    m = Maze.empty(3, 3)
    assert m.can_step(1, 1, "north") is True


def test_all_walls_no_passages() -> None:
    m = Maze.all_walls(3, 3)
    assert m.can_step(1, 1, "north") is False
    assert m.can_step(1, 1, "east") is False


def test_turn_left_right() -> None:
    assert turn_left("north") == "west"
    assert turn_right("north") == "east"
