import type { WorkingTemplate } from "./gm_monster_editor";

type WallDir = "n" | "e" | "s" | "w";
export type MazeEditMode = "walls" | "spawn" | "exit" | "surface" | "room_poi" | "edge_poi" | "monster";

function wallGet(c: Record<string, unknown>, k: string): boolean {
  const v = c[k];
  return v === true || v === 1;
}

function wallSet(c: Record<string, unknown>, k: string, on: boolean): void {
  c[k] = on ? 1 : 0;
}

/** Toggle wall on shared edge; keeps adjacent cell consistent. */
export function toggleWallAt(w: WorkingTemplate, x: number, y: number, dir: WallDir): void {
  const W = w.width;
  const H = w.height;
  const g = w.grid as Record<string, unknown>[][];
  if (x < 0 || y < 0 || x >= W || y >= H) return;
  const c = g[y][x] as Record<string, unknown>;
  if (dir === "n") {
    const next = !wallGet(c, "n");
    wallSet(c, "n", next);
    if (y > 0) wallSet(g[y - 1][x] as Record<string, unknown>, "s", next);
  } else if (dir === "s") {
    const next = !wallGet(c, "s");
    wallSet(c, "s", next);
    if (y + 1 < H) wallSet(g[y + 1][x] as Record<string, unknown>, "n", next);
  } else if (dir === "e") {
    const next = !wallGet(c, "e");
    wallSet(c, "e", next);
    if (x + 1 < W) wallSet(g[y][x + 1] as Record<string, unknown>, "w", next);
  } else {
    const next = !wallGet(c, "w");
    wallSet(c, "w", next);
    if (x > 0) wallSet(g[y][x - 1] as Record<string, unknown>, "e", next);
  }
}

function setWallAt(w: WorkingTemplate, x: number, y: number, dir: WallDir, on: boolean): void {
  const W = w.width;
  const H = w.height;
  const g = w.grid as Record<string, unknown>[][];
  if (x < 0 || y < 0 || x >= W || y >= H) return;
  const c = g[y][x] as Record<string, unknown>;
  if (dir === "n") {
    wallSet(c, "n", on);
    if (y > 0) wallSet(g[y - 1][x] as Record<string, unknown>, "s", on);
  } else if (dir === "s") {
    wallSet(c, "s", on);
    if (y + 1 < H) wallSet(g[y + 1][x] as Record<string, unknown>, "n", on);
  } else if (dir === "e") {
    wallSet(c, "e", on);
    if (x + 1 < W) wallSet(g[y][x + 1] as Record<string, unknown>, "w", on);
  } else {
    wallSet(c, "w", on);
    if (x > 0) wallSet(g[y][x - 1] as Record<string, unknown>, "e", on);
  }
}

const EDGE_PX = 8;

type EdgePick = { cellX: number; cellY: number; dir: WallDir; dist: number };

function nearestEdge(
  offsetX: number,
  offsetY: number,
  pad: number,
  cellSize: number,
  width: number,
  height: number,
): EdgePick | null {
  const fx = (offsetX - pad) / cellSize;
  const fy = (offsetY - pad) / cellSize;
  if (fx < 0 || fy < 0 || fx >= width || fy >= height) return null;
  const cellX = Math.floor(fx);
  const cellY = Math.floor(fy);
  const fracX = fx - cellX;
  const fracY = fy - cellY;
  const dN = fracY * cellSize;
  const dS = (1 - fracY) * cellSize;
  const dW = fracX * cellSize;
  const dE = (1 - fracX) * cellSize;
  const cands: Array<{ dir: WallDir; d: number }> = [
    { dir: "n", d: dN },
    { dir: "s", d: dS },
    { dir: "w", d: dW },
    { dir: "e", d: dE },
  ];
  cands.sort((a, b) => a.d - b.d);
  const best = cands[0];
  if (!best) return null;
  return { cellX, cellY, dir: best.dir, dist: best.d };
}

export type MazeCanvasEditorOptions = {
  /** When true, no click toggling and no movement trail accumulation. */
  readOnly?: boolean;
  onWallSet?: (x: number, y: number, dir: WallDir, on: boolean) => void;
  onSpawnSet?: (x: number, y: number) => void;
  onExitSet?: (x: number, y: number) => void;
  onSurfaceSet?: (x: number, y: number, surfaceType: string | null) => void;
  onRoomPoiAdd?: (x: number, y: number, poiType: string, note: string) => void;
  onEdgePoiAdd?: (x: number, y: number, dir: WallDir, poiType: string, note: string) => void;
  onMonsterPlace?: (x: number, y: number) => void;
};

export class MazeCanvasEditor {
  private working: WorkingTemplate | null = null;
  private canvas: HTMLCanvasElement;
  private cellSize = 28;
  private pad = 20;
  private ctx: CanvasRenderingContext2D;
  private trails: Record<string, Array<[number, number]>> = {};
  private readOnly: boolean;
  private mode: MazeEditMode = "walls";
  private currentSurfaceType: string | null = null;
  private currentPoiType = "";
  private currentPoiNote = "";
  private opts: MazeCanvasEditorOptions;
  private draggingWall: boolean | null = null;
  private seenWallEdges = new Set<string>();

  constructor(canvas: HTMLCanvasElement, options?: MazeCanvasEditorOptions) {
    this.canvas = canvas;
    this.opts = options ?? {};
    this.readOnly = this.opts.readOnly ?? false;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2d context");
    this.ctx = ctx;
    if (!this.readOnly) {
      canvas.addEventListener("pointerdown", (ev) => this.onPointerDown(ev));
      canvas.addEventListener("pointermove", (ev) => this.onPointerMove(ev));
      canvas.addEventListener("pointerup", () => this.endDrag());
      canvas.addEventListener("pointerleave", () => this.endDrag());
      canvas.addEventListener("click", (ev) => this.onClick(ev.offsetX, ev.offsetY));
      canvas.addEventListener("contextmenu", (ev) => ev.preventDefault());
    }
  }

  setMode(mode: MazeEditMode): void {
    this.mode = mode;
  }

  setSurfaceType(surfaceType: string | null): void {
    this.currentSurfaceType = surfaceType && surfaceType.trim() ? surfaceType.trim() : null;
  }

  setPoiType(poiType: string): void {
    this.currentPoiType = poiType.trim();
  }

  setPoiNote(note: string): void {
    this.currentPoiNote = note;
  }

  setWorking(w: WorkingTemplate | null): void {
    this.updateTrails(w);
    this.working = w;
    this.resize();
    this.draw();
  }

  refresh(): void {
    this.resize();
    this.draw();
  }

  private logicalSize(): { lw: number; lh: number } {
    const w = this.working;
    if (!w) return { lw: 320, lh: 240 };
    const cs = this.cellSize;
    const p = this.pad;
    return { lw: p * 2 + w.width * cs, lh: p * 2 + w.height * cs };
  }

  private resize(): void {
    const { lw, lh } = this.logicalSize();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.max(1, Math.floor(lw * dpr));
    this.canvas.height = Math.max(1, Math.floor(lh * dpr));
    this.canvas.style.width = `${lw}px`;
    this.canvas.style.height = `${lh}px`;
  }

  private cellOrigin(x: number, y: number): { ox: number; oy: number } {
    return { ox: this.pad + x * this.cellSize, oy: this.pad + y * this.cellSize };
  }

  draw(): void {
    const w = this.working;
    const ctx = this.ctx;
    const dpr = window.devicePixelRatio || 1;
    const { lw, lh } = this.logicalSize();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#0d0d12";
    ctx.fillRect(0, 0, lw, lh);
    if (!w || !w.grid?.length) {
      ctx.fillStyle = "#888";
      ctx.font = "14px system-ui";
      ctx.fillText("No maze loaded.", this.pad, this.pad + 20);
      return;
    }
    const g = w.grid as Record<string, unknown>[][];
    const cs = this.cellSize;
    const wallColor = "#c8c8e8";
    const floorColor = "#1e1e2e";

    for (let y = 0; y < w.height; y++) {
      for (let x = 0; x < w.width; x++) {
        const { ox, oy } = this.cellOrigin(x, y);
        const cell = g[y]?.[x];
        let fill = floorColor;
        if (cell && typeof cell === "object") {
          const st = String((cell as Record<string, unknown>).surface_type ?? "");
          if (st === "standing water") fill = "#1b2b46";
          else if (st === "crunchy gravel") fill = "#3d3a2d";
          else if (st === "dirt") fill = "#3a2b1f";
        }
        ctx.fillStyle = fill;
        ctx.fillRect(ox + 1, oy + 1, cs - 2, cs - 2);
      }
    }

    ctx.strokeStyle = wallColor;
    ctx.lineWidth = 3;
    ctx.lineCap = "square";
    for (let y = 0; y < w.height; y++) {
      for (let x = 0; x < w.width; x++) {
        const row = g[y];
        const cell = (row && row[x]) as Record<string, unknown> | undefined;
        if (!cell || typeof cell !== "object") continue;
        const { ox, oy } = this.cellOrigin(x, y);
        if (wallGet(cell, "n")) {
          ctx.beginPath();
          ctx.moveTo(ox, oy);
          ctx.lineTo(ox + cs, oy);
          ctx.stroke();
        }
        if (wallGet(cell, "w")) {
          ctx.beginPath();
          ctx.moveTo(ox, oy);
          ctx.lineTo(ox, oy + cs);
          ctx.stroke();
        }
        if (y === w.height - 1 && wallGet(cell, "s")) {
          ctx.beginPath();
          ctx.moveTo(ox, oy + cs);
          ctx.lineTo(ox + cs, oy + cs);
          ctx.stroke();
        }
        if (x === w.width - 1 && wallGet(cell, "e")) {
          ctx.beginPath();
          ctx.moveTo(ox + cs, oy);
          ctx.lineTo(ox + cs, oy + cs);
          ctx.stroke();
        }
      }
    }

    const [px, py] = w.player_spawn;
    const [ex, ey] = w.exit;
    this.drawMarker(ex, ey, "E", "#fc6", "#420");
    for (const m of w.monsters) {
      const [mx, my] = m.cell;
      this.drawFacingMarker(mx, my, m.facing, "#c6f", "#204", "M");
      this.drawTrail(m.id, "#7f66aa");
    }
    this.drawFacingMarker(px, py, w.player_facing, "#6cf", "#024", "P");
  }

  private drawMarker(cx: number, cy: number, label: string, fill: string, stroke: string): void {
    const w = this.working;
    if (!w || cx < 0 || cy < 0 || cx >= w.width || cy >= w.height) return;
    const { ox, oy } = this.cellOrigin(cx, cy);
    const cs = this.cellSize;
    const ctx = this.ctx;
    const r = Math.min(cs, 18) / 2 - 2;
    const cxp = ox + cs / 2;
    const cyp = oy + cs / 2;
    ctx.beginPath();
    ctx.arc(cxp, cyp, r, 0, Math.PI * 2);
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.fillStyle = stroke;
    ctx.font = `bold ${Math.floor(r * 1.1)}px system-ui`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, cxp, cyp);
  }

  private drawFacingMarker(
    cx: number,
    cy: number,
    facing: string,
    fill: string,
    stroke: string,
    label: string,
  ): void {
    this.drawMarker(cx, cy, label, fill, stroke);
    const { ox, oy } = this.cellOrigin(cx, cy);
    const cs = this.cellSize;
    const ctx = this.ctx;
    const centerX = ox + cs / 2;
    const centerY = oy + cs / 2;
    const len = Math.max(6, cs * 0.28);
    let dx = 0;
    let dy = 0;
    if (facing === "north") dy = -len;
    else if (facing === "south") dy = len;
    else if (facing === "east") dx = len;
    else if (facing === "west") dx = -len;
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(centerX + dx, centerY + dy);
    ctx.stroke();
  }

  private updateTrails(w: WorkingTemplate | null): void {
    if (this.readOnly || !w) return;
    const playerTrail = this.trails["player"] || [];
    playerTrail.push([w.player_spawn[0], w.player_spawn[1]]);
    this.trails["player"] = playerTrail.slice(-12);
    for (const m of w.monsters) {
      const t = this.trails[m.id] || [];
      t.push([m.cell[0], m.cell[1]]);
      this.trails[m.id] = t.slice(-12);
    }
  }

  private drawTrail(id: string, color: string): void {
    const points = this.trails[id];
    if (!points || points.length < 2) return;
    const ctx = this.ctx;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < points.length; i++) {
      const [x, y] = points[i];
      const { ox, oy } = this.cellOrigin(x, y);
      const px = ox + this.cellSize / 2;
      const py = oy + this.cellSize / 2;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.stroke();
  }

  private onPointerDown(ev: PointerEvent): void {
    if (this.readOnly || this.mode !== "walls" || !this.working) return;
    const edge = nearestEdge(
      ev.offsetX,
      ev.offsetY,
      this.pad,
      this.cellSize,
      this.working.width,
      this.working.height,
    );
    if (!edge || edge.dist > EDGE_PX) return;
    this.draggingWall = ev.button === 2 ? true : ev.ctrlKey ? true : false;
    this.seenWallEdges.clear();
    this.applyWallDrag(edge);
  }

  private onPointerMove(ev: PointerEvent): void {
    if (this.readOnly || this.mode !== "walls" || this.draggingWall === null || !this.working) return;
    const edge = nearestEdge(
      ev.offsetX,
      ev.offsetY,
      this.pad,
      this.cellSize,
      this.working.width,
      this.working.height,
    );
    if (!edge || edge.dist > EDGE_PX) return;
    this.applyWallDrag(edge);
  }

  private endDrag(): void {
    this.draggingWall = null;
    this.seenWallEdges.clear();
  }

  private applyWallDrag(edge: EdgePick): void {
    if (!this.working || this.draggingWall === null) return;
    const key = `${edge.cellX}:${edge.cellY}:${edge.dir}`;
    if (this.seenWallEdges.has(key)) return;
    this.seenWallEdges.add(key);
    setWallAt(this.working, edge.cellX, edge.cellY, edge.dir, this.draggingWall);
    this.opts.onWallSet?.(edge.cellX, edge.cellY, edge.dir, this.draggingWall);
    this.draw();
  }

  private onClick(offsetX: number, offsetY: number): void {
    if (this.readOnly) return;
    const w = this.working;
    if (!w) return;
    if (this.mode === "walls") return;

    const fx = (offsetX - this.pad) / this.cellSize;
    const fy = (offsetY - this.pad) / this.cellSize;
    if (fx < 0 || fy < 0 || fx >= w.width || fy >= w.height) return;
    const cellX = Math.floor(fx);
    const cellY = Math.floor(fy);
    if (this.mode === "spawn") {
      w.player_spawn = [cellX, cellY];
      this.opts.onSpawnSet?.(cellX, cellY);
      this.draw();
      return;
    }
    if (this.mode === "exit") {
      w.exit = [cellX, cellY];
      this.opts.onExitSet?.(cellX, cellY);
      this.draw();
      return;
    }
    if (this.mode === "surface") {
      const g = w.grid as Record<string, unknown>[][];
      const c = g[cellY]?.[cellX];
      if (c && typeof c === "object") {
        if (this.currentSurfaceType) (c as Record<string, unknown>).surface_type = this.currentSurfaceType;
        else delete (c as Record<string, unknown>).surface_type;
      }
      this.opts.onSurfaceSet?.(cellX, cellY, this.currentSurfaceType);
      this.draw();
      return;
    }
    if (this.mode === "room_poi") {
      if (!this.currentPoiType) return;
      this.opts.onRoomPoiAdd?.(cellX, cellY, this.currentPoiType, this.currentPoiNote);
      return;
    }
    if (this.mode === "edge_poi") {
      if (!this.currentPoiType) return;
      const edge = nearestEdge(offsetX, offsetY, this.pad, this.cellSize, w.width, w.height);
      if (!edge || edge.dist > EDGE_PX) return;
      this.opts.onEdgePoiAdd?.(edge.cellX, edge.cellY, edge.dir, this.currentPoiType, this.currentPoiNote);
      return;
    }
    if (this.mode === "monster") {
      this.opts.onMonsterPlace?.(cellX, cellY);
    }
  }
}
