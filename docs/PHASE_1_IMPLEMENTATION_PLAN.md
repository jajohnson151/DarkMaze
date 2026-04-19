# Phase 1 — Implementation Plan

**Authority:** [plan_v2.md](plan_v2.md) is the only product spec for this plan.

**Note on §7:** Section **7. Execution Phases** in `plan_v2.md` is marked *(unchanged)* and does not inline phase text. Phase 1 below is therefore **defined explicitly** as the first implementation slice that fits **§4.8 (Play Mode preconditions)**, **§5.3 (template data model)**, **§6 (Play Mode — resolver/hearing, etc., unchanged)**, and **§9 (Key Principles)** without building the full **§4.1–4.11** GM lifecycle UI (Working vs Active, Accept/Discard, top menu, canvas) in this phase.

---

## 1. Phase 1 goal

Deliver a **reliable, authoritative play path**: a **valid, committed maze** (template) can be loaded into the session, the GM can enter **play** mode, and the **player client** can complete a run using **movement and wall feedback** only. The server remains the source of truth.

**Intentional deferrals (later phases):**

- Full **Working Maze / Active Maze** UX, **Accept / Discard / Re-do**, and **§4.10** layout (top menu + contextual controls + main canvas).
- **§5.1** graphical wall drag (open/close) and placement tools on a canvas.
- **§5.2** generation UI wired to every **§4.6** nuance (server may already expose `gm.design.generate_maze`; Phase 1 does not require GM buttons for it).

Phase 1 may still use a **single committed template** per session (today’s mental model: “active” data only), as long as **play** does not use unvalidated drafts and **§9** is not violated (no silent overwrite of play-authoritative data).

---

## 2. In scope (checklist)

| Area | Requirement (trace to plan_v2) |
|------|--------------------------------|
| Template / maze | **§5.3:** `width`, `height`, `grid`, `player_spawn`, `exit`, `monsters`, `monster_types` supported by server validation and `PlayState`. |
| Play entry | **§4.8:** Preconditions enforced before or at **Start Play**: spawn, exit, valid grid (define “valid” minimally: bounds, shared walls consistent, template passes `validate_template_data`). |
| Play mode | **§6:** Existing play rules (paused/design rejection, resolver) remain correct; no regression. |
| Player client | Readable **wall-relative** view; **keyboard** controls + **visible key binding legend** (align with Wizardry-style intent in architecture §3.2 player client). |
| GM client | Minimum to run a session: **start/stop play** and any existing **apply template** path; **no** requirement for graphical maze editor in Phase 1. |
| Docs | GM manual accurate for Phase 1 capabilities ([GM_MANUAL.md](GM_MANUAL.md) updated if behavior changes). |

---

## 3. Out of scope for Phase 1

- **§4.2–4.7** state machine **in the GM UI** (Working vs Active labels, Accept/Discard flows, Edit Maze → copy).
- **§4.9–4.10** “maze always displayed” **graphical** canvas (JSON/log-only GM is acceptable for Phase 1).
- **§5.1** interactive wall editing and placement tools on a map.
- Replacing **§7** in `plan_v2.md` with explicit phase bullets (optional editorial follow-up, not blocking implementation).

---

## 4. Current codebase vs Phase 1

**Already close:**

- `game/maze.py`, `template_io.py`, `resolver.py`, WebSocket **player** / **GM** messages, `gm.design.apply_template`, `gm.design.generate_maze`, design vs play `sessionMode`, player **buttons** and optional **keyboard** (verify and complete per §2).
- `GMView` includes `grid` and `monsterTypes` for future canvas; not required to drive Phase 1 acceptance.

**Gaps to close (typical):**

1. **Explicit play precondition checks** at `gm.play.start` (or equivalent): fail fast with a clear error if spawn/exit/grid/monster references are invalid (beyond current `validate_template_data` if anything is missing).
2. **Player UX:** keyboard parity with on-screen actions + **always-visible or obvious** key legend.
3. **Tests:** maze wall semantics, `Maze.all_walls`, movement/win/lose path, design/paused rejection (pytest).
4. **TypeScript:** strict `tsc` clean for GM modules if CI runs `tsc`.
5. **GM_MANUAL.md:** state Phase 1 limits (no graphical maze editor) so expectations match **plan_v2** long-term vs current UI.

---

## 5. Implementation sequence

1. **Server — play gate**  
   - Add a small `assert_play_ready(template_dict)` (or reuse/extend `validate_template_data`) and call from `start_play` path so **§4.8** is enforced in one place.  
   - Return structured WebSocket `error` to GM if start fails.

2. **Player client**  
   - Confirm `W/A/D/Space` (and arrows) send `player.action` with current pace.  
   - Ensure legend in DOM matches bound keys.  
   - Ignore keys while focus is in inputs.

3. **Tests**  
   - Lock wall + movement + outer boundary + `all_walls` behavior.  
   - Optional: one integration test from template dict → `play_state_from_template_dict` → one `resolve_player_action` forward toward exit.

4. **GM / docs**  
   - Short note in GM manual: full **§4** GM design client is later; Phase 1 uses template file + apply + play controls only.

5. **Hardening**  
   - Run `pytest`, `npx tsc --noEmit` in `web/`, manual smoke: GM start play, player reaches exit or game over.

---

## 6. Acceptance criteria (Phase 1 done when)

- [ ] From a **valid** default or applied template, **Play start** succeeds and player receives **state.player_view** with walls/heard cues as today.  
- [ ] **Play start** on an **invalid** template fails with a **clear** error (no silent hang).  
- [ ] Player can use **keyboard** for turn / forward / wait with **visible** binding help.  
- [ ] **pytest** passes; **tsc** passes if project standard includes it.  
- [ ] **GM_MANUAL** does not imply a graphical maze editor exists unless one is implemented.

---

## 7. Files likely touched

| File | Change |
|------|--------|
| [server/sessions.py](../server/sessions.py) | Optional: centralize validation call in `start_play`. |
| [server/main.py](../server/main.py) | Surface validation errors on `gm.play.start` to GM WebSocket. |
| [game/template_io.py](../game/template_io.py) | Optional: `play_ready` / extra checks for §4.8. |
| [web/src/main.ts](../web/src/main.ts), [web/index.html](../web/index.html), [web/src/style.css](../web/src/style.css) | Keyboard + legend polish. |
| [tests/test_maze.py](../tests/test_maze.py) (and/or new test module) | Movement / validation tests. |
| [docs/GM_MANUAL.md](GM_MANUAL.md) | Phase 1 scope note. |

---

## 8. Follow-on (not Phase 1)

Implement **§4**–**§5** as subsequent phases: Working vs Active session model, Accept/Discard, graphical canvas, generation and redo UI, placement tools — each with its own implementation plan once Phase 1 is signed off.
