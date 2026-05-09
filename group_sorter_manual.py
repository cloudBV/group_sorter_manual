import tkinter as tk
from tkinter import messagebox, filedialog
import json
import os
import datetime
from typing import Optional

# ── colours ───────────────────────────────────────────────────────────────────
BG           = "#F5F4F0"
POOL_BG      = "#ECEAE4"
CHIP_BG      = "#FFFFFF"
CHIP_BORDER  = "#CCCAC3"
CHIP_DRAG    = "#D6EAF8"
GROUP_BORDER = "#CCCAC3"
BTN_BG       = "#FFFFFF"
BTN_FG       = "#333333"
TITLE_FG     = "#222222"
SUB_FG       = "#888888"
DELETE_FG    = "#CC4444"
SAVE_FG      = "#1A6B3C"

GROUP_COLORS = ["#EAF3FE", "#EAF6EE", "#FEF6E4", "#FDE8E8", "#F3EAFE", "#E4F7F3"]

FONT_NAME  = ("Segoe UI", 11)
FONT_BOLD  = ("Segoe UI", 11, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_TITLE = ("Segoe UI", 13, "bold")


class GroupSorter(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Group Sorter")
        self.geometry("920x660")
        self.configure(bg=BG)
        self.resizable(True, True)

        self.names:    list[dict]  = []
        self.groups:   list[dict]  = []
        self._next_id: int         = 0
        self._drag_name_id: Optional[int]       = None
        self._ghost:        Optional[tk.Toplevel] = None

        # maps tkinter widget id → group id (avoids monkey-patching tk widgets)
        self._widget_group: dict[int, int] = {}

        self._build_ui()

    # ── uid ───────────────────────────────────────────────────────────────────
    def _uid(self) -> int:
        self._next_id += 1
        return self._next_id

    # ── widget → group registry ───────────────────────────────────────────────
    def _tag(self, widget: tk.Widget, group_id: int) -> None:
        self._widget_group[widget.winfo_id()] = group_id

    # ── ui ────────────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        top = tk.Frame(self, bg=BG, pady=10, padx=14)
        top.pack(fill="x")

        tk.Label(top, text="Group Sorter", font=FONT_TITLE,
                 bg=BG, fg=TITLE_FG).pack(side="left")

        self._entry = tk.Entry(top, font=FONT_NAME, width=20,
                               relief="solid", bd=1, bg=CHIP_BG)
        self._entry.pack(side="left", padx=(14, 5))
        self._entry.bind("<Return>", lambda _e: self._add_name())

        self._btn(top, "+ Add",       self._add_name).pack(side="left", padx=3)
        self._btn(top, "Paste list",  self._paste_names).pack(side="left", padx=3)
        self._btn(top, "+ New group", self._add_group).pack(side="left", padx=3)

        self._btn(top, "Clear all",   self._clear_all, fg=DELETE_FG).pack(side="right", padx=3)
        self._btn(top, "Export .txt", self._export,    fg=BTN_FG).pack(side="right", padx=3)
        self._btn(top, "Load",        self._load,      fg=SAVE_FG).pack(side="right", padx=3)
        self._btn(top, "Save",        self._save,      fg=SAVE_FG).pack(side="right", padx=3)

        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vsb = tk.Scrollbar(outer, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._main = tk.Frame(self._canvas, bg=BG)
        self._win_id = self._canvas.create_window((0, 0), window=self._main, anchor="nw")
        self._main.bind("<Configure>",   lambda _e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda _e: self._canvas.itemconfig(
            self._win_id, width=self._canvas.winfo_width()))
        self._canvas.bind_all("<MouseWheel>", self._scroll)
        self._canvas.bind_all("<Button-4>",   self._scroll)
        self._canvas.bind_all("<Button-5>",   self._scroll)

        self._render()

    def _btn(self, parent: tk.Widget, text: str, cmd: object,
             fg: str = BTN_FG) -> tk.Button:
        return tk.Button(parent, text=text, font=FONT_SMALL, bg=BTN_BG, fg=fg,
                         relief="solid", bd=1, padx=8, pady=4, cursor="hand2",
                         command=cmd, activebackground="#EBEBEB")

    def _scroll(self, event: tk.Event) -> None:
        if   event.num == 4: self._canvas.yview_scroll(-1, "units")
        elif event.num == 5: self._canvas.yview_scroll( 1, "units")
        else:                self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── data ops ──────────────────────────────────────────────────────────────
    def _add_name(self) -> None:
        text = self._entry.get().strip()
        if not text:
            return
        self.names.append({"id": self._uid(), "text": text, "group": None})
        self._entry.delete(0, "end")
        self._render()

    def _paste_names(self) -> None:
        try:
            raw = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo("Nothing to paste", "Clipboard is empty.")
            return

        lines = [line.strip() for line in raw.splitlines()]
        if len(lines) == 1 and "\t" in lines[0]:
            lines = [line.strip() for line in lines[0].split("\t")]

        existing = {n["text"].lower() for n in self.names}
        added = 0
        for line in lines:
            if line and line.lower() not in existing:
                self.names.append({"id": self._uid(), "text": line, "group": None})
                existing.add(line.lower())
                added += 1

        if added:
            self._render()
            messagebox.showinfo("Pasted!", f"Added {added} name{'s' if added != 1 else ''}.")
        else:
            messagebox.showinfo("Nothing new", "All names already exist or clipboard was empty.")

    def _add_group(self) -> None:
        color = GROUP_COLORS[len(self.groups) % len(GROUP_COLORS)]
        self.groups.append({"id": self._uid(),
                            "label": f"Group {len(self.groups) + 1}",
                            "color": color})
        self._render()

    def _remove_name(self, nid: int) -> None:
        self.names = [n for n in self.names if n["id"] != nid]
        self._render()

    def _edit_name(self, nid: int, chip_frame: tk.Frame, lbl_widget: tk.Label) -> None:
        name = next((n for n in self.names if n["id"] == nid), None)
        if not name:
            return
        lbl_widget.pack_forget()
        evar = tk.StringVar(value=name["text"])
        entry = tk.Entry(chip_frame, textvariable=evar, font=FONT_NAME,
                         relief="solid", bd=1, width=max(6, len(name["text"]) + 2))
        entry.pack(side="left")
        entry.focus_set()
        entry.select_range(0, "end")

        def commit(_event: tk.Event) -> None:
            new = evar.get().strip()
            if new:
                name["text"] = new
            entry.destroy()
            self._render()

        def cancel(_event: tk.Event) -> None:
            entry.destroy()
            self._render()

        entry.bind("<Return>",   commit)
        entry.bind("<FocusOut>", commit)
        entry.bind("<Escape>",   cancel)

    def _remove_group(self, gid: int) -> None:
        for n in self.names:
            if n["group"] == gid:
                n["group"] = None
        self.groups = [g for g in self.groups if g["id"] != gid]
        self._render()

    def _rename_group(self, gid: int, lv: tk.StringVar,
                      entry: tk.Entry, lbl: tk.Label) -> None:
        entry.place_forget()
        new = lv.get().strip() or "Unnamed"
        for g in self.groups:
            if g["id"] == gid:
                g["label"] = new
                break
        lbl.config(text=new)

    def _assign(self, name_id: int, group_id: Optional[int]) -> None:
        for n in self.names:
            if n["id"] == name_id:
                n["group"] = group_id
                break
        self._render()

    def _clear_all(self) -> None:
        if messagebox.askyesno("Clear all", "Remove all names and groups?"):
            self.names  = []
            self.groups = []
            self._render()

    # ── save / load ───────────────────────────────────────────────────────────
    def _save(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save session",
            defaultextension=".json",
            filetypes=[("Group Sorter file", "*.json"), ("All files", "*.*")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"next_id": self._next_id,
                       "names":   self.names,
                       "groups":  self.groups}, f, indent=2, ensure_ascii=False)
        messagebox.showinfo("Saved", f"Saved to: {os.path.basename(path)}")

    def _load(self) -> None:
        path = filedialog.askopenfilename(
            title="Load session",
            filetypes=[("Group Sorter file", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._next_id = data.get("next_id", 0)
            self.names    = data.get("names",   [])
            self.groups   = data.get("groups",  [])
            self._render()
            messagebox.showinfo("Loaded", f"Loaded: {os.path.basename(path)}")
        except (OSError, json.JSONDecodeError, KeyError) as ex:
            messagebox.showerror("Error", f"Could not load file:\n{ex}")

    # ── export ────────────────────────────────────────────────────────────────
    def _export(self) -> None:
        if not self.names and not self.groups:
            messagebox.showinfo("Nothing to export", "Add some names or groups first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export grouping",
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")])
        if not path:
            return

        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [f"Group Sorter Export — {stamp}", "=" * 44]

        for g in self.groups:
            members = [n["text"] for n in self.names if n["group"] == g["id"]]
            lines.append(f"\n[ {g['label']} ]  ({len(members)} name)")
            lines.append("-" * 30)
            lines += [f"  • {m}" for m in members] if members else ["  (empty)"]

        unassigned = [n["text"] for n in self.names if n["group"] is None]
        if unassigned:
            lines.append(f"\n[ Unassigned ]  ({len(unassigned)} name)")
            lines.append("-" * 30)
            lines += [f"  • {m}" for m in unassigned]

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        messagebox.showinfo("Exported", f"Saved to: {os.path.basename(path)}")

    # ── render ────────────────────────────────────────────────────────────────
    def _render(self) -> None:
        self._widget_group.clear()
        for w in self._main.winfo_children():
            w.destroy()

        # pool
        pool = tk.LabelFrame(self._main, text="  Unassigned  ",
                             font=FONT_SMALL, bg=POOL_BG, fg=SUB_FG,
                             relief="solid", bd=1, labelanchor="nw",
                             padx=8, pady=8)
        pool.pack(fill="x", padx=6, pady=(8, 12))

        unassigned = [n for n in self.names if n["group"] is None]
        if unassigned:
            wrap = tk.Frame(pool, bg=POOL_BG)
            wrap.pack(fill="x")
            for n in unassigned:
                self._make_chip(wrap, n, POOL_BG)
        else:
            tk.Label(pool, text="Add names above, then drag them into a group →",
                     font=FONT_SMALL, bg=POOL_BG, fg=SUB_FG).pack(anchor="w")

        # groups grid
        if self.groups:
            grid = tk.Frame(self._main, bg=BG)
            grid.pack(fill="both", expand=True, padx=6)
            cols = max(1, min(3, len(self.groups)))
            for i, g in enumerate(self.groups):
                grid_row, grid_col = divmod(i, cols)
                self._make_group_box(grid, g, grid_row, grid_col)
            for c in range(cols):
                grid.columnconfigure(c, weight=1)
        else:
            tk.Label(self._main,
                     text='Click "+ New group" to create a group box',
                     font=FONT_NAME, bg=BG, fg=SUB_FG).pack(pady=30)

    # ── group box ─────────────────────────────────────────────────────────────
    def _make_group_box(self, parent: tk.Frame, g: dict,
                        grid_row: int, grid_col: int) -> None:
        color: str = g.get("color", "#FFFFFF")
        gid:   int = g["id"]

        box = tk.Frame(parent, bg=color, relief="solid", bd=1,
                       highlightbackground=GROUP_BORDER, highlightthickness=1)
        box.grid(row=grid_row, column=grid_col, padx=5, pady=5, sticky="nsew")
        parent.rowconfigure(grid_row, weight=1)

        hdr = tk.Frame(box, bg=color)
        hdr.pack(fill="x", padx=8, pady=(8, 4))

        self._tag(box, gid)
        self._tag(hdr, gid)

        lv  = tk.StringVar(value=g["label"])
        lbl = tk.Label(hdr, textvariable=lv, font=FONT_BOLD,
                       bg=color, fg=TITLE_FG, cursor="xterm")
        lbl.pack(side="left")

        ent = tk.Entry(hdr, textvariable=lv, font=FONT_BOLD,
                       relief="solid", bd=1, width=16)

        # named functions so the type checker can see their signatures clearly
        def start_edit(_event: tk.Event) -> None:
            ent.place(in_=lbl, x=0, y=0,
                      width=lbl.winfo_width() + 40,
                      height=lbl.winfo_height() + 2)
            ent.focus_set()
            ent.select_range(0, "end")

        def finish_edit(_event: tk.Event) -> None:
            self._rename_group(gid, lv, ent, lbl)

        lbl.bind("<Double-Button-1>", start_edit)
        ent.bind("<Return>",          finish_edit)
        ent.bind("<FocusOut>",        finish_edit)

        count = sum(1 for n in self.names if n["group"] == gid)
        tk.Label(hdr, text=f"{count} name", font=FONT_SMALL,
                 bg=color, fg=SUB_FG).pack(side="left", padx=6)

        # named function replaces the lambda that confused the checker
        def on_delete() -> None:
            self._remove_group(gid)

        tk.Button(hdr, text="✕", font=FONT_SMALL, fg=DELETE_FG,
                  bg=color, relief="flat", bd=0, cursor="hand2",
                  command=on_delete).pack(side="right")

        tk.Frame(box, bg=GROUP_BORDER, height=1).pack(fill="x", padx=8)

        body = tk.Frame(box, bg=color, padx=8, pady=8)
        body.pack(fill="both", expand=True)
        self._tag(body, gid)

        assigned = [n for n in self.names if n["group"] == gid]
        if assigned:
            for n in assigned:
                self._make_chip(body, n, color)
        else:
            tk.Label(body, text="drop names here",
                     font=FONT_SMALL, bg=color, fg=SUB_FG).pack(anchor="w")

    # ── chip ──────────────────────────────────────────────────────────────────
    def _make_chip(self, parent: tk.Frame, n: dict, bg_ctx: str) -> None:
        nid:  int      = n["id"]
        row_frame = tk.Frame(parent, bg=bg_ctx)
        row_frame.pack(anchor="w", pady=2)

        chip = tk.Frame(row_frame, bg=CHIP_BG, relief="solid", bd=1,
                        highlightbackground=CHIP_BORDER, highlightthickness=1,
                        cursor="fleur", padx=8, pady=4)
        chip.pack(side="left")

        lbl = tk.Label(chip, text=n["text"], font=FONT_NAME,
                       bg=CHIP_BG, fg=TITLE_FG, cursor="fleur")
        lbl.pack(side="left")

        def on_remove() -> None:
            self._remove_name(nid)

        tk.Button(chip, text="✕", font=("Segoe UI", 8), fg=SUB_FG,
                  bg=CHIP_BG, relief="flat", bd=0, cursor="hand2",
                  command=on_remove).pack(side="left", padx=(4, 0))

        def on_double_click(_event: tk.Event) -> None:
            self._edit_name(nid, chip, lbl)

        def on_press(event: tk.Event) -> None:
            self._drag_start(event, nid)

        for widget in (chip, lbl):
            widget.bind("<Double-Button-1>", on_double_click)
            widget.bind("<ButtonPress-1>",   on_press)
            widget.bind("<B1-Motion>",       self._drag_motion)
            widget.bind("<ButtonRelease-1>", self._drag_end)

    # ── drag ──────────────────────────────────────────────────────────────────
    def _drag_start(self, event: tk.Event, nid: int) -> None:
        name = next((n for n in self.names if n["id"] == nid), None)
        if not name:
            return
        self._drag_name_id = nid
        ghost = tk.Toplevel(self)
        ghost.overrideredirect(True)
        ghost.attributes("-alpha", 0.80)
        ghost.configure(bg=CHIP_DRAG)
        tk.Label(ghost, text=name["text"], font=FONT_NAME,
                 bg=CHIP_DRAG, fg=TITLE_FG, padx=10, pady=6).pack()
        ghost.geometry(f"+{event.x_root - 20}+{event.y_root - 14}")
        self._ghost = ghost

    def _drag_motion(self, event: tk.Event) -> None:
        if self._ghost is not None:
            self._ghost.geometry(f"+{event.x_root - 20}+{event.y_root - 14}")

    def _drag_end(self, event: tk.Event) -> None:
        if self._ghost is not None:
            self._ghost.destroy()
            self._ghost = None

        if self._drag_name_id is None:
            return

        target = self._group_at(event.x_root, event.y_root)
        self._assign(self._drag_name_id, target)
        self._drag_name_id = None

    # ── hit-test ──────────────────────────────────────────────────────────────
    def _group_at(self, rx: int, ry: int) -> Optional[int]:
        """Return the group id of whichever registered widget is under (rx, ry)."""
        for widget_id, group_id in self._widget_group.items():
            try:
                widget = self.nametowidget(
                    self.tk.call("winfo", "pathname", widget_id))
                wx = widget.winfo_rootx()
                wy = widget.winfo_rooty()
                if wx <= rx <= wx + widget.winfo_width() and \
                   wy <= ry <= wy + widget.winfo_height():
                    return group_id
            except Exception:
                continue
        return None


if __name__ == "__main__":
    GroupSorter().mainloop()
