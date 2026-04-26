"""Tkinter offline maze template editor."""

from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

import yaml

from game.maze_gen import ALGORITHMS
from game.template_edit import (
    add_edge_poi,
    add_room_poi_at,
    apply_generated_maze,
    get_wall_at,
    normalize_template_grid_for_edit,
    pick_wall_toggle_cell_dir,
    set_surface_type_at,
    set_surface_noisiness,
    set_wall_at,
)
from game.template_io import load_template, minimal_template_dict, validate_template_data

FACINGS = ("north", "east", "south", "west")
DEFAULT_SURFACE_TYPES = ("smooth stone", "dirt", "crunchy gravel", "standing water")
POI_CATALOG_PATH = Path(".darkmaze_designer_poi.yaml")
DEFAULT_POI_TYPES = [
    {"id": "dip_floor", "label": "Dip in floor", "applies_to": "room"},
    {"id": "engraving_wall", "label": "Engravings on wall", "applies_to": "edge"},
    {"id": "cobweb_opening", "label": "Cobweb at opening", "applies_to": "edge"},
]


def _blank_template(width: int, height: int) -> dict[str, Any]:
    data = minimal_template_dict(width, height)
    normalize_template_grid_for_edit(data)
    return data


class DesignerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._path: Path | None = None
        self._data: dict[str, Any] = _blank_template(5, 5)
        self._dirty = False

        self._cell_size = 28
        self._pad = 20
        self._last_generate_params: dict[str, Any] = {
            "width": int(self._data["width"]),
            "height": int(self._data["height"]),
            "algorithm": "recursive_backtracker",
            "seed": "",
            "params": {},
        }
        self._drag_mode_on: bool | None = None
        self._drag_seen_edges: set[tuple[int, int, str]] = set()
        self._left_drag_prev_cell: tuple[int, int] | None = None
        self._left_drag_close: bool = False
        self._left_drag_seen_segments: set[tuple[int, int, str]] = set()
        self._poi_catalog: dict[str, Any] = self._load_poi_catalog()

        root.title("Dark Maze — template designer")
        root.minsize(520, 480)

        menubar = tk.Menu(root)
        root.config(menu=menubar)
        fm = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=fm)
        fm.add_command(label="New…", command=self._menu_new)
        fm.add_command(label="Open…", command=self._menu_open)
        fm.add_command(label="Save", command=self._menu_save)
        fm.add_command(label="Save as…", command=self._menu_save_as)
        fm.add_separator()
        fm.add_command(label="Quit", command=self._quit)

        top = ttk.Frame(root, padding=6)
        top.pack(fill=tk.X)

        self._mode_var = tk.StringVar(value="walls")
        ttk.Label(top, text="Click mode:").pack(side=tk.LEFT, padx=(0, 4))
        for val, lab in (
            ("walls", "Walls"),
            ("spawn", "Player spawn"),
            ("exit", "Exit"),
            ("surface", "Surface"),
            ("room_poi", "Room POI"),
            ("edge_poi", "Edge POI"),
        ):
            ttk.Radiobutton(top, text=lab, value=val, variable=self._mode_var).pack(side=tk.LEFT, padx=2)

        ttk.Label(top, text="Facing").pack(side=tk.LEFT, padx=(16, 4))
        self._facing_var = tk.StringVar(value="east")
        self._facing_cb = ttk.Combobox(top, textvariable=self._facing_var, values=FACINGS, width=8, state="readonly")
        self._facing_cb.pack(side=tk.LEFT)
        self._facing_cb.bind("<<ComboboxSelected>>", lambda _e: self._set_facing_from_ui())

        ttk.Button(top, text="Validate", command=self._validate).pack(side=tk.LEFT, padx=(16, 0))

        self._status = tk.StringVar(value="Ready")
        st = ttk.Label(root, textvariable=self._status, anchor=tk.W, padding=(8, 2))
        st.pack(fill=tk.X)

        gen = ttk.LabelFrame(root, text="Maze generation", padding=8)
        gen.pack(fill=tk.X, padx=6, pady=(2, 4))
        self._gen_width_var = tk.StringVar(value=str(int(self._data["width"])))
        self._gen_height_var = tk.StringVar(value=str(int(self._data["height"])))
        self._gen_algorithm_var = tk.StringVar(value="recursive_backtracker")
        self._gen_seed_var = tk.StringVar(value="")
        self._gen_error_var = tk.StringVar(value="")
        self._algo_param_vars: dict[str, tk.StringVar] = {}
        self._algo_param_widgets: list[ttk.Widget] = []

        ttk.Label(gen, text="Width").grid(row=0, column=0, sticky=tk.W, padx=(0, 4))
        ttk.Entry(gen, textvariable=self._gen_width_var, width=6).grid(row=0, column=1, sticky=tk.W, padx=(0, 8))
        ttk.Label(gen, text="Height").grid(row=0, column=2, sticky=tk.W, padx=(0, 4))
        ttk.Entry(gen, textvariable=self._gen_height_var, width=6).grid(row=0, column=3, sticky=tk.W, padx=(0, 8))
        ttk.Label(gen, text="Algorithm").grid(row=0, column=4, sticky=tk.W, padx=(0, 4))
        algo_values = [k for k in ALGORITHMS]
        self._algo_cb = ttk.Combobox(
            gen,
            textvariable=self._gen_algorithm_var,
            values=algo_values,
            width=24,
            state="readonly",
        )
        self._algo_cb.grid(row=0, column=5, sticky=tk.W, padx=(0, 8))
        self._algo_cb.bind("<<ComboboxSelected>>", lambda _e: self._render_algorithm_param_fields())
        ttk.Label(gen, text="Seed").grid(row=0, column=6, sticky=tk.W, padx=(0, 4))
        ttk.Entry(gen, textvariable=self._gen_seed_var, width=12).grid(row=0, column=7, sticky=tk.W, padx=(0, 8))
        ttk.Button(gen, text="Generate", command=self._generate_maze).grid(row=0, column=8, sticky=tk.W, padx=(2, 4))
        ttk.Button(gen, text="Quick generate", command=self._quick_generate_maze).grid(row=0, column=9, sticky=tk.W)
        self._gen_params_frame = ttk.Frame(gen)
        self._gen_params_frame.grid(row=1, column=0, columnspan=10, sticky=tk.W, pady=(6, 0))
        ttk.Label(gen, textvariable=self._gen_error_var, foreground="#ff6b6b").grid(
            row=2, column=0, columnspan=10, sticky=tk.W, pady=(2, 0)
        )

        meta = ttk.LabelFrame(root, text="Room and POI metadata", padding=8)
        meta.pack(fill=tk.X, padx=6, pady=(0, 4))
        self._surface_var = tk.StringVar(value=DEFAULT_SURFACE_TYPES[0])
        self._surface_noisiness_var = tk.StringVar(value="0")
        ttk.Label(meta, text="Surface").grid(row=0, column=0, sticky=tk.W, padx=(0, 4))
        self._surface_cb = ttk.Combobox(meta, textvariable=self._surface_var, values=list(DEFAULT_SURFACE_TYPES), width=24)
        self._surface_cb.grid(row=0, column=1, sticky=tk.W, padx=(0, 6))
        ttk.Button(meta, text="Add surface type", command=self._add_surface_type).grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        ttk.Label(meta, text="Noisiness").grid(row=0, column=3, sticky=tk.W, padx=(0, 4))
        ttk.Entry(meta, textvariable=self._surface_noisiness_var, width=6).grid(row=0, column=4, sticky=tk.W, padx=(0, 4))
        ttk.Button(meta, text="Set", command=self._set_selected_surface_noisiness).grid(row=0, column=5, sticky=tk.W, padx=(0, 10))
        self._surface_cb.bind("<<ComboboxSelected>>", lambda _e: self._sync_surface_noisiness_from_data())

        self._poi_type_var = tk.StringVar(value="")
        ttk.Label(meta, text="POI type").grid(row=0, column=6, sticky=tk.W, padx=(0, 4))
        self._poi_type_cb = ttk.Combobox(meta, textvariable=self._poi_type_var, values=[], width=28, state="readonly")
        self._poi_type_cb.grid(row=0, column=7, sticky=tk.W, padx=(0, 6))
        ttk.Button(meta, text="Add POI type", command=self._add_poi_type).grid(row=0, column=8, sticky=tk.W)

        hint = ttk.Label(
            root,
            text="Walls: left-drag opens passages room-to-room; Ctrl+left-drag closes passages. "
            "Right-click drag paints wall segments. Surface/Room POI: click room center. "
            "Edge POI: click near an edge. Spawn/Exit: click cell center. "
            "Monsters are shown read-only (edit YAML for details).",
            wraplength=640,
            padding=(8, 0),
        )
        hint.pack(fill=tk.X)

        self._canvas = tk.Canvas(root, background="#0d0d12", highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._canvas.bind("<ButtonPress-1>", self._on_left_press)
        self._canvas.bind("<B1-Motion>", self._on_left_motion)
        self._canvas.bind("<ButtonRelease-1>", self._on_left_release)
        self._canvas.bind("<Button-3>", self._on_right_drag_start)
        self._canvas.bind("<B3-Motion>", self._on_right_drag_motion)
        self._canvas.bind("<ButtonRelease-3>", self._on_right_drag_end)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._sync_facing_from_data()
        self._refresh_surface_values()
        self._refresh_poi_type_values()
        self._render_algorithm_param_fields()
        self._update_title()
        self.redraw()

    def _set_facing_from_ui(self) -> None:
        self._data["player_facing"] = self._facing_var.get()
        self._dirty = True
        self.redraw()

    def _sync_facing_from_data(self) -> None:
        f = str(self._data.get("player_facing", "east"))
        if f in FACINGS:
            self._facing_var.set(f)
        else:
            self._facing_var.set("east")

    def _update_title(self) -> None:
        name = self._path.name if self._path else "Untitled"
        star = " *" if self._dirty else ""
        self.root.title(f"Dark Maze — {name}{star}")

    def _logical_size(self) -> tuple[int, int]:
        w = int(self._data["width"])
        h = int(self._data["height"])
        cs, p = self._cell_size, self._pad
        return p * 2 + w * cs, p * 2 + h * cs

    def _on_canvas_configure(self, _evt: tk.Event[Any]) -> None:
        self.redraw()

    def redraw(self) -> None:
        c = self._canvas
        c.delete("all")
        lw, lh = self._logical_size()
        c.config(scrollregion=(0, 0, lw, lh))
        W = int(self._data["width"])
        H = int(self._data["height"])
        grid = self._data.get("grid")
        cs, p = self._cell_size, self._pad
        floor = "#1e1e2e"
        wall_col = "#c8c8e8"

        if not isinstance(grid, list) or not grid:
            c.create_text(p, p + 20, text="No maze loaded.", fill="#888", anchor=tk.W)
            return

        for y in range(H):
            for x in range(W):
                ox = p + x * cs
                oy = p + y * cs
                c.create_rectangle(ox + 1, oy + 1, ox + cs - 1, oy + cs - 1, outline="", fill=floor)

        for y in range(H):
            for x in range(W):
                if y >= len(grid) or x >= len(grid[y]):
                    continue
                cell = grid[y][x]
                if not isinstance(cell, dict):
                    continue
                ox = p + x * cs
                oy = p + y * cs
                n = cell.get("n") in (True, 1)
                e_ = cell.get("e") in (True, 1)
                s = cell.get("s") in (True, 1)
                wv = cell.get("w") in (True, 1)
                w3 = 3
                if n:
                    c.create_line(ox, oy, ox + cs, oy, fill=wall_col, width=w3, capstyle=tk.PROJECTING)
                if wv:
                    c.create_line(ox, oy, ox, oy + cs, fill=wall_col, width=w3, capstyle=tk.PROJECTING)
                if y == H - 1 and s:
                    c.create_line(ox, oy + cs, ox + cs, oy + cs, fill=wall_col, width=w3, capstyle=tk.PROJECTING)
                if x == W - 1 and e_:
                    c.create_line(ox + cs, oy, ox + cs, oy + cs, fill=wall_col, width=w3, capstyle=tk.PROJECTING)
                if cell.get("surface_type"):
                    c.create_text(
                        ox + cs / 2,
                        oy + cs - 6,
                        text="S",
                        fill="#9bd28f",
                        font=("Segoe UI", 8, "bold"),
                    )
                if isinstance(cell.get("room_pois"), list) and cell.get("room_pois"):
                    c.create_text(
                        ox + 6,
                        oy + 6,
                        text="P",
                        fill="#ff9ecf",
                        font=("Segoe UI", 8, "bold"),
                    )

        ps = self._data["player_spawn"]
        ex = self._data["exit"]
        self._draw_marker(int(ps[0]), int(ps[1]), "P", "#66ccff", "#002244")
        self._draw_marker(int(ex[0]), int(ex[1]), "E", "#ffcc66", "#442200")
        for m in self._data.get("monsters") or []:
            cell = m.get("cell", [0, 0])
            self._draw_marker(int(cell[0]), int(cell[1]), "M", "#cc66ff", "#220044")

    def _draw_marker(self, cx: int, cy: int, label: str, fill: str, stroke: str) -> None:
        W = int(self._data["width"])
        H = int(self._data["height"])
        if cx < 0 or cy < 0 or cx >= W or cy >= H:
            return
        cs, p = self._cell_size, self._pad
        ox = p + cx * cs
        oy = p + cy * cs
        r = min(cs, 18) / 2 - 2
        xp = ox + cs / 2
        yp = oy + cs / 2
        self._canvas.create_oval(xp - r, yp - r, xp + r, yp + r, fill=fill, outline=stroke, width=2)
        self._canvas.create_text(xp, yp, text=label, fill=stroke, font=("Segoe UI", int(r * 1.1), "bold"))

    def _cell_from_event(self, evt: tk.Event[Any]) -> tuple[int, int] | None:
        ox = self._canvas.canvasx(evt.x)
        oy = self._canvas.canvasy(evt.y)
        W = int(self._data["width"])
        H = int(self._data["height"])
        cs, p = self._cell_size, self._pad
        fx = (ox - p) / cs
        fy = (oy - p) / cs
        if fx < 0 or fy < 0 or fx >= W or fy >= H:
            return None
        return (int(fx), int(fy))

    def _on_left_press(self, evt: tk.Event[Any]) -> None:
        ox = self._canvas.canvasx(evt.x)
        oy = self._canvas.canvasy(evt.y)
        W = int(self._data["width"])
        H = int(self._data["height"])
        cs, p = self._cell_size, self._pad
        mode = self._mode_var.get()

        if mode == "walls":
            self._left_drag_prev_cell = self._cell_from_event(evt)
            self._left_drag_close = bool(evt.state & 0x0004)
            self._left_drag_seen_segments.clear()
            return

        if mode == "edge_poi":
            picked = self._edge_from_event(evt)
            poi_type = self._poi_type_var.get().strip()
            if picked and poi_type:
                cx, cy, d = picked
                add_edge_poi(self._data, cx, cy, d, poi_type)
                self._dirty = True
                self._update_title()
                self.redraw()
            return

        fx = (ox - p) / cs
        fy = (oy - p) / cs
        if fx < 0 or fy < 0 or fx >= W or fy >= H:
            return
        cell_x = int(fx)
        cell_y = int(fy)
        frac_x = fx - cell_x
        frac_y = fy - cell_y
        if not (0.2 <= frac_x <= 0.8 and 0.2 <= frac_y <= 0.8):
            return

        if mode == "spawn":
            self._data["player_spawn"] = [cell_x, cell_y]
        elif mode == "exit":
            self._data["exit"] = [cell_x, cell_y]
        elif mode == "surface":
            set_surface_type_at(self._data, cell_x, cell_y, self._surface_var.get().strip() or None)
        elif mode == "room_poi":
            poi_type = self._poi_type_var.get().strip()
            if not poi_type:
                return
            add_room_poi_at(self._data, cell_x, cell_y, poi_type)
        self._dirty = True
        self._update_title()
        self.redraw()

    def _on_left_motion(self, evt: tk.Event[Any]) -> None:
        if self._mode_var.get() != "walls":
            return
        if self._left_drag_prev_cell is None:
            self._left_drag_prev_cell = self._cell_from_event(evt)
            return
        cur = self._cell_from_event(evt)
        if cur is None:
            return
        prev = self._left_drag_prev_cell
        if cur == prev:
            return
        self._left_drag_close = bool(evt.state & 0x0004)
        self._apply_left_drag_segment(prev, cur)
        self._left_drag_prev_cell = cur

    def _on_left_release(self, _evt: tk.Event[Any]) -> None:
        self._left_drag_prev_cell = None
        self._left_drag_seen_segments.clear()

    def _apply_left_drag_segment(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        x, y = start
        tx, ty = end
        path: list[tuple[int, int]] = [(x, y)]
        while x != tx:
            x += 1 if tx > x else -1
            path.append((x, y))
        while y != ty:
            y += 1 if ty > y else -1
            path.append((x, y))

        changed = False
        for idx in range(1, len(path)):
            px, py = path[idx - 1]
            cx, cy = path[idx]
            if cx == px + 1 and cy == py:
                key = (px, py, "e")
                direction = "e"
                from_x, from_y = px, py
            elif cx == px - 1 and cy == py:
                key = (cx, cy, "e")
                direction = "e"
                from_x, from_y = cx, cy
            elif cx == px and cy == py + 1:
                key = (px, py, "s")
                direction = "s"
                from_x, from_y = px, py
            elif cx == px and cy == py - 1:
                key = (cx, cy, "s")
                direction = "s"
                from_x, from_y = cx, cy
            else:
                continue
            if key in self._left_drag_seen_segments:
                continue
            self._left_drag_seen_segments.add(key)
            set_wall_at(self._data, from_x, from_y, direction, self._left_drag_close)
            changed = True
        if changed:
            self._dirty = True
            self._update_title()
            self.redraw()

    def _edge_from_event(self, evt: tk.Event[Any]) -> tuple[int, int, str] | None:
        ox = self._canvas.canvasx(evt.x)
        oy = self._canvas.canvasy(evt.y)
        W = int(self._data["width"])
        H = int(self._data["height"])
        cs, p = self._cell_size, self._pad
        return pick_wall_toggle_cell_dir(ox, oy, p, cs, W, H, 8.0)

    def _on_right_drag_start(self, evt: tk.Event[Any]) -> None:
        if self._mode_var.get() != "walls":
            return
        picked = self._edge_from_event(evt)
        if not picked:
            return
        cx, cy, d = picked
        self._drag_mode_on = not get_wall_at(self._data, cx, cy, d)
        self._drag_seen_edges = set()
        self._apply_drag_edge(cx, cy, d)

    def _on_right_drag_motion(self, evt: tk.Event[Any]) -> None:
        if self._mode_var.get() != "walls" or self._drag_mode_on is None:
            return
        picked = self._edge_from_event(evt)
        if not picked:
            return
        cx, cy, d = picked
        self._apply_drag_edge(cx, cy, d)

    def _on_right_drag_end(self, _evt: tk.Event[Any]) -> None:
        self._drag_mode_on = None
        self._drag_seen_edges.clear()

    def _apply_drag_edge(self, cx: int, cy: int, d: str) -> None:
        key = (cx, cy, d)
        if key in self._drag_seen_edges or self._drag_mode_on is None:
            return
        self._drag_seen_edges.add(key)
        set_wall_at(self._data, cx, cy, d, self._drag_mode_on)
        self._dirty = True
        self._update_title()
        self.redraw()

    def _render_algorithm_param_fields(self) -> None:
        for w in self._algo_param_widgets:
            w.destroy()
        self._algo_param_widgets.clear()
        self._algo_param_vars.clear()
        algorithm = self._gen_algorithm_var.get().strip()
        algo = ALGORITHMS.get(algorithm)
        if not algo:
            self._gen_error_var.set(f"Unknown algorithm: {algorithm}")
            return
        self._gen_error_var.set("")
        if not algo.params:
            lbl = ttk.Label(self._gen_params_frame, text="No additional parameters")
            lbl.grid(row=0, column=0, sticky=tk.W)
            self._algo_param_widgets.append(lbl)
            return
        for idx, param in enumerate(algo.params):
            lbl = ttk.Label(self._gen_params_frame, text=param.label)
            lbl.grid(row=0, column=idx * 2, sticky=tk.W, padx=(0, 4))
            var = tk.StringVar(value="" if param.default is None else str(param.default))
            self._algo_param_vars[param.key] = var
            ent = ttk.Entry(self._gen_params_frame, textvariable=var, width=8)
            ent.grid(row=0, column=idx * 2 + 1, sticky=tk.W, padx=(0, 8))
            self._algo_param_widgets.extend([lbl, ent])

    def _load_poi_catalog(self) -> dict[str, Any]:
        if not POI_CATALOG_PATH.exists():
            data = {"poi_types": list(DEFAULT_POI_TYPES)}
            with open(POI_CATALOG_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, sort_keys=False)
            return data
        try:
            with open(POI_CATALOG_PATH, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return {"poi_types": list(DEFAULT_POI_TYPES)}
        poi_types = data.get("poi_types")
        if not isinstance(poi_types, list):
            data["poi_types"] = list(DEFAULT_POI_TYPES)
        return data

    def _save_poi_catalog(self) -> None:
        with open(POI_CATALOG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._poi_catalog, f, sort_keys=False)

    def _refresh_poi_type_values(self) -> None:
        types = self._poi_catalog.get("poi_types") or []
        labels = [str(t.get("id", "")) for t in types if isinstance(t, dict) and t.get("id")]
        self._poi_type_cb["values"] = labels
        if labels and self._poi_type_var.get() not in labels:
            self._poi_type_var.set(labels[0])

    def _refresh_surface_values(self) -> None:
        surface_types = self._data.get("surface_types")
        values: list[str] = []
        if isinstance(surface_types, dict):
            values = [str(k) for k in surface_types.keys()]
        if not values:
            values = list(DEFAULT_SURFACE_TYPES)
        self._surface_cb["values"] = values
        if self._surface_var.get() not in values:
            self._surface_var.set(values[0])
        self._sync_surface_noisiness_from_data()

    def _sync_surface_noisiness_from_data(self) -> None:
        surface_types = self._data.get("surface_types")
        if not isinstance(surface_types, dict):
            self._surface_noisiness_var.set("0")
            return
        spec = surface_types.get(self._surface_var.get())
        if isinstance(spec, dict):
            try:
                self._surface_noisiness_var.set(str(int(spec.get("noisiness", 0))))
            except Exception:
                self._surface_noisiness_var.set("0")
        else:
            self._surface_noisiness_var.set("0")

    def _set_selected_surface_noisiness(self) -> None:
        surface = self._surface_var.get().strip()
        if not surface:
            messagebox.showerror("Surface noisiness", "Choose a surface type first")
            return
        try:
            noisiness = int(self._surface_noisiness_var.get().strip())
        except ValueError:
            messagebox.showerror("Surface noisiness", "Noisiness must be an integer")
            return
        set_surface_noisiness(self._data, surface, noisiness)
        self._dirty = True
        self._update_title()
        self._status.set(f"Set noisiness for '{surface}' to {max(0, noisiness)}")

    def _add_poi_type(self) -> None:
        poi_id = simpledialog.askstring("Add POI type", "POI id (e.g. dip_floor):", initialvalue="")
        if poi_id is None:
            return
        poi_id = poi_id.strip()
        if not poi_id:
            messagebox.showerror("Add POI type", "POI id is required")
            return
        label = simpledialog.askstring("Add POI type", "Label:", initialvalue=poi_id.replace("_", " "))
        if label is None:
            return
        applies_to = simpledialog.askstring("Add POI type", "Applies to (room/edge/both):", initialvalue="room")
        if applies_to is None:
            return
        applies_to = applies_to.strip().lower()
        if applies_to not in ("room", "edge", "both"):
            messagebox.showerror("Add POI type", "Applies to must be room, edge, or both")
            return
        types = self._poi_catalog.setdefault("poi_types", [])
        if not isinstance(types, list):
            types = []
            self._poi_catalog["poi_types"] = types
        if any(isinstance(t, dict) and t.get("id") == poi_id for t in types):
            messagebox.showerror("Add POI type", "POI id already exists")
            return
        types.append({"id": poi_id, "label": label.strip() or poi_id, "applies_to": applies_to})
        self._save_poi_catalog()
        self._refresh_poi_type_values()
        self._status.set(f"Added POI type: {poi_id}")

    def _add_surface_type(self) -> None:
        value = simpledialog.askstring("Add surface type", "Surface label:", initialvalue="")
        if value is None:
            return
        value = value.strip()
        if not value:
            return
        vals = list(self._surface_cb["values"])
        if value not in vals:
            vals.append(value)
            self._surface_cb["values"] = vals
        self._surface_var.set(value)
        set_surface_noisiness(self._data, value, 0)
        self._sync_surface_noisiness_from_data()
        self._dirty = True
        self._update_title()

    def _collect_generation_inputs(self) -> tuple[int, int, str, int | None, dict[str, int]]:
        try:
            width = int(self._gen_width_var.get().strip())
            height = int(self._gen_height_var.get().strip())
        except ValueError as exc:
            raise ValueError("Width and height must be integers") from exc
        if width < 2 or height < 2:
            raise ValueError("Width and height must be at least 2")
        algorithm = self._gen_algorithm_var.get().strip()
        if algorithm not in ALGORITHMS:
            raise ValueError("Choose a valid algorithm")
        seed_txt = self._gen_seed_var.get().strip()
        seed: int | None = None
        if seed_txt:
            try:
                seed = int(seed_txt)
            except ValueError as exc:
                raise ValueError("Seed must be an integer or blank") from exc
        algo = ALGORITHMS[algorithm]
        params: dict[str, int] = {}
        for p in algo.params:
            txt = self._algo_param_vars.get(p.key, tk.StringVar(value="")).get().strip()
            if txt == "":
                if p.default is None:
                    raise ValueError(f"{p.label} is required")
                params[p.key] = p.default
            else:
                try:
                    params[p.key] = int(txt)
                except ValueError as exc:
                    raise ValueError(f"{p.label} must be an integer") from exc
            if p.min_value is not None and params[p.key] < p.min_value:
                raise ValueError(f"{p.label} must be >= {p.min_value}")
            if p.max_value is not None and params[p.key] > p.max_value:
                raise ValueError(f"{p.label} must be <= {p.max_value}")
        return width, height, algorithm, seed, params

    def _apply_generated_maze(self, width: int, height: int, algorithm: str, seed: int | None, params: dict[str, int]) -> None:
        apply_generated_maze(self._data, width, height, algorithm=algorithm, seed=seed, params=params)
        self._last_generate_params = {
            "width": width,
            "height": height,
            "algorithm": algorithm,
            "seed": "" if seed is None else str(seed),
            "params": dict(params),
        }
        self._gen_width_var.set(str(width))
        self._gen_height_var.set(str(height))
        self._gen_algorithm_var.set(algorithm)
        self._render_algorithm_param_fields()
        for key, value in params.items():
            if key in self._algo_param_vars:
                self._algo_param_vars[key].set(str(value))
        self._gen_seed_var.set("" if seed is None else str(seed))
        self._dirty = True
        self._sync_facing_from_data()
        self._refresh_surface_values()
        self._update_title()
        self.redraw()

    def _validate(self) -> None:
        try:
            validate_template_data(self._data)
        except Exception as e:
            messagebox.showerror("Validation failed", str(e))
            self._status.set(str(e))
            return
        self._status.set("Template OK")
        messagebox.showinfo("Validate", "Template OK")

    def _menu_new(self) -> None:
        if self._dirty and not messagebox.askyesno("New", "Discard unsaved changes?"):
            return
        w = simpledialog.askinteger("New template", "Width:", initialvalue=5, minvalue=2, maxvalue=80)
        if w is None:
            return
        h = simpledialog.askinteger("New template", "Height:", initialvalue=5, minvalue=2, maxvalue=80)
        if h is None:
            return
        self._path = None
        self._data = _blank_template(w, h)
        self._dirty = True
        self._sync_facing_from_data()
        self._refresh_surface_values()
        self._update_title()
        self.redraw()
        self._status.set("New template")

    def _menu_open(self) -> None:
        if self._dirty and not messagebox.askyesno("Open", "Discard unsaved changes?"):
            return
        path = filedialog.askopenfilename(
            title="Open template",
            filetypes=[("YAML", "*.yaml *.yml"), ("All", "*.*")],
        )
        if not path:
            return
        p = Path(path)
        try:
            data = load_template(p)
            normalize_template_grid_for_edit(data)
        except Exception as e:
            messagebox.showerror("Open failed", str(e))
            return
        self._path = p
        self._data = data
        self._dirty = False
        self._sync_facing_from_data()
        self._refresh_surface_values()
        self._update_title()
        self.redraw()
        self._status.set(f"Opened {p.name}")

    def _menu_save(self) -> None:
        if self._path is None:
            self._menu_save_as()
            return
        self._write_path(self._path)

    def _menu_save_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save template as",
            defaultextension=".yaml",
            filetypes=[("YAML", "*.yaml"), ("All", "*.*")],
        )
        if not path:
            return
        self._path = Path(path)
        self._write_path(self._path)

    def _write_path(self, path: Path) -> None:
        try:
            validate_template_data(self._data)
        except Exception as e:
            if not messagebox.askyesno("Validation warning", f"{e}\n\nSave anyway?"):
                return
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self._data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self._dirty = False
        self._update_title()
        self._status.set(f"Saved {path.name}")

    def _generate_maze(self) -> None:
        try:
            w, h, algorithm, seed, params = self._collect_generation_inputs()
            self._apply_generated_maze(w, h, algorithm, seed, params)
        except Exception as e:
            self._gen_error_var.set(str(e))
            messagebox.showerror("Generate maze", str(e))
            return
        self._gen_error_var.set("")
        self._status.set(f"Generated maze via {algorithm} (spawn/exit reset; monsters unchanged — validate if needed)")

    def _quick_generate_maze(self) -> None:
        p = self._last_generate_params
        seed = random.randint(0, 2**31 - 1)
        try:
            self._apply_generated_maze(
                int(p["width"]),
                int(p["height"]),
                str(p["algorithm"]),
                seed,
                dict(p.get("params") or {}),
            )
        except Exception as e:
            self._gen_error_var.set(str(e))
            messagebox.showerror("Quick generate", str(e))
            return
        self._gen_error_var.set("")
        self._status.set(f"Quick generated maze via {p['algorithm']} (seed {seed})")

    def _quit(self) -> None:
        if self._dirty and not messagebox.askyesno("Quit", "Discard unsaved changes?"):
            return
        self.root.destroy()

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.mainloop()


def main() -> None:
    root = tk.Tk()
    DesignerApp(root).run()
