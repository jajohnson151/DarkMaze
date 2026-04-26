import {
  MonsterTypeEditor,
  gmViewToWorkingTemplate,
  validateWorkingTemplate,
  type GmViewMsg,
  type WorkingTemplate,
} from "./gm_monster_editor";
import { MazeCanvasEditor, type MazeEditMode } from "./gm_maze_canvas";
import { renderMonsterMirrors } from "./monster_mirror_render";
import { renderPlayerView, type PlayerView } from "./player_view_render";

const SESSION = "default";
const WS_URL = `ws://${window.location.hostname}:8000/ws/${SESSION}`;

type GmViewId = "home" | "maze" | "monsters";
type Facing = "north" | "east" | "south" | "west";

type ArmedMonster = {
  monsterId: string;
  monsterType: string;
  facing: Facing;
  perceptionBonus: number;
  stealthBonus: number;
};

const logEl = document.getElementById("log")!;
const designStatus = document.getElementById("design-status")!;
const mazeStatus = document.getElementById("maze-status")!;
const monsterRoot = document.getElementById("monster-types-root")!;
const gmApp = document.getElementById("gm-app")!;
const viewHome = document.getElementById("view-home")!;
const viewMaze = document.getElementById("view-maze")!;
const viewMonsters = document.getElementById("view-monsters")!;
const mazePlayNotice = document.getElementById("maze-play-notice")!;
const monstersPlayNotice = document.getElementById("monsters-play-notice")!;
const mazeDesignLock = document.getElementById("maze-design-lock")!;
const monstersEditable = document.getElementById("monsters-editable")!;
const mazeCanvasEl = document.getElementById("maze-canvas") as HTMLCanvasElement;
const mazeCanvasHomeEl = document.getElementById("maze-canvas-home") as HTMLCanvasElement;
const btnApplyMaze = document.getElementById("btn-apply-maze") as HTMLButtonElement;
const btnMazeGenerate = document.getElementById("btn-maze-generate") as HTMLButtonElement;
const mazeGenW = document.getElementById("maze-gen-w") as HTMLInputElement;
const mazeGenH = document.getElementById("maze-gen-h") as HTMLInputElement;
const mazeGenSeed = document.getElementById("maze-gen-seed") as HTMLInputElement;
const mazeGenAlgo = document.getElementById("maze-gen-algo") as HTMLSelectElement;
const mazeMode = document.getElementById("maze-mode") as HTMLSelectElement;
const playerFacingSelect = document.getElementById("maze-player-facing") as HTMLSelectElement;
const surfacePanel = document.getElementById("surface-panel")!;
const poiPanel = document.getElementById("poi-panel")!;
const monsterPanel = document.getElementById("monster-panel")!;
const surfaceTypeSelect = document.getElementById("surface-type") as HTMLSelectElement;
const surfaceNewType = document.getElementById("surface-new-type") as HTMLInputElement;
const surfaceNoisiness = document.getElementById("surface-noisiness") as HTMLInputElement;
const btnSurfaceSave = document.getElementById("btn-surface-save") as HTMLButtonElement;
const poiTypeInput = document.getElementById("poi-type") as HTMLInputElement;
const poiNoteInput = document.getElementById("poi-note") as HTMLInputElement;
const monsterIdInput = document.getElementById("monster-id") as HTMLInputElement;
const monsterTypeSelect = document.getElementById("monster-type-select") as HTMLSelectElement;
const monsterFacingSelect = document.getElementById("monster-facing") as HTMLSelectElement;
const monsterPerInput = document.getElementById("monster-per") as HTMLInputElement;
const monsterSteInput = document.getElementById("monster-ste") as HTMLInputElement;
const monsterListRoot = document.getElementById("monster-list-root")!;
const monsterPlaceStatus = document.getElementById("monster-place-status")!;
const btnArmMonster = document.getElementById("btn-arm-monster") as HTMLButtonElement;

const navButtons = Array.from(document.querySelectorAll<HTMLButtonElement>(".gm-nav-btn"));
const monsterGoalsRoot = document.getElementById("monster-goals-root")!;
const monsterMirrorsRoot = document.getElementById("gm-monster-mirrors-root")!;

let gmOnboardingShown = true;
let sharedWorking: WorkingTemplate | null = null;
let armedMonster: ArmedMonster | null = null;

function log(obj: unknown) {
  logEl.textContent = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
}

function viewElements(id: GmViewId): HTMLElement {
  switch (id) {
    case "home":
      return viewHome;
    case "maze":
      return viewMaze;
    case "monsters":
      return viewMonsters;
  }
}

function setView(view: GmViewId) {
  const views: GmViewId[] = ["home", "maze", "monsters"];
  for (const id of views) {
    const el = viewElements(id);
    const active = id === view;
    el.classList.toggle("view--hidden", !active);
    el.hidden = !active;
    el.setAttribute("aria-hidden", active ? "false" : "true");
  }
  for (const btn of navButtons) {
    const isActive = btn.dataset.view === view;
    btn.classList.toggle("gm-nav-btn--active", isActive);
    if (isActive) btn.setAttribute("aria-current", "page");
    else btn.removeAttribute("aria-current");
  }
  if (view === "maze") mazeEditor.refresh();
  if (view === "home") mazeHomeEditor.refresh();
}

function setSessionMode(mode: "design" | "play") {
  gmApp.classList.toggle("gm-app--play", mode === "play");
  const editingLocked = mode === "play";
  mazePlayNotice.hidden = !editingLocked;
  monstersPlayNotice.hidden = !editingLocked;
  mazeDesignLock.classList.toggle("view-body--locked", editingLocked);
  monstersEditable.classList.toggle("view-body--locked", editingLocked);
  const applyBtn = document.getElementById("btn-apply-template") as HTMLButtonElement | null;
  if (applyBtn) applyBtn.disabled = editingLocked;
  btnApplyMaze.disabled = editingLocked;
  btnMazeGenerate.disabled = editingLocked;
  mazeGenW.disabled = editingLocked;
  mazeGenH.disabled = editingLocked;
  mazeGenSeed.disabled = editingLocked;
  mazeGenAlgo.disabled = editingLocked;
}

for (const btn of navButtons) {
  btn.addEventListener("click", () => {
    const v = btn.dataset.view as GmViewId | undefined;
    if (v === "home" || v === "maze" || v === "monsters") setView(v);
  });
}

const ws = new WebSocket(WS_URL);

const editor = new MonsterTypeEditor(monsterRoot, ws, (s) => {
  designStatus.textContent = s;
});

function send(payload: Record<string, unknown>) {
  ws.send(JSON.stringify(payload));
}

function canvasMode(): MazeEditMode {
  const v = mazeMode.value as MazeEditMode;
  return v;
}

const mazeEditor = new MazeCanvasEditor(mazeCanvasEl, {
  onWallSet: (x, y, dir, on) => {
    send({ type: "gm.design.set_wall", x, y, dir, on });
  },
  onSpawnSet: (x, y) => {
    send({ type: "gm.design.set_spawn", x, y, facing: playerFacingSelect.value });
  },
  onExitSet: (x, y) => {
    send({ type: "gm.design.set_exit", x, y });
  },
  onSurfaceSet: (x, y, surfaceType) => {
    send({ type: "gm.design.set_surface", x, y, surfaceType });
  },
  onRoomPoiAdd: (x, y, poiType, note) => {
    send({ type: "gm.design.add_room_poi", x, y, poiType, note });
  },
  onEdgePoiAdd: (x, y, dir, poiType, note) => {
    send({ type: "gm.design.add_edge_poi", x, y, dir, poiType, note });
  },
  onMonsterPlace: (x, y) => {
    if (!armedMonster) return;
    send({
      type: "gm.design.add_monster",
      ...armedMonster,
      x,
      y,
    });
    monsterPlaceStatus.textContent = `Placed ${armedMonster.monsterId} at (${x}, ${y})`;
    armedMonster = null;
    mazeMode.value = "walls";
    applyModeVisibility();
  },
});
const mazeHomeEditor = new MazeCanvasEditor(mazeCanvasHomeEl, { readOnly: true });

function applyModeVisibility() {
  const mode = canvasMode();
  mazeEditor.setMode(mode);
  surfacePanel.hidden = mode !== "surface";
  poiPanel.hidden = !(mode === "room_poi" || mode === "edge_poi");
  monsterPanel.hidden = mode !== "monster";
}

function refreshSurfaceControls() {
  const w = sharedWorking;
  if (!w) return;
  const surfaceTypes = w.surface_types ?? {};
  const keys = Object.keys(surfaceTypes).sort();
  const options = ['<option value="">(clear)</option>', ...keys.map((k) => `<option value="${escapeHtml(k)}">${escapeHtml(k)}</option>`)];
  surfaceTypeSelect.innerHTML = options.join("");
  const selected = surfaceTypeSelect.value || (keys[0] ?? "");
  if (selected) {
    surfaceTypeSelect.value = selected;
    const n = surfaceTypes[selected]?.noisiness ?? 0;
    surfaceNoisiness.value = String(Number.isFinite(Number(n)) ? Number(n) : 0);
  }
  mazeEditor.setSurfaceType(surfaceTypeSelect.value || null);
}

function refreshMonsterTypeControls() {
  const w = sharedWorking;
  if (!w) return;
  const typeIds = Object.keys(w.monster_types).sort();
  monsterTypeSelect.innerHTML = typeIds
    .map((id) => `<option value="${escapeHtml(id)}">${escapeHtml(id)}</option>`)
    .join("");
}

function renderMonsterList() {
  const w = sharedWorking;
  if (!w) {
    monsterListRoot.innerHTML = "";
    return;
  }
  if (!w.monsters.length) {
    monsterListRoot.innerHTML = "<p class=\"hint\">No monsters in template.</p>";
    return;
  }
  monsterListRoot.innerHTML = w.monsters
    .map(
      (m) => `<div class="monster-list-item" data-mid="${escapeAttr(m.id)}">
      <strong>${escapeHtml(m.id)}</strong>
      <span>type: ${escapeHtml(m.type)}</span>
      <span>cell: (${m.cell[0]}, ${m.cell[1]})</span>
      <span>facing: ${escapeHtml(m.facing)}</span>
      <button type="button" class="monster-del">Delete</button>
    </div>`,
    )
    .join("");
  for (const row of Array.from(monsterListRoot.querySelectorAll<HTMLElement>(".monster-list-item"))) {
    const mid = row.dataset.mid ?? "";
    row.querySelector(".monster-del")?.addEventListener("click", () => {
      send({ type: "gm.design.remove_monster", monsterId: mid });
    });
  }
}

function applySharedTemplate(statusOnMaze: string) {
  editor.flushFromDom();
  const w = sharedWorking;
  if (!w) {
    designStatus.textContent = "No template";
    mazeStatus.textContent = "No template";
    return;
  }
  const err = validateWorkingTemplate(w);
  if (err) {
    designStatus.textContent = err;
    mazeStatus.textContent = err;
    return;
  }
  send({ type: "gm.design.apply_template", template: w });
  designStatus.textContent = statusOnMaze;
  mazeStatus.textContent = statusOnMaze;
}

function hydrateFromGmView(msg: GmViewMsg) {
  sharedWorking = gmViewToWorkingTemplate(msg);
  editor.setWorking(sharedWorking);
  mazeEditor.setWorking(sharedWorking);
  mazeHomeEditor.setWorking(sharedWorking);
  renderGoalControls(msg);
  renderMonsterMirrors(monsterMirrorsRoot, msg.monsterMirrors);
  refreshSurfaceControls();
  refreshMonsterTypeControls();
  renderMonsterList();
}

function renderGoalControls(msg: GmViewMsg) {
  const monsters = msg.monsters ?? [];
  if (!monsters.length) {
    monsterGoalsRoot.innerHTML = "<p>No monsters in session.</p>";
    return;
  }
  monsterGoalsRoot.innerHTML = monsters
    .map(
      (m) => `
      <div class="goal-row" data-mid="${m.id}">
        <strong>${m.id}</strong>
        <label>Goal
          <select class="goal-mode">
            ${["catch_player", "find_bones", "return_start"]
              .map((g) => `<option value="${g}" ${m.goalMode === g ? "selected" : ""}>${g}</option>`)
              .join("")}
          </select>
        </label>
        <label>Target x <input class="goal-x" type="number" value="${m.goalTarget?.[0] ?? ""}" /></label>
        <label>y <input class="goal-y" type="number" value="${m.goalTarget?.[1] ?? ""}" /></label>
        <button type="button" class="goal-apply">Apply</button>
      </div>`,
    )
    .join("");
  for (const row of Array.from(monsterGoalsRoot.querySelectorAll<HTMLElement>(".goal-row"))) {
    const btn = row.querySelector<HTMLButtonElement>(".goal-apply");
    if (!btn) continue;
    btn.onclick = () => {
      const monsterId = row.dataset.mid ?? "";
      const goalMode = (row.querySelector(".goal-mode") as HTMLSelectElement | null)?.value ?? "catch_player";
      const xRaw = (row.querySelector(".goal-x") as HTMLInputElement | null)?.value.trim() ?? "";
      const yRaw = (row.querySelector(".goal-y") as HTMLInputElement | null)?.value.trim() ?? "";
      const payload: Record<string, unknown> = { type: "gm.monster.set_goal", monsterId, goalMode };
      if (xRaw !== "" && yRaw !== "") payload.goalTarget = [Number(xRaw), Number(yRaw)];
      send(payload);
      designStatus.textContent = `Sent goal update for ${monsterId}`;
    };
  }
}

function renderPlayerMirror(v: PlayerView) {
  gmOnboardingShown = renderPlayerView(
    v,
    {
      pausedBanner: document.getElementById("gm-paused-banner")!,
      waiting: document.getElementById("gm-waiting")!,
      onboarding: document.getElementById("gm-onboarding")!,
      stats: document.getElementById("gm-stats")!,
      game: document.getElementById("gm-game")!,
      wallTop: document.getElementById("gm-w-top")!,
      wallBottom: document.getElementById("gm-w-bot")!,
      wallLeft: document.getElementById("gm-w-left")!,
      wallRight: document.getElementById("gm-w-right")!,
      cornerNW: document.getElementById("gm-corner-nw")!,
      cornerNE: document.getElementById("gm-corner-ne")!,
      cornerSW: document.getElementById("gm-corner-sw")!,
      cornerSE: document.getElementById("gm-corner-se")!,
      center: document.getElementById("gm-center")!,
      heard: document.getElementById("gm-heard")!,
      actionButtons: [],
    },
    gmOnboardingShown,
  );
}

mazeMode.addEventListener("change", () => applyModeVisibility());
surfaceTypeSelect.addEventListener("change", () => {
  const v = surfaceTypeSelect.value || null;
  mazeEditor.setSurfaceType(v);
  const n = sharedWorking?.surface_types?.[v ?? ""]?.noisiness ?? 0;
  surfaceNoisiness.value = String(n);
});
poiTypeInput.addEventListener("input", () => mazeEditor.setPoiType(poiTypeInput.value));
poiNoteInput.addEventListener("input", () => mazeEditor.setPoiNote(poiNoteInput.value));

btnSurfaceSave.addEventListener("click", () => {
  const typeName = (surfaceNewType.value.trim() || surfaceTypeSelect.value || "").trim();
  if (!typeName) {
    designStatus.textContent = "Surface type required";
    return;
  }
  send({
    type: "gm.design.set_surface_noisiness",
    surfaceType: typeName,
    noisiness: Number(surfaceNoisiness.value) || 0,
  });
  surfaceNewType.value = "";
  designStatus.textContent = `Saved surface type ${typeName}`;
});

btnArmMonster.addEventListener("click", () => {
  const monsterId = monsterIdInput.value.trim();
  const monsterType = monsterTypeSelect.value.trim();
  const facing = monsterFacingSelect.value as Facing;
  if (!monsterId) {
    monsterPlaceStatus.textContent = "Monster id required";
    return;
  }
  if (!monsterType) {
    monsterPlaceStatus.textContent = "Monster type required";
    return;
  }
  armedMonster = {
    monsterId,
    monsterType,
    facing,
    perceptionBonus: Number(monsterPerInput.value) || 0,
    stealthBonus: Number(monsterSteInput.value) || 0,
  };
  mazeMode.value = "monster";
  applyModeVisibility();
  monsterPlaceStatus.textContent = `Armed. Click a cell to place ${monsterId}.`;
});

ws.onopen = () => {
  send({ type: "hello", role: "gm" });
};
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data as string) as Record<string, unknown>;
  log(msg);
  if (msg.type === "state.gm_view") {
    const mode = msg.sessionMode === "play" ? "play" : "design";
    setSessionMode(mode);
    hydrateFromGmView(msg as unknown as GmViewMsg);
    const pv = (msg as { playerView?: PlayerView }).playerView;
    if (pv) renderPlayerMirror(pv);
  }
  if (msg.type === "error") {
    const m = String((msg as { message?: string }).message ?? "error");
    designStatus.textContent = m;
    mazeStatus.textContent = m;
  }
};
ws.onerror = () => console.error("WS error");

document.getElementById("btn-start")!.onclick = () => send({ type: "gm.play.start" });
document.getElementById("btn-stop")!.onclick = () => send({ type: "gm.play.stop" });
document.getElementById("btn-pause")!.onclick = () => send({ type: "gm.play.pause" });
document.getElementById("btn-resume")!.onclick = () => send({ type: "gm.play.resume" });

document.getElementById("btn-apply-template")!.onclick = () => editor.applyTemplate();
btnApplyMaze.onclick = () => applySharedTemplate("Sent apply_template…");

btnMazeGenerate.onclick = () => {
  const width = Math.max(2, Math.min(80, Number(mazeGenW.value) || 8));
  const height = Math.max(2, Math.min(80, Number(mazeGenH.value) || 8));
  const seedRaw = mazeGenSeed.value.trim();
  const payload: Record<string, unknown> = {
    type: "gm.design.generate_maze",
    width,
    height,
    algorithm: mazeGenAlgo.value || "recursive_backtracker",
  };
  if (seedRaw !== "") payload.seed = Number(seedRaw);
  send(payload);
  mazeStatus.textContent = "Sent generate_maze…";
  designStatus.textContent = "Sent generate_maze…";
};

window.addEventListener("resize", () => {
  mazeEditor.refresh();
  mazeHomeEditor.refresh();
});

applyModeVisibility();
setView("home");

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function escapeAttr(s: string): string {
  return escapeHtml(s).replace(/'/g, "&#39;");
}

