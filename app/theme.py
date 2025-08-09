from __future__ import annotations
import platform, json, os, atexit
import ttkbootstrap as tb
import tkinter as tk
import tkinter.font as tkfont
from ttkbootstrap.tooltip import ToolTip

BASE_THEME = "superhero"      # Ausgangsbasis
DEFAULT_THEME = "superhero_lila"  # dunkel / blau mit lila Akzent
ALT_THEME = "flatly"          # hell / modern
THEME_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "superhero_lila.json"))

def make_root(title: str = "GSA Flashcards", theme: str = DEFAULT_THEME) -> tb.Window:
    _enable_hidpi_awareness()
    root = tb.Window(title=title, themename=BASE_THEME)
    _load_user_theme(root.style)
    try:
        root.style.theme_use(theme)
    except Exception:
        root.style.theme_use(BASE_THEME)
    _apply_readability_tweaks(root)
    root.minsize(960, 640)                 # genug Platz für 13" Displays
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

def _restore_geometry(root: tk.Tk):
    cfg = os.path.join(os.path.expanduser("~"), ".lernkarte_gui.json")
    try:
        if os.path.exists(cfg):
            geo = json.load(open(cfg, "r", encoding="utf-8")).get("geometry")
            if geo:
                root.geometry(geo)
    except Exception:
        pass

def _persist_geometry_on_exit(root: tk.Tk):
    cfg = os.path.join(os.path.expanduser("~"), ".lernkarte_gui.json")
    @atexit.register
    def _save():
        try:
            json.dump({"geometry": root.wm_geometry()}, open(cfg, "w", encoding="utf-8"))
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
