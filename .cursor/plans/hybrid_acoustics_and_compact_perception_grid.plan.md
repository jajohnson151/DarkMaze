# Hybrid acoustics + compact perception grid

## Part A — Sound propagation (RMS path A + B)

### Path model and code touchpoints

- [`game/acoustics.py`](game/acoustics.py): BFS open-path metric (A), grid-ray wall/segment metric (B), octant-weighted RMS into `mod_eff`; optional path-adjacent wall term on A in a later pass.
- [`game/tuning.py`](game/tuning.py): `propagation_per_wall_ray`, `propagation_ray_weight_by_octant`, etc.
- [`game/resolver.py`](game/resolver.py): use hybrid `mod_eff` in contests; tie perception outputs to physics-derived bounds (see invariants below).
- [`tests/test_acoustics.py`](tests/test_acoustics.py): A/B/RMS/cap cases + **one-sided closeness** cases (below).

### Perception invariants (must hold after implementation)

1. **Loudness ceiling (prior rule)** — Perceived sound level / contest advantage from propagation must **not exceed** the physics implied by source strength and hybrid attenuation (`mod_eff`).

2. **No “closer than truth” (new rule)** — An actor must **never** be represented as **closer** (spatially / in distance band) than they actually are relative to the listener. Concretely, for any cue that carries **distance-ish** information (e.g. [`pick_distance_label`](game/acoustics.py) / `margin` driving “distant” vs “very near”):  
   - Define a **physics-only upper bound on optimism** (e.g. max margin or max closeness-band index derivable from `mod_eff` and the same contest formula with best-case rolls for the listener **only within what physics allows** — same construction as the loudness cap).  
   - **Clamp** the value used for **distance labeling** (and any parallel GM/debug fields) so perceived closeness is **at most** that bound: lucky rolls may still cause a **miss** (hear nothing) or sound **farther** than the floor implied by noise, but must **not** upgrade “far” into “right on top” when physics forbids it.  
   - **Asymmetric errors:** false “farther” / uncertain is allowed; false “closer” is not.

3. **Relation to existing `distance_band_thresholds`** — Today higher `margin` → smaller distance label index progression toward “close” ([`distance_band_index`](game/acoustics.py)). The clamp ensures the band (or equivalent) used for UX is **never more “near”** than the band implied by the physics cap.

4. **Actors** — Apply the same principle wherever another **actor** (player or monster) is the emitter and the listener gets a distance or proximity-like readout, so rules stay consistent for player ↔ monster hearing paths in [`game/resolver.py`](game/resolver.py).

## Part B — Perception grid: minimize size, ~three events per cell

### Problem

[`web/src/style.css`](web/src/style.css) `.perception-grid` uses `repeat(3, 1fr)` columns/rows and every `.perception-cell` has `aspect-ratio: 1 / 1`. Inside `#game` (`max-width: 64rem`), fringe cells become large squares even when they only show a short bucket title and `—` or one line of text. The center cell also scales with that track size.

### Goal

Outer octant cells should be **only as large as needed for about three “events”** (three list lines / cue lines). The overall grid should **not** scale to full content column width as huge squares.

### Approach

1. **Cap visible events in markup** ([`web/src/player_view_render.ts`](web/src/player_view_render.ts))  
   - In `bucketHtml` (or a thin helper), pass `items.slice(0, 3)` into the `<ul>`.  
   - If `items.length > 3`, append a single line such as `…and N more` (or `+N`) so the UI stays honest without growing the cell.

2. **CSS layout** ([`web/src/style.css`](web/src/style.css))  
   - Constrain the grid: e.g. `.perception-grid { width: fit-content; max-width: 100%; margin-inline: auto; }` plus explicit column sizing so fringe columns are **content-driven width** (narrow), not `1fr` of full play column.  
   - Example pattern: `grid-template-columns: minmax(0, max-content) minmax(6.5rem, 8.5rem) minmax(0, max-content)` and `grid-template-rows` similarly, with the **center** holding the fixed-ish wall diagram; tune `minmax` so the center remains readable (wall bars ~10px font can shrink slightly if needed).  
   - **Remove `aspect-ratio: 1/1` from outer `.perception-cell`** (keep compact height: `min-height` unset or small; optional `max-height` ~3 lines + title + padding with `overflow-y: auto` only if you prefer scroll over hard cap—default to **slice to 3** + no scroll).  
   - Optionally add `.perception-cell--diag` with slightly smaller max width than cardinal cells if diagonals stay text-only.

3. **Wall inset**  
   - If the center column/row becomes too tight, reduce `.center` padding / `.wall-bar` font-size slightly in the same stylesheet so three wall labels still fit without forcing the whole 3×3 to blow up.

4. **Verify**  
   - Build `web` and sanity-check play layout at narrow and wide viewport; confirm eight sectors stay compact with 0, 1, and 3+ items (third shows overflow hint).

### Files

| File | Change |
|------|--------|
| [`web/src/player_view_render.ts`](web/src/player_view_render.ts) | Cap bucket list at 3 items + overflow hint in `bucketHtml`. |
| [`web/src/style.css`](web/src/style.css) | Compact grid template; drop outer square aspect-ratio; optional center min size tuning. |

### Out of scope

- GM `gm.css` monster mirror unless you want the same compact pattern there (can mirror later).

---

## Part C — Web GM design mode parity with offline designer

### Reference: offline designer

[`designer/app.py`](designer/app.py) (Tkinter) includes:

- **Quick generate** — reuses `_last_generate_params` (width, height, algorithm, params), picks a **new random seed** each click, calls the same `apply_generated_maze` path as full generate ([`_quick_generate_maze`](designer/app.py) vs [`_generate_maze`](designer/app.py)).
- **Full maze generation UI** — all entries from [`game/maze_gen.ALGORITHMS`](game/maze_gen.py), plus **algorithm-specific params** (e.g. linearity) rendered from each algorithm’s `params` tuple.
- **File** New / Open / Save — disk YAML workflow (web session uses `designTemplate` over WebSocket instead; true file parity is optional).

### Gaps today (web)

| Offline | Web today |
|--------|------------|
| Quick generate (one click, last dims + algo + params, random seed) | Only **Generate**; empty seed already random on server, but there is **no one-click “repeat last”** and no memory of last params beyond whatever is left in the inputs. |
| Full `ALGORITHMS` list + dynamic param fields | [`web/gm.html`](web/gm.html) algorithm `<select>` effectively **only lists** `recursive_backtracker`; [`sessions.generate_maze_design`](server/sessions.py) passes **`params={}`** always — no parity with Tk for algorithms that honor params. |
| — | **GM player mirror in design** uses [`build_player_view`](game/resolver.py) with `playerStatsReady` from state (default **False**). [`renderPlayerView`](web/src/player_view_render.ts) keeps `#gm-game` hidden until stats/onboarding complete — so the GM **does not see the wall/surroundings preview** without a play flow / player, even though design mode never sends the player client `state.player_view`. |

### Root cause: “full edit mode” without a player

Players never receive `state.player_view` when `st.mode != "play"` ([`server/main.py`](server/main.py) `hello` branch). Only GMs receive `state.gm_view` + `playerView`. So it is **safe** to treat **design-mode** `PlayerView` as a **GM-only preview**: e.g. when `state.mode == "design"`, set `playerStatsReady=True` in `build_player_view` (or add an explicit `surroundingsPreview: true`) so the GM Home **Player mirror** shows walls / center / heard buckets from template spawn **without** a connected player. Document that this field is “relaxed” in design for GM preview only.

If `sess.state is None` (e.g. default template failed to load on startup), [`_broadcast_session`](server/main.py) **returns early** and the GM may get **no** `state.gm_view` after `hello` — hard to “enter” any edit mode. Mitigation: on GM `hello`, if `st is None` but `design_template` exists, still send a minimal payload; or **always** ensure startup loads a fallback `minimal_template_dict` into design so `state` is never `None` for `default` session.

### Plan (implementation)

1. **Quick regen** — [`web/gm.html`](web/gm.html) + [`web/src/gm.ts`](web/src/gm.ts): add **Quick generate** next to Generate. On each successful generate (or on click), store `lastGen = { width, height, algorithm, params }` in module state; Quick sends `gm.design.generate_maze` with those fields and **omits seed** (server `None` → new maze, same as empty seed today). Optionally clear the seed input on Quick for visual parity with Tk.

2. **Algorithm list + params** — Either populate `<select id="maze-gen-algo">` from a **static list** mirroring `ALGORITHMS` keys, or add a small **HTTP or WS** “catalog” message listing keys + param specs from Python (single source of truth). Extend `gm.design.generate_maze` payload and [`generate_maze_design`](server/sessions.py) to accept **`params`** dict and pass through to [`apply_generated_maze`](game/template_edit.py). Render param inputs in the maze view (same pattern as Tk `_render_algorithm_param_fields`).

3. **GM design preview** — [`game/resolver.py`](game/resolver.py) `build_player_view`: when `state.mode == "design"`, set `playerStatsReady=True` (or equivalent) so GM mirror renders surroundings. **Do not** change play-mode behavior.

4. **Robust GM hello** — [`server/main.py`](server/main.py): if GM connects with `st is None`, send `state.gm_view` built from `sess.design_template` or `minimal_template_dict` + `play_state_from_template_dict` so maze/monster tabs can hydrate; or fix startup so `state` is never null for default session.

5. **Docs** — [`docs/GM_MANUAL.md`](docs/GM_MANUAL.md) / README: note Quick regen + algorithm parity + “no player needed for maze design” after fixes.

### Out of scope (unless requested)

- Disk New/Open/Save from browser (would need download/upload endpoints or File System Access API).
- **Validate** as a dedicated web button (can reuse `validate_template_data` on apply only).

---

## Implementation todos

- [ ] `acoustics-paths` — BFS + ray + RMS + octant weights in `game/acoustics.py`
- [ ] `tuning-knobs` — extend `TuningConfig`
- [ ] `resolver-wire` — hybrid modifier + margin cap in `game/resolver.py`
- [ ] `tests-acoustics` — `tests/test_acoustics.py` (RMS, caps, **no-closer-than-truth** distance band / margin cases for player and monster listeners)
- [ ] `perception-grid-compact` — slice 3 + CSS grid shrink in `web/src/player_view_render.ts` + `web/src/style.css`
- [ ] `web-quick-regen` — Quick generate button + last-gen memory in `web/gm.html` + `web/src/gm.ts`
- [ ] `web-maze-algorithms` — Full algorithm dropdown + optional params in HTML/TS; `gm.design.generate_maze` + `generate_maze_design` pass `params`
- [ ] `gm-design-preview` — `build_player_view` design-mode `playerStatsReady` (or explicit preview flag) + optional GM `hello` when `state is None`
