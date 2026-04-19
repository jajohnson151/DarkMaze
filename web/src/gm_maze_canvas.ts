import type { WorkingTemplate } from "./gm_monster_editor";

type WallDir = "n" | "e" | "s" | "w";

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

const EDGE_PX = 8;

export class MazeCanvasEditor {
  private working: WorkingTemplate | null = null;
  private canvas: HTMLCanvasElement;
  private cellSize = 28;
  private pad = 20;
  private ctx: CanvasRenderingContext2D;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2d context");
    this.ctx = ctx;
    canvas.addEventListener("click", (ev) => this.onPointer(ev.offsetX, ev.offsetY));
  }

  setWorking(w: WorkingTemplate | null): void {
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
        ctx.fillStyle = floorColor;
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
    this.drawMarker(px, py, "P", "#6cf", "#024");
    const [ex, ey] = w.exit;
    this.drawMarker(ex, ey, "E", "#fc6", "#420");
    for (const m of w.monsters) {
      const [mx, my] = m.cell;
      this.drawMarker(mx, my, "M", "#c6f", "#204");
    }
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

  private onPointer(offsetX: number, offsetY: number): void {
    const w = this.working;
    if (!w) return;
    const cs = this.cellSize;
    const p = this.pad;
    const fx = (offsetX - p) / cs;
    const fy = (offsetY - p) / cs;
    if (fx < 0 || fy < 0 || fx >= w.width || fy >= w.height) return;
    const cellX = Math.floor(fx);
    const cellY = Math.floor(fy);
    const fracX = fx - cellX;
    const fracY = fy - cellY;
    const dN = fracY * cs;
    const dS = (1 - fracY) * cs;
    const dW = fracX * cs;
    const dE = (1 - fracX) * cs;
    type Cand = { dir: WallDir; d: number };
    const cands: Cand[] = [
      { dir: "n", d: dN },
      { dir: "s", d: dS },
      { dir: "w", d: dW },
      { dir: "e", d: dE },
    ];
    cands.sort((a, b) => a.d - b.d);
    const best = cands[0];
    if (!best || best.d > EDGE_PX) return;
    toggleWallAt(w, cellX, cellY, best.dir);
    this.draw();
  }
}
