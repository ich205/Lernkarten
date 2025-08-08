import os, sys, subprocess, venv, platform

PY_MIN = (3, 10)
if sys.version_info < PY_MIN:
    print(
        f"[FEHLER] Python >= {PY_MIN[0]}.{PY_MIN[1]} erforderlich, gefunden: {sys.version_info.major}.{sys.version_info.minor}"
    )
    sys.exit(1)

VENV_DIR = ".venv"
if not os.path.exists(VENV_DIR):
    print("[INFO] Erzeuge virtuelle Umgebung …")
    venv.EnvBuilder(with_pip=True).create(VENV_DIR)

python = (
    os.path.join(VENV_DIR, "Scripts", "python.exe")
    if platform.system() == "Windows"
    else os.path.join(VENV_DIR, "bin", "python")
)
pip = [python, "-m", "pip"]


def packages_installed(requirements):
    try:
        import pkg_resources

        pkg_resources.require(requirements)
        return True
    except Exception:
        return False


basics = ["pip", "setuptools", "wheel"]
if packages_installed(basics):
    print("[INFO] Grundlegende Pakete bereits installiert.")
else:
    print("[INFO] Aktualisiere pip …")
    subprocess.check_call(pip + ["install", "-U"] + basics)

with open("requirements.txt") as fh:
    reqs = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

if packages_installed(reqs):
    print("[INFO] Requirements bereits installiert.")
else:
    print("[INFO] Installiere Requirements …")
    subprocess.check_call(pip + ["install", "-r", "requirements.txt"])

print("\n[OK] Installation fertig.")
print("Starten Sie die App mit:")
if platform.system() == "Windows":
    print("  run.bat")
else:
    print("  bash run.sh")
