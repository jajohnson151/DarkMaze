from __future__ import annotations

from pathlib import Path

import typer
import yaml

from game.maze_gen import generate_maze
from game.template_io import validate_template

app = typer.Typer(help="Dark Maze CLI")
design = typer.Typer(help="Design-time commands")
play = typer.Typer(help="Play-time helpers")
app.add_typer(design, name="design")
app.add_typer(play, name="play")


@design.command("validate")
def design_validate(path: Path) -> None:
    """Validate a maze template YAML."""
    validate_template(path)
    typer.echo(f"OK: {path}")


@design.command("autogen")
def design_autogen(
    width: int = typer.Option(5, "--width", "-w"),
    height: int = typer.Option(5, "--height", "-h"),
    seed: int | None = typer.Option(None, "--seed", "-s"),
    output: Path = typer.Option(Path("maze_out.yaml"), "--output", "-o"),
) -> None:
    """Generate a perfect maze and write a minimal template YAML."""
    maze = generate_maze(width, height, seed=seed)
    grid = []
    for y in range(height):
        row = []
        for x in range(width):
            c = maze.cell(x, y)
            row.append([int(c.n), int(c.e), int(c.s), int(c.w)])
        grid.append(row)
    data = {
        "version": 1,
        "width": width,
        "height": height,
        "player_spawn": [0, 0],
        "player_facing": "east",
        "exit": [width - 1, height - 1],
        "monster_types": {},
        "monsters": [],
        "grid": grid,
    }
    with open(output, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    typer.echo(f"Wrote {output} (add monster_types/monsters to play)")


@play.command("start")
def play_start(
    template: Path = typer.Option(
        Path("templates/example.yaml"),
        "--template",
        "-t",
        exists=True,
        readable=True,
    ),
) -> None:
    """Validate template and remind how to run the server."""
    validate_template(template)
    typer.echo(f"Template OK: {template}")
    typer.echo("Run: uvicorn server.main:app --reload --host 0.0.0.0 --port 8000")
    typer.echo("GM client: connect WebSocket, send gm.play.start (default session loads example.yaml).")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
