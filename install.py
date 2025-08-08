import os, sys, subprocess, venv, platform

PY_MIN = (3, 10)
if sys.version_info < PY_MIN:
    print(f"[FEHLER] Python >= {PY_MIN[0]}.{PY_MIN[1]} erforderlich, gefunden: {sys.version_info.major}.{sys.version_info.minor}")
    sys.exit(1)

VENV_DIR = ".venv"
if not os.path.exists(VENV_DIR):
    print("[INFO] Erzeuge virtuelle Umgebung …")
    venv.EnvBuilder(with_pip=True).create(VENV_DIR)

python = os.path.join(VENV_DIR, "Scripts", "python.exe") if platform.system()=="Windows" else os.path.join(VENV_DIR, "bin", "python")
pip = [python, "-m", "pip"]

print("[INFO] Aktualisiere pip …")
subprocess.check_call(pip + ["install", "-U", "pip", "setuptools", "wheel"])

print("[INFO] Installiere Requirements …")
subprocess.check_call(pip + ["install", "-r", "requirements.txt"])

print("\n[OK] Installation fertig.")
print("Starten Sie die App mit:")
if platform.system()=="Windows":
    print("  run.bat")
else:
    print("  bash run.sh")
