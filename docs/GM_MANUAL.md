# Dark Maze — Game Master (GM) User Manual

This guide is for the person running the **GM client** in the browser: session control, design-time editing, and how it connects to the server.

---

## 1. What you need running

Two processes are required:

| Process | Typical command | Purpose |
|--------|------------------|--------|
| **Game server** | `py -3 -m uvicorn server.main:app --host 127.0.0.1 --port 8000` | Authoritative game state, WebSocket API |
| **Web dev server** | In `web/`: `npm install` then `npm run dev` | Serves the GM and player HTML/JS (port **5173**) |

Install Python deps once from the repo root:

```bash
pip install -e ".[dev]"
```

**Important:** Open the GM page from **Vite** (`http://localhost:5173/gm.html`), **not** from `http://127.0.0.1:8000/`. The API on port 8000 does not serve the GM UI; it only exposes `/health` and WebSockets.

---

## 2. Opening the GM client

1. Start **uvicorn** (port **8000**).
2. Start **Vite** in `web/` (port **5173**, or another port if Vite prints a different one).
3. In your browser, go to: **http://localhost:5173/gm.html**  
   (If you use `127.0.0.1` for the page, keep host consistent; the client opens WebSockets to the same hostname on port 8000.)

The page connects to session **`default`** at `ws://<your-host>:8000/ws/default`.

---

## 2a. Navigation (three views)

The GM UI has a top bar with three views:

| View | Purpose |
|------|--------|
| **Home** | Session info, **Play start / stop / pause / resume**, and the raw JSON log. No maze or monster editors here. |
| **Maze editor** | Canvas wall editor, **Apply template to server**, and **Generate** (procedural maze). |
| **Monster types** | List and edit `monster_types`, then **Apply template to server**. |

**Apply** from either **Maze editor** or **Monster types** sends the **full** current template (grid, spawn, exit, monsters, types). Edits made in one view are included when you apply from the other, as long as you have received state from the server at least once.

---

## 3. Session modes: design vs play

The server keeps the `default` session in one of two modes:

| Mode | Meaning |
|------|--------|
| **design** | Maze/template is being prepared. Players see “waiting” until you start play. |
| **play** | Active run; players can move after they submit stats. |

On server startup, the default template (`templates/example.yaml`) is loaded in **design** mode.

- **Play start** — switches to **play** (new run from the current template).
- **Play stop (design)** — returns to **design** and reloads the template from the last saved source (file or last applied JSON).

---

## 4. Control buttons (Home view)

Open the **Home** view for session controls:

| Button | Effect |
|--------|--------|
| **Play start** | Begin **play** mode from the current template. |
| **Play stop (design)** | Return to **design** mode. |
| **Pause** | While in **play**, pauses resolution (player actions rejected while paused). |
| **Resume** | Clears pause in **play** mode. |

While the session is in **play** mode, the **Maze editor** and **Monster types** views show *Stop play to edit* and their controls are disabled.

---

## 5. Maze editor (design mode)

Open **Maze editor** from the top navigation.

- **Canvas** — click near a wall segment to toggle it. Shared edges between two cells stay consistent.
- **Markers** — **P** = player spawn, **E** = exit cell, **M** = monsters (read-only overlays in this version; moving spawn/exit/monsters is not done on the canvas yet).
- **Apply template to server** — validates and sends the full template (same protocol as the monster view).
- **Generate new maze** — **Width**, **Height**, optional integer **Seed**, and **Algorithm** (currently `recursive_backtracker`). **Generate** calls `gm.design.generate_maze` on the server, which replaces the session with a new maze and default spawn/exit (empty `monster_types` / `monsters` until you add them again).

Server validation errors from apply or other actions also appear in status text on **Home** and **Maze editor** when the server sends an `error` message.

---

## 6. Monster types (design mode)

Open **Monster types** from the top navigation.

- The list and fields reflect **`monster_types`** on the current template (phrases, maze proficiency, sound homing).
- **Add type** — enter a type id (letters, numbers, underscore; must be unique). New types get default phrase `rustle` and 0.5 / 0.5 floats until you edit them.
- **Delete type** — disabled while any **monster** instance still uses that type; remove or reassign those monsters in the template first (today that usually means editing YAML or applying a template that fixes references).
- **Apply template to server** — sends the **full** working template (grid, spawn, exit, monsters, monster types, etc.) as JSON. The server validates it; errors appear in the status line.

After a successful apply, the server broadcasts updated state to all GM connections.

---

## 7. Raw state (JSON)

Expand **“Raw GM state (JSON)”** to see the latest `state.gm_view` message. Use this for debugging (positions, `sessionMode`, grid, etc.). It is not required for normal play.

---

## 8. Loading templates from disk (advanced)

The server supports **`gm.load_template`** with a **`path`** on the **machine running uvicorn** (not your PC’s path if the server is remote). The current GM web UI does not expose this; it can be sent from browser dev tools or a custom tool if needed.

---

## 9. Troubleshooting

| Problem | What to check |
|---------|----------------|
| Blank or stuck GM | Confirm **8000** and **5173** are both running; refresh `gm.html`. |
| WebSocket errors | Firewall; correct host; only one app on port 8000. |
| “Port already in use” (8000) | Another uvicorn (or app) is using 8000 — stop it or pick another port (and update client if you change the port). |
| Apply template fails | Read the error text — often a missing key, monster `type` not in `monster_types`, or actor out of bounds. |
| CORS errors | Page must be served from `http://localhost:5173` or `http://127.0.0.1:5173` as configured on the server. |

---

## 10. Related docs

- Product spec and phases: [plan_v2.md](plan_v2.md)  
- Repo setup and CLI: [README.md](../README.md)
