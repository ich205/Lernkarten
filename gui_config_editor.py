import ttkbootstrap as tb
from ttkbootstrap.toast import ToastNotification
from app.theme import make_root, attach_theme_toggle
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


cfg = load_config()

root = make_root(title="Config-Editor")
style = tb.Style()
attach_theme_toggle(root, style)

if not cfg:
    ToastNotification(
        title="Hinweis",
        message="config.toml nicht gefunden oder ungültig. Standardwerte werden verwendet.",
        bootstyle="warning",
    ).show_toast()

notebook = tb.Notebook(root)
notebook.pack(fill="both", expand=True, padx=10, pady=10)


# Modelle
models_tab = tb.Frame(notebook)
notebook.add(models_tab, text="Modelle")

label_model_var = tb.StringVar(value=cfg.get("models", {}).get("label_model", ""))
qa_model_var = tb.StringVar(value=cfg.get("models", {}).get("qa_model", ""))
use_json_var = tb.BooleanVar(value=cfg.get("models", {}).get("use_json_mode", True))
max_parallel_var = tb.IntVar(value=cfg.get("models", {}).get("max_parallel_requests", 3))

tb.Label(models_tab, text="Label-Modell").grid(row=0, column=0, sticky="w")
tb.Entry(models_tab, textvariable=label_model_var, width=20).grid(row=0, column=1, padx=5, pady=2)

tb.Label(models_tab, text="QA-Modell").grid(row=1, column=0, sticky="w")
tb.Entry(models_tab, textvariable=qa_model_var, width=20).grid(row=1, column=1, padx=5, pady=2)

tb.Checkbutton(models_tab, text="JSON-Modus", variable=use_json_var, onvalue=True, offvalue=False).grid(
    row=2, column=0, columnspan=2, sticky="w"
)

tb.Label(models_tab, text="Parallelität").grid(row=3, column=0, sticky="w")
tb.Spinbox(models_tab, from_=1, to=20, textvariable=max_parallel_var, width=5).grid(
    row=3, column=1, padx=5, pady=2, sticky="w"
)


# Preise
prices_tab = tb.Frame(notebook)
notebook.add(prices_tab, text="Preise")

cost_keys = [
    "gpt-5_input_usd_per_mtok",
    "gpt-5_cached_input_usd_per_mtok",
    "gpt-5_output_usd_per_mtok",
    "gpt-5-mini_input_usd_per_mtok",
    "gpt-5-mini_cached_input_usd_per_mtok",
    "gpt-5-mini_output_usd_per_mtok",
    "gpt-5-nano_input_usd_per_mtok",
    "gpt-5-nano_cached_input_usd_per_mtok",
    "gpt-5-nano_output_usd_per_mtok",
]
cost_vars: dict[str, tb.DoubleVar] = {}

for i, key in enumerate(cost_keys):
    tb.Label(prices_tab, text=key).grid(row=i, column=0, sticky="w")
    var = tb.DoubleVar(value=cfg.get("costs", {}).get(key, 0.0))
    tb.Entry(prices_tab, textvariable=var, width=10).grid(row=i, column=1, padx=5, pady=2, sticky="w")
    cost_vars[key] = var


# Chunking
chunk_tab = tb.Frame(notebook)
notebook.add(chunk_tab, text="Chunking")

target_var = tb.IntVar(value=cfg.get("chunking", {}).get("target_tokens", 600))
overlap_var = tb.IntVar(value=cfg.get("chunking", {}).get("overlap_tokens", 60))

tb.Label(chunk_tab, text="Chunk-Größe").grid(row=0, column=0, sticky="w")
tb.Scale(chunk_tab, from_=100, to=2000, orient="horizontal", variable=target_var).grid(row=0, column=1, padx=5)
tb.Entry(chunk_tab, textvariable=target_var, width=6).grid(row=0, column=2, padx=5)
tb.Label(chunk_tab, text="Empf.: 300-800").grid(row=0, column=3, sticky="w")

tb.Label(chunk_tab, text="Überlappung").grid(row=1, column=0, sticky="w")
tb.Scale(chunk_tab, from_=0, to=400, orient="horizontal", variable=overlap_var).grid(row=1, column=1, padx=5)
tb.Entry(chunk_tab, textvariable=overlap_var, width=6).grid(row=1, column=2, padx=5)
tb.Label(chunk_tab, text="Empf.: 40-120").grid(row=1, column=3, sticky="w")


# UI
ui_tab = tb.Frame(notebook)
notebook.add(ui_tab, text="UI")

theme_var = tb.StringVar(value=cfg.get("ui", {}).get("theme", "auto"))
tb.Label(ui_tab, text="Theme").grid(row=0, column=0, sticky="w")
tb.Combobox(ui_tab, textvariable=theme_var, values=("auto", "light", "dark"), width=10).grid(
    row=0, column=1, padx=5, pady=2, sticky="w"
)


def save() -> None:
    cfg.setdefault("models", {})
    cfg["models"]["label_model"] = label_model_var.get()
    cfg["models"]["qa_model"] = qa_model_var.get()
    cfg["models"]["use_json_mode"] = bool(use_json_var.get())
    cfg["models"]["max_parallel_requests"] = int(max_parallel_var.get())

    cfg.setdefault("costs", {})
    for key, var in cost_vars.items():
        cfg["costs"][key] = float(var.get())

    cfg.setdefault("chunking", {})
    cfg["chunking"]["target_tokens"] = int(target_var.get())
    cfg["chunking"]["overlap_tokens"] = int(overlap_var.get())

    cfg.setdefault("ui", {})
    cfg["ui"]["theme"] = theme_var.get()

    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        toml.dump(cfg, f)
    ToastNotification(
        title="Gespeichert",
        message="Konfiguration gespeichert",
        bootstyle="success",
    ).show_toast()


tb.Button(root, text="Speichern", command=save).pack(pady=10)


if __name__ == "__main__":
    root.mainloop()

