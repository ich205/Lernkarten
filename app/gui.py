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
from tkinter import ttk, filedialog, messagebox

from openai import OpenAIError

from .config import load_config, load_api_key
from .pipeline import LernkartenPipeline
from .cost import estimate_cost_for_text
from .pdf_utils import try_extract_text
from .models import count_tokens_rough
from .logging_utils import get_logger

logger = get_logger(__name__)

APP_TITLE = "GSA Flashcards (GPT‑5 Serie)"
LOG_MAX_LINES = 1000

def run_gui():
    cfg = load_config()

    api_key_initial, source = load_api_key(cfg)

    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("1000x680")

    # Theming
    style = ttk.Style()
    try:
        if cfg["ui"].get("theme", "auto") == "dark":
            root.tk.call("tk", "scaling", 1.1)
        style.theme_use("clam")
    except tk.TclError:
        pass

    # State variables
    api_key_var = tk.StringVar(value=api_key_initial)
    file_path_var = tk.StringVar(value="")
    out_dir_var = tk.StringVar(value=os.path.abspath("."))
    thorough_var = tk.IntVar(value=int(cfg["prompting"].get("max_questions_per_chunk_default", 8)))
    budget_var = tk.DoubleVar(value=2.0)
    model_var = tk.StringVar(value=cfg["models"].get("qa_model","gpt-5-mini"))
    label_model_var = tk.StringVar(value=cfg["models"].get("label_model","gpt-5-nano"))
    use_cache_var = tk.BooleanVar(value=True)
    limit_by_budget_var = tk.BooleanVar(value=True)

    # Layout
    root.columnconfigure(0, weight=0)
    root.columnconfigure(1, weight=1)
    root.rowconfigure(0, weight=1)

    left = ttk.Frame(root, padding=12)
    left.grid(row=0, column=0, sticky="ns")
    right = ttk.Frame(root, padding=12)
    right.grid(row=0, column=1, sticky="nsew")

    # LEFT: controls
    ttk.Label(left, text="1) Skript wählen (PDF/TXT)").grid(sticky="w")
    path_row = ttk.Frame(left)
    path_row.grid(sticky="ew", pady=(2,10))
    path_entry = ttk.Entry(path_row, textvariable=file_path_var, width=40)
    path_entry.grid(row=0, column=0, sticky="w")
    def choose_file():
        p = filedialog.askopenfilename(filetypes=[("PDF/TXT","*.pdf *.txt"), ("Alle","*.*")])
        if p:
            file_path_var.set(p)
    ttk.Button(path_row, text="Durchsuchen …", command=choose_file).grid(row=0, column=1, padx=6)

    ttk.Separator(left).grid(sticky="ew", pady=6)
    ttk.Label(left, text="2) API‑Key (nur für diese Sitzung)").grid(sticky="w")
    ttk.Entry(left, textvariable=api_key_var, width=40, show="•").grid(sticky="w")
    ttk.Label(left, text="⚠ sensibler Schlüssel – nicht speichern", foreground="red").grid(sticky="w")

    ttk.Separator(left).grid(sticky="ew", pady=6)
    ttk.Label(left, text="3) Modelle").grid(sticky="w")
    ttk.Label(left, text="Label‑Modell (Nano)").grid(sticky="w")
    ttk.Combobox(left, textvariable=label_model_var, values=["gpt-5-nano","gpt-5-mini","gpt-5"], width=20).grid(sticky="w")
    ttk.Label(left, text="QA‑Modell").grid(sticky="w", pady=(6,0))
    ttk.Combobox(left, textvariable=model_var, values=["gpt-5-mini","gpt-5"], width=20).grid(sticky="w")

    ttk.Separator(left).grid(sticky="ew", pady=6)
    ttk.Label(left, text="4) Gründlichkeit (Fragen/Chunk)").grid(sticky="w")
    slider = ttk.Scale(left, from_=4, to=16, orient="horizontal", command=lambda v: thorough_var.set(int(float(v))))
    slider.set(thorough_var.get())
    slider.grid(sticky="ew")
    lbl_val = ttk.Label(left, textvariable=thorough_var)
    lbl_val.grid(sticky="w")

    ttk.Separator(left).grid(sticky="ew", pady=6)
    ttk.Label(left, text="5) Budgetlimit (USD)").grid(sticky="w")
    ttk.Entry(left, textvariable=budget_var, width=10).grid(sticky="w")
    ttk.Checkbutton(left, text="Bei Bedarf automatisch herunterskalieren", variable=limit_by_budget_var).grid(sticky="w")

    ttk.Separator(left).grid(sticky="ew", pady=6)
    ttk.Label(left, text="6) Ausgabeordner").grid(sticky="w")
    out_row = ttk.Frame(left)
    out_row.grid(sticky="ew", pady=(2,10))
    ttk.Entry(out_row, textvariable=out_dir_var, width=40).grid(row=0, column=0, sticky="w")
    def choose_out():
        p = filedialog.askdirectory()
        if p: out_dir_var.set(p)
    ttk.Button(out_row, text="Wählen …", command=choose_out).grid(row=0, column=1, padx=6)

    ttk.Checkbutton(left, text="Cache verwenden", variable=use_cache_var).grid(sticky="w")

    btn_row = ttk.Frame(left)
    btn_row.grid(sticky="ew", pady=(12,0))
    progress = ttk.Progressbar(left, length=240, mode="determinate")
    progress.grid(sticky="ew", pady=(6,0))
    status_var = tk.StringVar(value="")
    ttk.Label(left, textvariable=status_var).grid(sticky="w")

    # RIGHT: log and actions
    ttk.Label(right, text="Log / Schätzung / Ergebnis").grid(sticky="w")
    text = tk.Text(right, height=30)
    text.grid(sticky="nsew")
    right.rowconfigure(1, weight=1)

    def log(msg):
        text.insert("end", msg + "\n")
        text.see("end")
        # truncate
        if int(text.index('end-1c').split('.')[0]) > LOG_MAX_LINES:
            text.delete("1.0", "2.0")

    # Estimation
    def estimate():
        p = file_path_var.get().strip()
        if not p:
            messagebox.showerror("Fehler", "Bitte zunächst eine Datei wählen.")
            return
        raw = try_extract_text(p)
        if not raw.strip():
            messagebox.showerror("Fehler", "Konnte keinen Text extrahieren.")
            return
        model = model_var.get()
        label_model = label_model_var.get()
        thorough = thorough_var.get()
        est = estimate_cost_for_text(raw, model=model, label_model=label_model, questions_per_chunk=thorough)
        log(f"[SCHÄTZUNG] Tokens_in={est['in_tokens']:,} | Tokens_out≈{est['out_tokens']:,} | Chunks={est['chunks']}")
        log(f"  Label‑Kosten (Nano)≈ ${est['cost_label_usd']:.4f}  | QA‑Kosten ({model})≈ ${est['cost_qa_usd']:.4f}  | Gesamt≈ ${est['total_cost_usd']:.4f}")

    def start():
        p = file_path_var.get().strip()
        if not p:
            messagebox.showerror("Fehler", "Bitte Datei wählen.")
            return
        api = api_key_var.get().strip()
        if not api:
            api, _ = load_api_key(cfg)
        if not api:
            messagebox.showerror("Fehler", "Bitte API‑Key eingeben (nur für diese Sitzung).")
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
                messagebox.showinfo("Fertig", f"Export erstellt:\n{out}")
            except (OSError, ValueError, RuntimeError, OpenAIError) as ex:
                logger.exception("Fehler bei der Pipeline-Ausführung")
                log(f"[FEHLER] {ex}")
                messagebox.showerror("Fehler", f"{ex.__class__.__name__}: {ex}")
        threading.Thread(target=worker, daemon=True).start()

    ttk.Button(btn_row, text="Schätzung", command=estimate).grid(row=0, column=0, padx=4)
    ttk.Button(btn_row, text="Start", command=start).grid(row=0, column=1, padx=4)

    def on_close():
        api_key_var.set("")
        root.destroy()

    if source in {"config", "file"}:
        messagebox.showwarning(
            APP_TITLE,
            "API-Key wurde aus einer Datei geladen. Klartextspeicherung ist riskant.",
        )

    root.protocol("WM_DELETE_WINDOW", on_close)

    root.mainloop()
