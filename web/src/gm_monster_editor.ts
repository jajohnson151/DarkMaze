/** Working template for gm.design.apply_template (snake_case keys). */

import type { MonsterMirrorPayload } from "./player_view_render";

export type MonsterTypeSpec = {
  phrases: string[];
  maze_proficiency: number;
  sound_homing: number;
};

export type MonsterInstance = {
  id: string;
  type: string;
  cell: [number, number];
  facing: string;
  perception_bonus: number;
  stealth_bonus: number;
  goal_mode?: string;
  goal_target?: [number, number] | null;
};

export type WorkingTemplate = {
  version: number;
  width: number;
  height: number;
  player_spawn: [number, number];
  player_facing: string;
  exit: [number, number];
  grid: unknown[][];
  monster_types: Record<string, MonsterTypeSpec>;
  monsters: MonsterInstance[];
  surface_types?: Record<string, { noisiness?: number }>;
  edge_pois?: Array<{ x: number; y: number; dir: string; poi_type: string; note?: string }>;
};

export type GmViewMsg = {
  sessionMode?: string;
  width: number;
  height: number;
  grid: unknown[][];
  monsterTypes?: Record<string, { phrases?: string[]; maze_proficiency?: number; sound_homing?: number }>;
  player: { x: number; y: number; facing: string };
  monsters: Array<{
    id: string;
    x: number;
    y: number;
    facing: string;
    monsterTypeId?: string | null;
    goalMode?: string;
    goalTarget?: [number, number] | null;
  }>;
  exitCell: [number, number] | number[];
  monsterMirrors?: MonsterMirrorPayload[];
  designTemplate?: Partial<WorkingTemplate> & Record<string, unknown>;
};

function deepClone<T>(x: T): T {
  return JSON.parse(JSON.stringify(x)) as T;
}

export function gmViewToWorkingTemplate(msg: GmViewMsg): WorkingTemplate {
  const dt = msg.designTemplate;
  if (dt && typeof dt === "object") {
    const fromDesign = dt as WorkingTemplate;
    if (Array.isArray(fromDesign.grid)) {
      return deepClone({
        version: Number(fromDesign.version ?? 1),
        width: Number(fromDesign.width ?? msg.width),
        height: Number(fromDesign.height ?? msg.height),
        player_spawn: (fromDesign.player_spawn ?? [msg.player.x, msg.player.y]) as [number, number],
        player_facing: String(fromDesign.player_facing ?? msg.player.facing),
        exit: (fromDesign.exit ?? [Number(msg.exitCell[0]), Number(msg.exitCell[1])]) as [number, number],
        grid: fromDesign.grid,
        monster_types: (fromDesign.monster_types ?? {}) as Record<string, MonsterTypeSpec>,
        monsters: (fromDesign.monsters ?? []) as MonsterInstance[],
        surface_types: fromDesign.surface_types,
        edge_pois: fromDesign.edge_pois,
      });
    }
  }
  const mtRaw = msg.monsterTypes ?? {};
  const monster_types: Record<string, MonsterTypeSpec> = {};
  for (const [tid, spec] of Object.entries(mtRaw)) {
    monster_types[tid] = {
      phrases: Array.isArray(spec.phrases) && spec.phrases.length ? [...spec.phrases] : ["rustle"],
      maze_proficiency: typeof spec.maze_proficiency === "number" ? spec.maze_proficiency : 0.5,
      sound_homing: typeof spec.sound_homing === "number" ? spec.sound_homing : 0.5,
    };
  }
  const monsters: MonsterInstance[] = (msg.monsters ?? []).map((m) => ({
    id: m.id,
    type: m.monsterTypeId ?? "",
    cell: [m.x, m.y] as [number, number],
    facing: m.facing,
    perception_bonus: 0,
    stealth_bonus: 0,
    goal_mode: m.goalMode ?? "catch_player",
    goal_target: m.goalTarget ?? null,
  }));
  return {
    version: 1,
    width: msg.width,
    height: msg.height,
    player_spawn: [msg.player.x, msg.player.y],
    player_facing: msg.player.facing,
    exit: [Number(msg.exitCell[0]), Number(msg.exitCell[1])],
    grid: deepClone(msg.grid),
    monster_types,
    monsters,
  };
}

const ID_RE = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

/** Returns an error message if the template cannot be applied, else null. */
export function validateWorkingTemplate(w: WorkingTemplate): string | null {
  for (const m of w.monsters) {
    if (m.type && !w.monster_types[m.type]) {
      return `Monster "${m.id}" references unknown type "${m.type}"`;
    }
  }
  return null;
}

export class MonsterTypeEditor {
  private working: WorkingTemplate | null = null;
  private root: HTMLElement;
  private ws: WebSocket;
  private onStatus: (s: string) => void;

  constructor(root: HTMLElement, ws: WebSocket, onStatus: (s: string) => void) {
    this.root = root;
    this.ws = ws;
    this.onStatus = onStatus;
  }

  /** Use the same object reference as the maze editor so edits stay in sync. */
  setWorking(w: WorkingTemplate | null): void {
    this.working = w;
    this.render();
  }

  private render(): void {
    const w = this.working;
    if (!w) {
      this.root.innerHTML = "<p>No template loaded.</p>";
      return;
    }
    const types = Object.entries(w.monster_types);
    const usedBy = (tid: string) => w.monsters.filter((m) => m.type === tid).map((m) => m.id);

    const rows = types
      .map(
        ([tid, spec]) => `
      <div class="mt-row" data-type-id="${escapeAttr(tid)}">
        <div class="mt-row-head">
          <strong>${escapeHtml(tid)}</strong>
          <button type="button" class="btn-del-type" data-id="${escapeAttr(tid)}"
            ${usedBy(tid).length ? "disabled title=\"Remove or reassign monsters first\"" : ""}>Delete</button>
        </div>
        <label>Phrases (one per line)<textarea class="mt-phrases" data-id="${escapeAttr(tid)}" rows="3">${escapeHtml(
          spec.phrases.join("\n"),
        )}</textarea></label>
        <label>maze_proficiency (0–1) <input type="number" class="mt-mp" data-id="${escapeAttr(tid)}" step="0.05" min="0" max="1" value="${spec.maze_proficiency}" /></label>
        <label>sound_homing (0–1) <input type="number" class="mt-sh" data-id="${escapeAttr(tid)}" step="0.05" min="0" max="1" value="${spec.sound_homing}" /></label>
      </div>`,
      )
      .join("");

    this.root.innerHTML = `
      <div class="mt-add">
        <input type="text" id="mt-new-id" placeholder="new_type_id" />
        <button type="button" id="mt-btn-add">Add type</button>
      </div>
      <div class="mt-list">${rows || "<p>No types yet.</p>"}</div>
    `;

    this.root.querySelector("#mt-btn-add")?.addEventListener("click", () => this.addType());
    for (const btn of Array.from(this.root.querySelectorAll(".btn-del-type"))) {
      btn.addEventListener("click", (ev: Event) => {
        const id = (ev.target as HTMLElement).dataset.id;
        if (id) this.deleteType(id);
      });
    }
    for (const el of Array.from(this.root.querySelectorAll(".mt-phrases, .mt-mp, .mt-sh"))) {
      el.addEventListener("change", () => this.collectFromForm());
    }
  }

  /** Merge open inputs into `working` before apply from another view (e.g. maze editor). */
  flushFromDom(): void {
    this.collectFromForm();
  }

  private collectFromForm(): void {
    const w = this.working;
    if (!w) return;
    for (const row of Array.from(this.root.querySelectorAll(".mt-row"))) {
      const tid = row.getAttribute("data-type-id");
      if (!tid || !w.monster_types[tid]) continue;
      const ta = row.querySelector("textarea.mt-phrases") as HTMLTextAreaElement | null;
      const mp = row.querySelector("input.mt-mp") as HTMLInputElement | null;
      const sh = row.querySelector("input.mt-sh") as HTMLInputElement | null;
      if (ta) {
        const lines = ta.value.split("\n").map((s: string) => s.trim()).filter(Boolean);
        w.monster_types[tid].phrases = lines.length ? lines : ["rustle"];
      }
      if (mp) w.monster_types[tid].maze_proficiency = clamp01(Number(mp.value));
      if (sh) w.monster_types[tid].sound_homing = clamp01(Number(sh.value));
    }
  }

  addType(): void {
    const input = this.root.querySelector<HTMLInputElement>("#mt-new-id");
    const id = input?.value.trim() ?? "";
    if (!ID_RE.test(id)) {
      this.onStatus("Type id must match [a-zA-Z_][a-zA-Z0-9_]*");
      return;
    }
    const w = this.working;
    if (!w) return;
    if (w.monster_types[id]) {
      this.onStatus("Type id already exists");
      return;
    }
    w.monster_types[id] = { phrases: ["rustle"], maze_proficiency: 0.5, sound_homing: 0.5 };
    if (input) input.value = "";
    this.onStatus("");
    this.render();
  }

  deleteType(id: string): void {
    const w = this.working;
    if (!w) return;
    if (w.monsters.some((m) => m.type === id)) {
      this.onStatus(`Monsters still use type "${id}"`);
      return;
    }
    delete w.monster_types[id];
    this.onStatus("");
    this.render();
  }

  applyTemplate(): void {
    this.collectFromForm();
    const w = this.working;
    if (!w) {
      this.onStatus("No template");
      return;
    }
    const err = validateWorkingTemplate(w);
    if (err) {
      this.onStatus(err);
      return;
    }
    this.ws.send(JSON.stringify({ type: "gm.design.apply_template", template: w }));
    this.onStatus("Sent apply_template…");
  }
}

function clamp01(n: number): number {
  if (Number.isNaN(n)) return 0.5;
  return Math.min(1, Math.max(0, n));
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(s: string): string {
  return escapeHtml(s).replace(/'/g, "&#39;");
}
