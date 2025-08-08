# app/main.py
from __future__ import annotations
import os, sys, threading, traceback
from tkinter import Tk, ttk, filedialog, StringVar, IntVar, BooleanVar, Text, END, N, S, E, W
from tkinter import messagebox

from .config import DEFAULT_CLASSIFY_MODEL, DEFAULT_QA_MODEL, GPT5, GPT5_MINI, GPT5_NANO, DEFAULT_LANGUAGE
from .pipeline import LernkartenPipeline
from .openai_client import OpenAISettings

APP_TITLE = "Lernkarten-Generator (Installer-fix)"

def safe_tk():
    try:
        root = Tk()
        return root
    except Exception as e:
        print("Fehler beim Starten der GUI:", e, file=sys.stderr)
        sys.exit(1)

class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("920x640")

        self.file_path = StringVar(value="")
        self.api_key = StringVar(value="")
        self.classify_model = StringVar(value=DEFAULT_CLASSIFY_MODEL)
        self.qa_model = StringVar(value=DEFAULT_QA_MODEL)
        self.questions_per_chunk = IntVar(value=8)
        self.language = StringVar(value=DEFAULT_LANGUAGE)

        self.progress = StringVar(value="Bereit.")
        self.cost_label = StringVar(value="—")

        self._pipeline = None
        self._segments = None
        self._full_text = ""
        self._stop_flag = False

        self.build_ui()

    def build_ui(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.grid(row=0, column=0, sticky=(N,S,E,W))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Row 0: Datei
        ttk.Label(frm, text="Skript (PDF):").grid(row=0, column=0, sticky=W)
        ttk.Entry(frm, textvariable=self.file_path, width=80).grid(row=0, column=1, sticky=(E,W))
        ttk.Button(frm, text="Auswaehlen…", command=self.pick_file).grid(row=0, column=2, padx=5)
        frm.columnconfigure(1, weight=1)

        # Row 1: API Key
        ttk.Label(frm, text="OpenAI API-Key:").grid(row=1, column=0, sticky=W, pady=(8,0))
        ttk.Entry(frm, textvariable=self.api_key, width=50, show="•").grid(row=1, column=1, sticky=(E,W), pady=(8,0))

        # Row 2: Modelle
        model_values = (GPT5, GPT5_MINI, GPT5_NANO)
        ttk.Label(frm, text="Klassifikation (Nano):").grid(row=2, column=0, sticky=W, pady=(8,0))
        ttk.Combobox(frm, textvariable=self.classify_model, values=model_values, width=20).grid(row=2, column=1, sticky=W, pady=(8,0))

        ttk.Label(frm, text="Lernkarten (Mini/5):").grid(row=3, column=0, sticky=W)
        ttk.Combobox(frm, textvariable=self.qa_model, values=model_values, width=20).grid(row=3, column=1, sticky=W)

        # Row 4: Sprache
        ttk.Label(frm, text="Sprache:").grid(row=4, column=0, sticky=W)
        ttk.Combobox(frm, textvariable=self.language, values=("de","en"), width=10).grid(row=4, column=1, sticky=W)

        # Row 5: Slider
        ttk.Label(frm, text="Fragen pro Chunk:").grid(row=5, column=0, sticky=W, pady=(8,0))
        scale = ttk.Scale(frm, from_=2, to=24, orient="horizontal", command=self.on_scale)
        scale.set(self.questions_per_chunk.get())
        scale.grid(row=5, column=1, sticky=(E,W), pady=(8,0))
        self.scale_widget = scale

        # Row 6: Kosten
        ttk.Label(frm, text="Kosten-Schaetzung:").grid(row=6, column=0, sticky=W)
        ttk.Label(frm, textvariable=self.cost_label).grid(row=6, column=1, sticky=W)

        # Row 7: Buttons
        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=3, sticky=W, pady=(10,5))
        ttk.Button(btns, text="1) Segmentieren & Schaetzen", command=self.segment_and_estimate).grid(row=0, column=0, padx=5)
        ttk.Button(btns, text="2) Start (Labeln + Lernkarten + Export)", command=self.start_pipeline).grid(row=0, column=1, padx=5)
        ttk.Button(btns, text="Abbrechen", command=self.cancel).grid(row=0, column=2, padx=5)

        # Row 8: Log
        ttk.Label(frm, text="Protokoll:").grid(row=8, column=0, sticky=W)
        self.log = Text(frm, height=15)
        self.log.grid(row=9, column=0, columnspan=3, sticky=(N,S,E,W))
        frm.rowconfigure(9, weight=1)

        # Footer status
        ttk.Label(frm, textvariable=self.progress).grid(row=10, column=0, columnspan=3, sticky=(W))

    def on_scale(self, val):
        try:
            self.questions_per_chunk.set(int(float(val)))
            self.update_cost_label()
        except Exception:
            pass

    def pick_file(self):
        p = filedialog.askopenfilename(
            title="Skript waehlen (PDF)",
            filetypes=[("PDF", "*.pdf"), ("Alle Dateien", "*.*")]
        )
        if p:
            self.file_path.set(p)

    def logln(self, msg):
        self.log.insert(END, msg + "\n")
        self.log.see(END)

    def segment_and_estimate(self):
        path = self.file_path.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showerror(APP_TITLE, "Bitte eine PDF-Datei waehlen.")
            return
        self.progress.set("Lese & segmentiere ...")
        self.root.update()

        try:
            from .pdf_ingest import extract_text_from_pdf, segment_text
            from .tokenizer_utils import Tokenizer

            txt = extract_text_from_pdf(path)
            self._full_text = txt
            segs = segment_text(txt)
            self._segments = segs
            self.logln(f"Segmentiert: {len(segs)} Segmente.")
            self.progress.set(f"Segmentierung fertig: {len(segs)} Segmente.")
            self.update_cost_label()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror(APP_TITLE, f"Fehler bei Segmentierung: {e}")
            self.progress.set("Fehler.")
            return

    def update_cost_label(self):
        if not self._segments or not self._full_text:
            self.cost_label.set("— (erst segmentieren)")
            return
        try:
            from .tokenizer_utils import Tokenizer
            from .pipeline import LernkartenPipeline
            from .config import PRICES
            tok = Tokenizer()
            seg_token_counts = [tok.count(s) for s in self._segments]
            seg_avg = int(sum(seg_token_counts)/max(1, len(seg_token_counts)))
            n_segments = len(self._segments)
            qpc = self.questions_per_chunk.get()

            # settings nur fuer Schaetzung
            settings = OpenAISettings(api_key="DUMMY",
                                      classify_model=self.classify_model.get(),
                                      qa_model=self.qa_model.get())
            pipe = LernkartenPipeline(settings)
            est = pipe.estimate_cost(
                self._full_text,
                n_segments,
                seg_avg,
                qpc,
                settings.classify_model,
                settings.qa_model,
            )
            s = (f"Klassifikation ({est['classification']['model']}): "
                 f"{est['classification']['input_tokens']:,} in / {est['classification']['output_tokens']:,} out → ${est['classification']['usd']:.4f};  "
                 f"Lernkarten ({est['qa']['model']}): "
                 f"{est['qa']['input_tokens']:,} in / {est['qa']['output_tokens']:,} out → ${est['qa']['usd']:.4f};  "
                 f"GESAMT ≈ ${est['sum_usd']:.4f} (Schätzung)")
            self.cost_label.set(s)
        except Exception as e:
            self.cost_label.set(f"Fehler bei Schätzung: {e}")

    def start_pipeline(self):
        if not self._segments:
            messagebox.showinfo(APP_TITLE, "Bitte zuerst segmentieren & schaetzen.")
            return
        if not self.api_key.get().strip():
            messagebox.showerror(APP_TITLE, "Bitte OpenAI API-Key eingeben (wird nicht gespeichert).")
            return
        self._stop_flag = False
        t = threading.Thread(target=self._run_pipeline_thread, daemon=True)
        t.start()

    def cancel(self):
        self._stop_flag = True
        self.progress.set("Abbruch angefordert …")

    def _run_pipeline_thread(self):
        try:
            settings = OpenAISettings(
                api_key=self.api_key.get().strip(),
                classify_model=self.classify_model.get().strip(),
                qa_model=self.qa_model.get().strip(),
            )
            pipe = LernkartenPipeline(settings)
            # Labeln
            self.progress.set("Labeln (Nano) …")
            self.logln("Starte Klassifikation (Nano)…")
            seg_objs = []
            for t in self._segments:
                if self._stop_flag: raise RuntimeError("Abgebrochen")
                seg_objs.append(t)
            seg_objs = pipe.classify(seg_objs)

            filtered = [s for s in seg_objs if s.keep]
            removed = len(seg_objs) - len(filtered)
            self.logln(f"Gefiltert: {removed} Segmente verworfen (Ueberschrift/Gliederung/Vorwort). "
                       f"{len(filtered)} verbleiben.")

            # Lernkarten
            self.progress.set("Erzeuge Lernkarten …")
            self.logln("Fragen/Antworten werden generiert …")
            rows = pipe.generate_cards(filtered, self.questions_per_chunk.get(), self.language.get())

            # Export
            out_path = os.path.join(os.path.dirname(__file__), "..", "output.xlsx")
            out_path = os.path.abspath(out_path)
            pipe.export_excel(rows, out_path)
            self.progress.set(f"Fertig. Export: {out_path}")
            self.logln(f"Exportiert nach: {out_path}")
            messagebox.showinfo(APP_TITLE, f"Fertig! Datei gespeichert:\n{out_path}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror(APP_TITLE, f"Fehler: {e}")
            self.progress.set("Fehler.")

def main():
    root = safe_tk()
    style = ttk.Style(root)
    # Nutze system theme
    try:
        style.theme_use(style.theme_use())
    except Exception:
        pass
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
