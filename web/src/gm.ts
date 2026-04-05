import {
  MonsterTypeEditor,
  gmViewToWorkingTemplate,
  validateWorkingTemplate,
  type GmViewMsg,
  type WorkingTemplate,
} from "./gm_monster_editor";
import { MazeCanvasEditor } from "./gm_maze_canvas";

const SESSION = "default";
const WS_URL = `ws://${window.location.hostname}:8000/ws/${SESSION}`;

type GmViewId = "home" | "maze" | "monsters";

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
const mazeEditable = document.getElementById("maze-editable")!;
const monstersEditable = document.getElementById("monsters-editable")!;
const mazeCanvasEl = document.getElementById("maze-canvas") as HTMLCanvasElement;
const btnApplyMaze = document.getElementById("btn-apply-maze") as HTMLButtonElement;
const btnMazeGenerate = document.getElementById("btn-maze-generate") as HTMLButtonElement;
const mazeGenW = document.getElementById("maze-gen-w") as HTMLInputElement;
const mazeGenH = document.getElementById("maze-gen-h") as HTMLInputElement;
const mazeGenSeed = document.getElementById("maze-gen-seed") as HTMLInputElement;
const mazeGenAlgo = document.getElementById("maze-gen-algo") as HTMLSelectElement;

const navButtons = Array.from(document.querySelectorAll<HTMLButtonElement>(".gm-nav-btn"));

let sharedWorking: WorkingTemplate | null = null;

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
    if (isActive) {
      btn.setAttribute("aria-current", "page");
    } else {
      btn.removeAttribute("aria-current");
    }
  }
  if (view === "maze") {
    mazeEditor.refresh();
  }
}

function setSessionMode(mode: "design" | "play") {
  gmApp.classList.toggle("gm-app--play", mode === "play");
  const editingLocked = mode === "play";
  mazePlayNotice.hidden = !editingLocked;
  monstersPlayNotice.hidden = !editingLocked;
  mazeEditable.classList.toggle("view-body--locked", editingLocked);
  monstersEditable.classList.toggle("view-body--locked", editingLocked);
  const applyBtn = document.getElementById("btn-apply-template") as HTMLButtonElement | null;
  if (applyBtn) {
    applyBtn.disabled = editingLocked;
  }
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
    if (v === "home" || v === "maze" || v === "monsters") {
      setView(v);
    }
  });
}

const ws = new WebSocket(WS_URL);

const editor = new MonsterTypeEditor(monsterRoot, ws, (s) => {
  designStatus.textContent = s;
});

const mazeEditor = new MazeCanvasEditor(mazeCanvasEl);

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
  ws.send(JSON.stringify({ type: "gm.design.apply_template", template: w }));
  designStatus.textContent = statusOnMaze;
  mazeStatus.textContent = statusOnMaze;
}

function hydrateFromGmView(msg: GmViewMsg) {
  sharedWorking = gmViewToWorkingTemplate(msg);
  editor.setWorking(sharedWorking);
  mazeEditor.setWorking(sharedWorking);
}

ws.onopen = () => {
  ws.send(JSON.stringify({ type: "hello", role: "gm" }));
};
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data as string) as Record<string, unknown>;
  log(msg);
  if (msg.type === "state.gm_view") {
    const mode = msg.sessionMode === "play" ? "play" : "design";
    setSessionMode(mode);
    hydrateFromGmView(msg as unknown as GmViewMsg);
  }
  if (msg.type === "error") {
    const m = String((msg as { message?: string }).message ?? "error");
    designStatus.textContent = m;
    mazeStatus.textContent = m;
  }
};
ws.onerror = () => console.error("WS error");

document.getElementById("btn-start")!.onclick = () => {
  ws.send(JSON.stringify({ type: "gm.play.start" }));
};
document.getElementById("btn-stop")!.onclick = () => {
  ws.send(JSON.stringify({ type: "gm.play.stop" }));
};
document.getElementById("btn-pause")!.onclick = () => {
  ws.send(JSON.stringify({ type: "gm.play.pause" }));
};
document.getElementById("btn-resume")!.onclick = () => {
  ws.send(JSON.stringify({ type: "gm.play.resume" }));
};

document.getElementById("btn-apply-template")!.onclick = () => {
  editor.applyTemplate();
};

btnApplyMaze.onclick = () => {
  applySharedTemplate("Sent apply_template…");
};

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
  if (seedRaw !== "") {
    payload.seed = Number(seedRaw);
  }
  ws.send(JSON.stringify(payload));
  mazeStatus.textContent = "Sent generate_maze…";
  designStatus.textContent = "Sent generate_maze…";
};

window.addEventListener("resize", () => {
  mazeEditor.refresh();
});

setView("home");
