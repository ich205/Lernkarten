"""Tkinter-basierte Desktop-Oberfläche.

Die GUI verbindet Benutzerinteraktionen mit der Pipeline. Viele
Standardwerte (z. B. Startsprache, Fragen pro Chunk) stammen aus
``config.toml`` und werden über `load_config` eingelesen. Sie ruft
`pipeline.LernkartenPipeline` auf, um PDFs einzulesen, OpenAI anzusprechen und die
Ergebnisse zu exportieren.
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog
import webbrowser
import ttkbootstrap as tb
from ttkbootstrap.tooltip import ToolTip
from ttkbootstrap.toast import ToastNotification
from ttkbootstrap.scrolled import ScrolledText

from openai import OpenAIError

from .config import load_config, load_api_key
from .pipeline import LernkartenPipeline
from .cost import estimate_cost_for_text
from .pdf_utils import try_extract_text
from .models import count_tokens_rough
from .logging_utils import get_logger
from .theme import make_root, attach_theme_toggle, DEFAULT_THEME, ALT_THEME

logger = get_logger(__name__)

APP_TITLE = "GSA Flashcards (GPT‑5 Serie)"
LOG_MAX_LINES = 1000

def run_gui():
    cfg = load_config()

    api_key_initial, source = load_api_key(cfg)

    theme_pref = cfg["ui"].get("theme", "auto")
    initial_theme = ALT_THEME if theme_pref == "light" else DEFAULT_THEME
    root = make_root(APP_TITLE, theme=initial_theme)
    style = root.style
    attach_theme_toggle(root, style)

    # State variables
    api_key_var = tk.StringVar(value=api_key_initial)
    file_path_var = tk.StringVar(value="")
    out_dir_var = tk.StringVar(value=os.path.abspath("."))
    thorough_var = tk.IntVar(value=int(cfg["prompting"].get("max_questions_per_chunk_default", 8)))
    budget_var = tk.DoubleVar(value=2.0)
    model_var = tk.StringVar(value=cfg["models"].get("qa_model", "gpt-5-mini"))
    label_model_var = tk.StringVar(value=cfg["models"].get("label_model", "gpt-5-nano"))
    use_cache_var = tk.BooleanVar(value=True)
    limit_by_budget_var = tk.BooleanVar(value=True)
    status_var = tk.StringVar(value="Bereit")

    # ===== Layout =====
    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)

    # Toolbar
    toolbar = tb.Frame(root, padding=8)
    toolbar.grid(row=0, column=0, sticky="ew")
    toolbar.columnconfigure(99, weight=1)
    btn_open = tb.Button(toolbar, text="Datei öffnen", bootstyle="secondary")
    btn_est = tb.Button(toolbar, text="Schätzung", bootstyle="info")
    btn_start = tb.Button(toolbar, text="Start", bootstyle="primary")
    btn_abort = tb.Button(toolbar, text="Abbrechen", bootstyle="danger-outline")
    btn_open.grid(row=0, column=0, padx=4)
    btn_est.grid(row=0, column=1, padx=4)
    btn_start.grid(row=0, column=2, padx=4)
    btn_abort.grid(row=0, column=3, padx=4)
    ToolTip(btn_start, text="Startet die Verarbeitung (Strg+R)")

    # Center PanedWindow
    center = tb.Panedwindow(root, orient="horizontal")
    center.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

    left = tb.Labelframe(center, text="Quelle & Einstellungen", padding=10)
    right = tb.Notebook(center)
    center.add(left, weight=1, minsize=320)
    center.add(right, weight=3, minsize=480)

    for c in range(2):
        left.columnconfigure(c, weight=1)

    # Left inputs
    row = 0
    tb.Label(left, text="Datei").grid(row=row, column=0, sticky="w")
    path_row = tb.Frame(left)
    path_row.grid(row=row, column=1, sticky="ew", pady=(0,6))
    path_row.columnconfigure(0, weight=1)
    tb.Entry(path_row, textvariable=file_path_var).grid(row=0, column=0, sticky="ew")
    btn_browse = tb.Button(path_row, text="…")
    btn_browse.grid(row=0, column=1, padx=4)
    row += 1

    tb.Label(left, text="API‑Key").grid(row=row, column=0, sticky="w")
    ent_api = tb.Entry(left, textvariable=api_key_var, show="•")
    ent_api.grid(row=row, column=1, sticky="ew", pady=(0,6))
    ToolTip(ent_api, text="OpenAI API-Key (wird nicht gespeichert)")
    row += 1

    tb.Label(left, text="Label‑Modell").grid(row=row, column=0, sticky="w")
    tb.Combobox(left, textvariable=label_model_var, values=["gpt-5-nano","gpt-5-mini","gpt-5"]).grid(row=row, column=1, sticky="ew")
    row += 1

    tb.Label(left, text="QA‑Modell").grid(row=row, column=0, sticky="w")
    tb.Combobox(left, textvariable=model_var, values=["gpt-5-mini","gpt-5"]).grid(row=row, column=1, sticky="ew", pady=(0,6))
    row += 1

    tb.Label(left, text="Gründlichkeit").grid(row=row, column=0, sticky="w")
    slider = tb.Scale(
        left,
        from_=4,
        to=16,
        value=thorough_var.get(),
        bootstyle="info",
        length=180,
    )
    slider.grid(row=row, column=1, sticky="ew")
    slider.configure(sliderlength=24)
    ToolTip(slider, text="4/8/16 Fragen pro Segment")
    def _slider(v):
        thorough_var.set(int(float(v)))
    slider.configure(command=_slider)
    row += 1
    tb.Label(left, textvariable=thorough_var).grid(row=row, column=1, sticky="w")
    row += 1

    tb.Label(left, text="Budget (USD)").grid(row=row, column=0, sticky="w")
    spin_budget = tb.Spinbox(left, from_=0.0, to=100.0, increment=0.5, textvariable=budget_var)
    spin_budget.grid(row=row, column=1, sticky="ew", pady=(0,6))
    ToolTip(spin_budget, text="Grenze für OpenAI-Kosten")
    row += 1

    tb.Checkbutton(left, text="Autom. herunterskalieren", variable=limit_by_budget_var).grid(row=row, column=1, sticky="w")
    row += 1

    tb.Label(left, text="Ausgabeordner").grid(row=row, column=0, sticky="w")
    out_row = tb.Frame(left)
    out_row.grid(row=row, column=1, sticky="ew", pady=(0,6))
    out_row.columnconfigure(0, weight=1)
    tb.Entry(out_row, textvariable=out_dir_var).grid(row=0, column=0, sticky="ew")
    btn_out = tb.Button(out_row, text="…")
    btn_out.grid(row=0, column=1, padx=4)
    row += 1

    tb.Checkbutton(left, text="Cache verwenden", variable=use_cache_var).grid(row=row, column=1, sticky="w")
    row += 1

    # Tabs on right
    tab_preview = tb.Frame(right, padding=8)
    tab_log = tb.Frame(right, padding=0)
    tab_export = tb.Frame(right, padding=8)
    right.add(tab_preview, text="Vorschau")
    right.add(tab_log, text="Log")
    right.add(tab_export, text="Export")

    log_widget = ScrolledText(tab_log, wrap="word")
    log_widget.pack(fill="both", expand=True)

    # Status bar
    status = tb.Frame(root, padding=(10,6))
    status.grid(row=2, column=0, sticky="ew")
    status.columnconfigure(0, weight=1)
    tb.Label(status, textvariable=status_var).grid(row=0, column=0, sticky="w")
    progress = tb.Progressbar(status, mode="determinate", maximum=100, bootstyle="info-striped")
    progress.grid(row=0, column=1, sticky="e", padx=6)

    # ===== Functions =====
    def log(msg: str) -> None:
        log_widget.insert("end", msg + "\n")
        log_widget.see("end")
        if int(log_widget.index('end-1c').split('.')[0]) > LOG_MAX_LINES:
            log_widget.delete("1.0", "2.0")

    def choose_file() -> None:
        p = filedialog.askopenfilename(filetypes=[("PDF/TXT","*.pdf *.txt"), ("Alle Dateien","*.*")])
        if p:
            file_path_var.set(p)

    def choose_out() -> None:
        p = filedialog.askdirectory()
        if p:
            out_dir_var.set(p)

    def open_export() -> None:
        p = out_dir_var.get().strip() or "."
        webbrowser.open(os.path.abspath(p))

    def estimate() -> None:
        p = file_path_var.get().strip()
        if not p:
            ToastNotification(title="Fehler", message="Bitte zunächst eine Datei wählen.", bootstyle="danger").show_toast()
            return
        raw = try_extract_text(p)
        if not raw.strip():
            ToastNotification(title="Fehler", message="Konnte keinen Text extrahieren.", bootstyle="danger").show_toast()
            return
        model = model_var.get()
        label_model = label_model_var.get()
        thorough = thorough_var.get()
        est = estimate_cost_for_text(raw, model=model, label_model=label_model, questions_per_chunk=thorough)
        log(f"[SCHÄTZUNG] Tokens_in={est['in_tokens']:,} | Tokens_out≈{est['out_tokens']:,} | Chunks={est['chunks']}")
        log(f"  Label‑Kosten (Nano)≈ ${est['cost_label_usd']:.4f}  | QA‑Kosten ({model})≈ ${est['cost_qa_usd']:.4f}  | Gesamt≈ ${est['total_cost_usd']:.4f}")

    def start() -> None:
        p = file_path_var.get().strip()
        if not p:
            ToastNotification(title="Fehler", message="Bitte Datei wählen.", bootstyle="danger").show_toast()
            return
        api = api_key_var.get().strip()
        if not api:
            api, _ = load_api_key(cfg)
        if not api:
            ToastNotification(title="Fehler", message="Bitte API‑Key eingeben (nur für diese Sitzung).", bootstyle="danger").show_toast()
            return
        outd = out_dir_var.get().strip() or "."
        os.makedirs(outd, exist_ok=True)
        pipeline = LernkartenPipeline(
            api_key=api,
            qa_model=model_var.get(),
            label_model=label_model_var.get(),
            use_cache=use_cache_var.get(),
            budget_usd=float(budget_var.get() or 0),
            limit_by_budget=limit_by_budget_var.get(),
            questions_per_chunk=thorough_var.get(),
            ui_logger=log,
            ui_progress=lambda v: progress.configure(value=v),
            ui_status=lambda s: status_var.set(s),
        )
        def worker():
            try:
                out = pipeline.run(p, out_dir=outd)
                root.after(
                    0,
                    lambda: ToastNotification(
                        title="Fertig", message=f"Export erstellt:\n{out}"
                    ).show_toast(),
                )
            except (OSError, ValueError, RuntimeError, OpenAIError) as ex:
                logger.exception("Fehler bei der Pipeline-Ausführung")
                log(f"[FEHLER] {ex}")
                root.after(
                    0,
                    lambda: ToastNotification(
                        title="Fehler",
                        message=f"{ex.__class__.__name__}: {ex}",
                        bootstyle="danger",
                    ).show_toast(),
                )
        threading.Thread(target=worker, daemon=True).start()

    def on_close() -> None:
        api_key_var.set("")
        root.destroy()

    # Button commands
    btn_open.configure(command=choose_file)
    btn_browse.configure(command=choose_file)
    btn_out.configure(command=choose_out)
    btn_est.configure(command=estimate)
    btn_start.configure(command=start)
    btn_abort.configure(command=on_close)

    root.bind("<Control-o>", lambda e: choose_file())
    root.bind("<Control-r>", lambda e: start())
    root.bind("<Control-e>", lambda e: open_export())

    if source in {"config", "file"}:
        ToastNotification(
            title=APP_TITLE,
            message="API-Key wurde aus einer Datei geladen. Klartextspeicherung ist riskant.",
            bootstyle="warning",
        ).show_toast()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
