"""Standalone-Startskript für die alternative Tkinter-Oberfläche.

Während `gui.py` eine vereinfachte Oberfläche bietet, stellt dieses Modul eine
ausführlichere Variante bereit. Es demonstriert, wie `LernkartenPipeline` direkt
aus einem Skript heraus verwendet werden kann.
"""

from __future__ import annotations
import os, sys, threading
from tkinter import (
    filedialog,
    StringVar,
    IntVar,
    BooleanVar,
    END,
    N,
    S,
    E,
    W,
    TclError,
)
import ttkbootstrap as tb
from ttkbootstrap import ttk
from ttkbootstrap.scrolled import ScrolledText
from ttkbootstrap.toast import ToastNotification
from app.theme import make_root, attach_theme_toggle
from pypdf.errors import PdfReadError
from openai import OpenAIError

from .config import (
    DEFAULT_CLASSIFY_MODEL,
    DEFAULT_QA_MODEL,
    GPT5,
    GPT5_MINI,
    GPT5_NANO,
    DEFAULT_LANGUAGE,
    load_api_key,
)
from .pipeline import LernkartenPipeline
from .openai_client import OpenAISettings
from .logging_utils import get_logger

logger = get_logger(__name__)

APP_TITLE = "Lernkarten-Generator (Installer-fix)"

def safe_tk():
    try:
        root = make_root(APP_TITLE)
        return root
    except TclError as e:
        logger.exception("Fehler beim Starten der GUI")
        sys.exit(1)

class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)

        self.file_path = StringVar(value="")
        key, source = load_api_key()
        self.api_key = StringVar(value=key)
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
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._total_pages = 0

        self.build_ui()
        if source in {"config", "file"}:
            ToastNotification(
                title=APP_TITLE,
                message="API-Key wurde aus einer Datei geladen. Speicherung im Klartext ist riskant.",
                bootstyle="warning",
            ).show_toast()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_ui(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.grid(row=0, column=0, sticky=(N,S,E,W))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Row 0: Datei
        ttk.Label(frm, text="Skript (PDF):").grid(row=0, column=0, sticky=W)
        ttk.Entry(frm, textvariable=self.file_path).grid(row=0, column=1, sticky=(E,W))
        ttk.Button(frm, text="Auswaehlen…", command=self.pick_file).grid(row=0, column=2, padx=5)
        frm.columnconfigure(1, weight=1)

        # Row 1: API Key
        ttk.Label(frm, text="OpenAI API-Key:").grid(row=1, column=0, sticky=W, pady=(8,0))
        ttk.Entry(frm, textvariable=self.api_key, show="•").grid(row=1, column=1, sticky=(E,W), pady=(8,0))
        ttk.Label(
            frm,
            text="⚠ wird nicht gespeichert",
            bootstyle="danger",
        ).grid(row=1, column=2, sticky=W, pady=(8,0))

        # Row 2: Modelle
        model_values = (GPT5, GPT5_MINI, GPT5_NANO)
        ttk.Label(frm, text="Klassifikation (Nano):").grid(row=2, column=0, sticky=W, pady=(8,0))
        ttk.Combobox(frm, textvariable=self.classify_model, values=model_values).grid(row=2, column=1, sticky=W, pady=(8,0))

        ttk.Label(frm, text="Lernkarten (Mini/5):").grid(row=3, column=0, sticky=W)
        ttk.Combobox(frm, textvariable=self.qa_model, values=model_values).grid(row=3, column=1, sticky=W)

        # Row 4: Sprache
        ttk.Label(frm, text="Sprache:").grid(row=4, column=0, sticky=W)
        ttk.Combobox(frm, textvariable=self.language, values=("de","en")).grid(row=4, column=1, sticky=W)

        # Row 5: Slider
        ttk.Label(frm, text="Max. Karten pro Segment:").grid(row=5, column=0, sticky=W, pady=(8,0))
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
        ttk.Button(btns, text="Pause", command=self.pause).grid(row=0, column=2, padx=5)
        ttk.Button(btns, text="Fortsetzen", command=self.resume).grid(row=0, column=3, padx=5)
        ttk.Button(btns, text="Abbrechen", command=self.cancel).grid(row=0, column=4, padx=5)

        # Row 8: Log
        ttk.Label(frm, text="Protokoll:").grid(row=8, column=0, sticky=W)
        self.log = ScrolledText(frm, wrap="word")
        self.log.grid(row=9, column=0, columnspan=3, sticky=(N,S,E,W))
        frm.rowconfigure(9, weight=1)

        # Footer progress bar + status
        self.progress_bar = ttk.Progressbar(frm, mode="determinate")
        self.progress_bar.grid(row=10, column=0, columnspan=3, sticky=(E,W), pady=(5,0))
        ttk.Label(frm, textvariable=self.progress).grid(row=11, column=0, columnspan=3, sticky=(W))

        # Row 12+: Vorschau der aktuellen Karte
        ttk.Label(frm, text="Originaltext:").grid(row=12, column=0, sticky=W, pady=(8,0))
        self.preview_orig = tb.Text(frm, wrap="word")
        self.preview_orig.grid(row=13, column=0, columnspan=3, sticky=(E,W))
        self.preview_orig.configure(state="disabled")

        ttk.Label(frm, text="Frage:").grid(row=14, column=0, sticky=W, pady=(4,0))
        self.preview_frage = tb.Text(frm, wrap="word")
        self.preview_frage.grid(row=15, column=0, columnspan=3, sticky=(E,W))
        self.preview_frage.configure(state="disabled")

        ttk.Label(frm, text="Antwort:").grid(row=16, column=0, sticky=W, pady=(4,0))
        self.preview_antwort = tb.Text(frm, wrap="word")
        self.preview_antwort.grid(row=17, column=0, columnspan=3, sticky=(E,W))
        self.preview_antwort.configure(state="disabled")

    def on_scale(self, val):
        try:
            self.questions_per_chunk.set(int(float(val)))
            self.update_cost_label()
        except (ValueError, TypeError):
            logger.debug("Ungültiger Wert für Slider: %s", val)

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

    def update_preview(self, original: str, frage: str, antwort: str):
        snippet = original.strip()
        if len(snippet) > 200:
            snippet = snippet[:200] + "…"

        def do_update():
            for widget, content in (
                (self.preview_orig, snippet),
                (self.preview_frage, frage),
                (self.preview_antwort, antwort),
            ):
                widget.configure(state="normal")
                widget.delete("1.0", END)
                widget.insert(END, content)
                widget.configure(state="disabled")

        self.root.after(0, do_update)

    def segment_and_estimate(self):
        path = self.file_path.get().strip()
        if not path or not os.path.exists(path):
            ToastNotification(title=APP_TITLE, message="Bitte eine PDF-Datei waehlen.", bootstyle="danger").show_toast()
            return
        self.progress.set("Lese & segmentiere ...")
        self.root.update()

        try:
            from .pdf_ingest import extract_text_from_pdf, segment_text
            from .pipeline_models import Segment
            from pypdf import PdfReader

            txt = extract_text_from_pdf(path)
            self._full_text = txt
            segs = segment_text(txt)
            # Wandelt jeden Textabschnitt in ein Segment-Objekt um:
            self._segments = [Segment(text=s) for s in segs]
            try:
                reader = PdfReader(path)
                self._total_pages = len(reader.pages)
            except (PdfReadError, OSError):
                self._total_pages = 0
            self.logln(f"Segmentiert: {len(segs)} Segmente.")
            self.progress.set(f"Segmentierung fertig: {len(segs)} Segmente.")
            self.update_cost_label()
        except (OSError, ValueError, PdfReadError) as e:
            logger.exception("Fehler bei Segmentierung")
            ToastNotification(
                title=APP_TITLE,
                message=f"Fehler bei Segmentierung: {e.__class__.__name__}: {e}",
                bootstyle="danger",
            ).show_toast()
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
            # Wenn self._segments Segment-Objekte enthält, .text zum Zählen verwenden:
            seg_token_counts = [tok.count(s.text) for s in self._segments]
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
        except (OSError, ValueError) as e:
            logger.warning("Fehler bei Kostenschätzung: %s", e)
            self.cost_label.set(f"Fehler bei Schätzung: {e.__class__.__name__}: {e}")

    def start_pipeline(self):
        if not self._segments:
            ToastNotification(title=APP_TITLE, message="Bitte zuerst segmentieren & schaetzen.", bootstyle="info").show_toast()
            return
        if not self.api_key.get().strip():
            ToastNotification(title=APP_TITLE, message="Bitte OpenAI API-Key eingeben (wird nicht gespeichert).", bootstyle="danger").show_toast()
            return
        self._stop_flag = False
        self._pause_event.set()
        self.progress_bar.configure(value=0, maximum=len(self._segments))
        t = threading.Thread(target=self._run_pipeline_thread, daemon=True)
        t.start()

    def cancel(self):
        self._stop_flag = True
        self.progress.set("Abbruch angefordert …")

    def pause(self):
        self._pause_event.clear()
        self.progress.set("Pausiert …")

    def resume(self):
        self._pause_event.set()
        self.progress.set("Fortsetzen …")

    def on_close(self):
        self.api_key.set("")
        self.root.destroy()

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
            self.progress_bar.configure(value=0, maximum=len(self._segments))

            seg_objs = [s for s in self._segments]

            def cls_cb(i, total):
                self.progress_bar.configure(value=i, maximum=total)
                self.progress.set(f"Klassifikation {i}/{total}")

            seg_objs = pipe.classify(
                seg_objs,
                progress_cb=cls_cb,
                stop_cb=lambda: self._stop_flag,
                pause_event=self._pause_event,
            )

            filtered = [s for s in seg_objs if s.keep]
            removed = len(seg_objs) - len(filtered)
            self.logln(
                f"Gefiltert: {removed} Segmente verworfen (Ueberschrift/Gliederung/Vorwort). "
                f"{len(filtered)} verbleiben."
            )

            # Lernkarten
            self.progress.set("Erzeuge Lernkarten …")
            self.logln("Fragen/Antworten werden generiert …")
            self.progress_bar.configure(value=0, maximum=len(filtered))

            def gen_cb(i, total, card_count):
                self.progress_bar.configure(value=i, maximum=total)
                page = int((i / max(1, total)) * self._total_pages) + 1 if self._total_pages else i
                self.progress.set(
                    f"Segment {i}/{total} (Seite ~{page}) – Karten {card_count}"
                )

            def card_cb(orig, frage, antwort):
                self.update_preview(orig, frage, antwort)

            rows = pipe.generate_cards(
                filtered,
                self.questions_per_chunk.get(),
                self.language.get(),
                progress_cb=gen_cb,
                stop_cb=lambda: self._stop_flag,
                pause_event=self._pause_event,
                card_cb=card_cb,
            )

            # Export
            out_path = os.path.join(os.path.dirname(__file__), "..", "output.xlsx")
            out_path = os.path.abspath(out_path)
            pipe.export_excel(rows, out_path)
            self.progress.set(f"Fertig. Export: {out_path}")
            self.logln(f"Exportiert nach: {out_path}")
            ToastNotification(title=APP_TITLE, message=f"Fertig! Datei gespeichert:\n{out_path}", bootstyle="success").show_toast()
        except (OSError, ValueError, RuntimeError, OpenAIError) as e:
            logger.exception("Fehler in der Pipeline")
            ToastNotification(
                title=APP_TITLE,
                message=f"Fehler: {e.__class__.__name__}: {e}",
                bootstyle="danger",
            ).show_toast()
            self.progress.set("Fehler.")

def main():
    root = safe_tk()
    style = tb.Style()
    attach_theme_toggle(root, style)
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
