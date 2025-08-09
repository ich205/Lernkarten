import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import toml

CONFIG_PATH = Path(__file__).resolve().parent / "config.toml"

class ConfigEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Konfiguration")
        self.geometry("120x120")

        # Gear icon button
        gear_button = ttk.Button(self, text="\u2699\ufe0f", command=self.open_editor, width=3)
        gear_button.pack(expand=True)

    def open_editor(self) -> None:
        try:
            cfg = toml.load(CONFIG_PATH)
        except (FileNotFoundError, toml.TomlDecodeError):
            cfg = {}
            messagebox.showwarning(
                "Warnung",
                "Konfiguration konnte nicht geladen werden. Es wird eine leere Konfiguration verwendet.",
            )

        top = tk.Toplevel(self)
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
            messagebox.showinfo("Gespeichert", "Konfiguration gespeichert")
            top.destroy()

        save_button = ttk.Button(top, text="Speichern", command=save)
        save_button.grid(row=3, column=0, columnspan=4, pady=10)

if __name__ == "__main__":
    ConfigEditor().mainloop()
