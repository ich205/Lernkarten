import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap import ttk
from ttkbootstrap.toast import ToastNotification
from pathlib import Path
import toml

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.toml"


def load_config() -> dict:
    """Load configuration from `config.toml` if available."""
    try:
        return toml.load(CONFIG_PATH)
    except (FileNotFoundError, toml.TomlDecodeError):
        return {}

class ConfigEditor(tb.Window):
    def __init__(self) -> None:
        super().__init__()
        self.title("Konfiguration")
        self.minsize(120, 120)

        # Gear icon button without external image
        gear_button = ttk.Button(self, text="\u2699\ufe0f", command=self.open_editor, width=3)
        gear_button.pack(expand=True)

    def open_editor(self) -> None:
        cfg = load_config()
        if not cfg:
            ToastNotification(
                title="Hinweis",
                message="config.toml nicht gefunden oder ungültig. Standardwerte werden verwendet.",
                bootstyle="warning",
            ).show_toast()

        top = tb.Toplevel(self)
        top.title("Einstellungen")

        # Chunking target_tokens
        ttk.Label(top, text="Chunk-Größe").grid(row=0, column=0, sticky="w")
        target_var = tk.IntVar(value=cfg.get("chunking", {}).get("target_tokens", 600))
        target_scale = ttk.Scale(top, from_=100, to=2000, orient="horizontal", variable=target_var)
        target_scale.grid(row=0, column=1, padx=5)
        target_entry = ttk.Entry(top, textvariable=target_var, width=6)
        target_entry.grid(row=0, column=2, padx=5)
        ttk.Label(top, text="Empf.: 300-800").grid(row=0, column=3, sticky="w")

        # Chunking overlap_tokens
        ttk.Label(top, text="Überlappung").grid(row=1, column=0, sticky="w")
        overlap_var = tk.IntVar(value=cfg.get("chunking", {}).get("overlap_tokens", 60))
        overlap_scale = ttk.Scale(top, from_=0, to=400, orient="horizontal", variable=overlap_var)
        overlap_scale.grid(row=1, column=1, padx=5)
        overlap_entry = ttk.Entry(top, textvariable=overlap_var, width=6)
        overlap_entry.grid(row=1, column=2, padx=5)
        ttk.Label(top, text="Empf.: 40-120").grid(row=1, column=3, sticky="w")

        # Prompting max_questions_per_chunk_default
        ttk.Label(top, text="Fragen/Chunk").grid(row=2, column=0, sticky="w")
        q_var = tk.IntVar(value=cfg.get("prompting", {}).get("max_questions_per_chunk_default", 8))
        q_spin = ttk.Spinbox(top, from_=1, to=20, textvariable=q_var, width=5)
        q_spin.grid(row=2, column=1, padx=5)
        ttk.Label(top, text="Empf.: 4-10").grid(row=2, column=3, sticky="w")

        def save() -> None:
            cfg.setdefault("chunking", {})["target_tokens"] = int(target_var.get())
            cfg["chunking"]["overlap_tokens"] = int(overlap_var.get())
            cfg.setdefault("prompting", {})["max_questions_per_chunk_default"] = int(q_var.get())

            with CONFIG_PATH.open("w", encoding="utf-8") as f:
                toml.dump(cfg, f)
            ToastNotification(title="Gespeichert", message="Konfiguration gespeichert", bootstyle="success").show_toast()
            top.destroy()

        save_button = ttk.Button(top, text="Speichern", command=save)
        save_button.grid(row=3, column=0, columnspan=4, pady=10)

if __name__ == "__main__":
    ConfigEditor().mainloop()
