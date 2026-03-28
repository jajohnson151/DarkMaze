# Dark Maze

Authoritative Python server (FastAPI + WebSockets), pure `game/` logic, CLI for templates, Vite clients for player and GM.

## Quick start

```bash
cd DarkMaze
pip install -e ".[dev]"
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
cd web
npm install
npm run dev
```

- Player: http://localhost:5173/
- GM: http://localhost:5173/gm.html

CLI:

```bash
darkmaze design validate templates/example.yaml
darkmaze play start --template templates/example.yaml
```

## Tests

```bash
pytest
```
