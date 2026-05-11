"""
Crea il virtualenv e installa le dipendenze.

Uso: python Scripts/InstallDependencies.py

Funziona su Windows, Linux e Mac senza modifiche, a patto che Python
sia già installato sul sistema (è l'unico prerequisito).
"""

import os
import sys
import subprocess
from pathlib import Path

scriptsDir      = Path(__file__).resolve().parent
backendDir      = scriptsDir.parent
venvDir         = backendDir / ".venv"
dependenciesFile = backendDir / "Dependencies.txt"

def FindPython() -> str:
    if "PYTHON_CMD" in os.environ:
        return os.environ["PYTHON_CMD"]
    
    for candidate in ["python3", "python"]:
        # subprocess.run con 'capture_output' evita che l'output di --version
        # sporchi la console. check=False perché vogliamo gestire manualmente
        # il caso in cui il comando non esiste.
        Result = subprocess.run(
            [candidate, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if Result.returncode == 0:
            return candidate
    
    print("ERROR: No Python interpreter found in PATH.")
    print("       Install Python from https://www.python.org/ oppure")
    print("       set the PYTHON_CMD environment variable.")
    
    sys.exit(1)
    
def CreateVenv(PythonCmd: str):
    if venvDir.exists():
        print(f"Virtualenv already present in '{venvDir}'.")
        return

    print(f"Creating virtualenv in '{venvDir}'...")
    subprocess.run([PythonCmd, "-m", "venv", str(venvDir)], check=True)
    print("Virtualenv successfully created.")
    
def GetVenvPython() -> Path:
    if sys.platform == "win32":
        venvPython = venvDir / "Scripts" / "python.exe"
    else:
        venvPython = VenvDir / "bin" / "python"

    if not venvPython.exists():
        print(f"ERROR: Python executable of venv not found in '{venvPython}'.")
        print("       Try deleting the.venv folder and rerunning the script.")
        sys.exit(1)

    return venvPython

def UpgradePip(venvPython: Path):
    print("Upgrade pip...")
    subprocess.run(
        [str(venvPython), "-m", "pip", "install", "--upgrade", "pip"],
        check=True,
    )


def InstallDependencies(VenvPython: Path):
    if not dependenciesFile.exists():
        print(f"No Dependencies.txt file found in '{backendDir}'.")
        print("Virtualenv ready, no dependencies installed.")
        return

    print(f"Installing dependencies from '{dependenciesFile}'...")
    subprocess.run(
        [str(VenvPython), "-m", "pip", "install", "-r", str(dependenciesFile)],
        check=True,
    )
    print("Dependencies installed successfully.")
    
pythonCmd  = FindPython()
print(f"Python Interpreter: {pythonCmd}\n")

CreateVenv(pythonCmd)
venvPython = GetVenvPython()
UpgradePip(venvPython)
InstallDependencies(venvPython)

print(f"\nSetup completed. Virtualenv ready in '{venvDir}'.")