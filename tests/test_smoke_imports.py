import importlib

CANDIDATES = [
    "app.main",
    "app.gui",
    "gui_config_editor",
    "config_editor",
]


def test_import_any_entrypoint() -> None:
    ok = False
    for mod in CANDIDATES:
        try:
            importlib.import_module(mod)
            ok = True
            break
        except Exception:
            pass
    assert ok, f"Keines der Module importierbar: {CANDIDATES}"
