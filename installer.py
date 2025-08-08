import os
import zipfile
import subprocess
import sys
import platform
import stat

ZIP_NAME = "Lernkarten.zip"
EXTRACT_DIR = "Lernkarten"


def ensure_extracted():
    if os.path.isdir(EXTRACT_DIR):
        print("[INFO] Archiv bereits entpackt.")
        return
    if not os.path.exists(ZIP_NAME):
        print(f"[FEHLER] {ZIP_NAME} nicht gefunden.")
        sys.exit(1)
    print("[INFO] Entpacke Archiv …")
    with zipfile.ZipFile(ZIP_NAME, "r") as zf:
        zf.extractall(EXTRACT_DIR)


def run_install():
    install_path = os.path.join(EXTRACT_DIR, "install.py")
    if not os.path.exists(install_path):
        print("[FEHLER] install.py nicht gefunden im entpackten Verzeichnis.")
        sys.exit(1)
    subprocess.check_call([sys.executable, install_path])


def create_start_scripts():
    base_dir = EXTRACT_DIR
    start_py = f"""#!/usr/bin/env python3
import os, subprocess, platform
BASE = os.path.join(os.path.dirname(__file__), {base_dir!r})
if platform.system() == 'Windows':
    subprocess.check_call(['cmd', '/c', os.path.join(BASE, 'run.bat')])
else:
    subprocess.check_call(['bash', os.path.join(BASE, 'run.sh')])
"""
    with open("start.py", "w", encoding="utf-8") as fh:
        fh.write(start_py)
    os.chmod("start.py", stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
                             stat.S_IRGRP | stat.S_IXGRP |
                             stat.S_IROTH | stat.S_IXOTH)

    if platform.system() == "Windows":
        with open("start.bat", "w", encoding="utf-8") as fh:
            fh.write("@echo off\r\n")
            fh.write(f"cd {base_dir}\r\n")
            fh.write("call run.bat\r\n")
        print("\n[OK] Installation fertig. Starten Sie das Programm mit start.bat")
    else:
        with open("start.sh", "w", encoding="utf-8") as fh:
            fh.write("#!/usr/bin/env bash\n")
            fh.write(f"cd '{base_dir}'\n")
            fh.write("bash run.sh\n")
        os.chmod("start.sh", stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
                             stat.S_IRGRP | stat.S_IXGRP |
                             stat.S_IROTH | stat.S_IXOTH)
        print("\n[OK] Installation fertig. Starten Sie das Programm mit ./start.sh oder python start.py")


def main():
    ensure_extracted()
    run_install()
    create_start_scripts()


if __name__ == "__main__":
    main()
