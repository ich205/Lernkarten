import os
import sys
import subprocess
import venv
import platform
import zipfile
import stat
import re

from app.logging_utils import get_logger

logger = get_logger(__name__)

PY_MIN = (3, 10)
HERE = os.path.abspath(os.path.dirname(__file__))
ZIP_NAME = "Lernkarten.zip"
EXTRACT_DIR = "Lernkarten"


def ensure_python():
    if sys.version_info < PY_MIN:
        logger.error(
            "Python >= %s.%s erforderlich, gefunden: %s.%s",
            PY_MIN[0],
            PY_MIN[1],
            sys.version_info.major,
            sys.version_info.minor,
        )
        sys.exit(1)


def ensure_extracted():
    zip_path = os.path.join(HERE, ZIP_NAME)
    extract_path = os.path.join(HERE, EXTRACT_DIR)
    if os.path.exists(zip_path):
        if os.path.isdir(extract_path):
            logger.info("Archiv bereits entpackt.")
        else:
            logger.info("Entpacke Archiv …")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_path)
        return extract_path
    return HERE


def packages_installed(pip_cmd, requirements):
    for req in requirements:
        name = re.split(r"[<>=!\[]", req, 1)[0]
        result = subprocess.run(
            pip_cmd + ["show", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            return False
    return True


def install_requirements(base_dir):
    venv_dir = os.path.join(base_dir, ".venv")
    if not os.path.exists(venv_dir):
        logger.info("Erzeuge virtuelle Umgebung …")
        venv.EnvBuilder(with_pip=True).create(venv_dir)

    python = (
        os.path.join(venv_dir, "Scripts", "python.exe")
        if platform.system() == "Windows"
        else os.path.join(venv_dir, "bin", "python")
    )
    pip_cmd = [python, "-m", "pip"]

    basics = ["pip", "setuptools", "wheel"]
    if packages_installed(pip_cmd, basics):
        logger.info("Grundlegende Pakete bereits installiert.")
    else:
        logger.info("Aktualisiere pip …")
        subprocess.check_call(pip_cmd + ["install", "-U"] + basics)

    req_file = os.path.join(base_dir, "installer", "requirements.txt")
    with open(req_file, encoding="utf-8") as fh:
        reqs = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

    if packages_installed(pip_cmd, reqs):
        logger.info("Requirements bereits installiert.")
    else:
        logger.info("Installiere Requirements …")
        subprocess.check_call(pip_cmd + ["install", "-r", req_file])

    return venv_dir


def create_start_scripts(base_dir):
    if base_dir == HERE:
        return

    start_py = f"""#!/usr/bin/env python3
import os, subprocess, platform
BASE = os.path.join(os.path.dirname(__file__), {EXTRACT_DIR!r})
if platform.system() == 'Windows':
    subprocess.check_call(['cmd', '/c', os.path.join(BASE, 'run.bat')])
else:
    subprocess.check_call(['bash', os.path.join(BASE, 'run.sh')])
"""
    with open(os.path.join(HERE, "start.py"), "w", encoding="utf-8") as fh:
        fh.write(start_py)
    os.chmod(
        os.path.join(HERE, "start.py"),
        stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
        | stat.S_IRGRP | stat.S_IXGRP
        | stat.S_IROTH | stat.S_IXOTH,
    )

    if platform.system() == "Windows":
        with open(os.path.join(HERE, "start.bat"), "w", encoding="utf-8") as fh:
            fh.write("@echo off\r\n")
            fh.write(f"cd {EXTRACT_DIR}\r\n")
            fh.write("call run.bat\r\n")
        logger.info("Installation fertig. Starten Sie das Programm mit start.bat")
    else:
        with open(os.path.join(HERE, "start.sh"), "w", encoding="utf-8") as fh:
            fh.write("#!/usr/bin/env bash\n")
            fh.write(f"cd '{EXTRACT_DIR}'\n")
            fh.write("bash run.sh\n")
        os.chmod(
            os.path.join(HERE, "start.sh"),
            stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
            | stat.S_IRGRP | stat.S_IXGRP
            | stat.S_IROTH | stat.S_IXOTH,
        )
        logger.info("Installation fertig. Starten Sie das Programm mit ./start.sh oder python start.py")


def main():
    ensure_python()
    base = ensure_extracted()
    install_requirements(base)
    create_start_scripts(base)
    if base == HERE:
        logger.info("Installation fertig.")
        logger.info("Starten Sie die App mit:")
        if platform.system() == "Windows":
            logger.info("  run.bat")
        else:
            logger.info("  bash run.sh")


if __name__ == "__main__":
    main()
