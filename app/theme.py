from __future__ import annotations

import atexit
import json
import os
import platform
import tkinter as tk
import tkinter.font as tkfont

import ttkbootstrap as tb
from ttkbootstrap.tooltip import ToolTip

BASE_THEME = "superhero"      # Ausgangsbasis
DEFAULT_THEME = "superhero_lila"  # dunkel / blau mit lila Akzent
ALT_THEME = "flatly"          # hell / modern
THEME_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "superhero_lila.json")
)


def _minsize_for_screen(root: tk.Tk) -> tuple[int, int]:
    """Mindestgröße relativ zur Bildschirmauflösung."""
    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    min_w = max(800, int(w * 0.6))
    min_h = max(520, int(h * 0.6))
    return min_w, min_h

def make_root(title: str = "GSA Flashcards", theme: str = DEFAULT_THEME) -> tb.Window:
    _enable_hidpi_awareness()
    root = tb.Window(title=title, themename=BASE_THEME)
    _load_user_theme(root.style)
    try:
        root.style.theme_use(theme)
    except Exception:
        root.style.theme_use(BASE_THEME)
    _apply_readability_tweaks(root)
    mw, mh = _minsize_for_screen(root)
    root.minsize(mw, mh)
    _restore_geometry(root)                # letzte Fenstergröße wiederherstellen
    _persist_geometry_on_exit(root)
    return root

def attach_theme_toggle(root: tk.Tk, style: tb.Style) -> None:
    btn = tb.Button(root, text="Dark/Light", bootstyle="secondary-outline")
    btn.place(relx=1.0, x=-16, y=12, anchor="ne")
    ToolTip(btn, text="Theme umschalten (Strg+D)")  # kleine UX‑Hilfe
    def _toggle(*_):
        cur = style.theme.name
        style.theme_use(ALT_THEME if cur == DEFAULT_THEME else DEFAULT_THEME)
    btn.configure(command=_toggle)
    root.bind("<Control-d>", _toggle)

def _enable_hidpi_awareness():
    try:
        if platform.system() == "Windows":
            import ctypes  # Per‑Monitor DPI Aware (fallback)
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

def _cfg_path() -> str:
    home = os.path.expanduser("~")
    if platform.system() == "Windows":
        base = os.path.join(home, "AppData", "Roaming", "Lernkarten")
    else:
        base = os.path.join(home, ".config", "lernkarten")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "gui.json")


def _restore_geometry(root: tk.Tk) -> None:
    cfg = _cfg_path()
    try:
        if os.path.exists(cfg):
            with open(cfg, encoding="utf-8") as f:
                geo = json.load(f).get("geometry")
            if geo:
                root.geometry(geo)
    except Exception:
        pass


def _persist_geometry_on_exit(root: tk.Tk) -> None:
    cfg = _cfg_path()
    @atexit.register
    def _save() -> None:
        try:
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump({"geometry": root.wm_geometry()}, f)
        except Exception:
            pass

def _load_user_theme(style: tb.Style) -> None:
    try:
        style.load_user_themes(THEME_FILE)
    except Exception:
        pass


def _apply_readability_tweaks(root: tk.Tk) -> None:
    """Moderate Verbesserungen für Lesbarkeit und Bedienbarkeit."""
    try:
        for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont"):
            f = tkfont.nametofont(name)
            f.configure(size=f.cget("size") + 1)
    except Exception:
        pass

    try:
        root.tk.call("tk", "scaling", 1.15)
    except Exception:
        pass

    try:
        style = root.style
        style.configure("TButton", padding=(8, 6))
        style.configure("TScale", sliderlength=24)
    except Exception:
        pass
