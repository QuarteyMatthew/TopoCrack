"""
Compila DtwCore.c nella shared library corretta per la piattaforma.

Uso: Uso: python Scripts/BuildNative.py
Requisiti:
  - Windows: MSVC o GCC
  - Linux:   GCC
  - Mac:     GCC
  
Struttura di output:
  - Backend/Build/Binaries-Intermediates/  ← file oggetto intermedi (.obj, .o)
  - Backend/Build/Libraries/               ← shared library finale (.dll, .so, .dylib)
"""

import sys
import subprocess
import platform
from pathlib import Path

# ------------------ Variabili globali di utilità ------------------
# Percorsi relativi allo script: funziona indipendentemente da dove
# viene lanciato il comando, purché si sia dentro la cartella Backend/
scriptsDir = Path(__file__).resolve().parent
backendDir = scriptsDir.parent
nativeDir  = backendDir / "Source" / "Services" / "Native"
buildDir   = nativeDir / "Build"
sourceFile = nativeDir / "DtwCore.c"

# I due percorsi di output distinti che vogliamo ottenere.
intermediatesDir  = nativeDir / "Build" / "Binaries-Intermediates"
librariesDir      = nativeDir / "Build" / "Libraries"

# Creiamo entrambe le cartelle se non esistono già
intermediatesDir.mkdir(parents=True, exist_ok=True)
librariesDir.mkdir(parents=True, exist_ok=True)

print(f"Platform     : {platform.system()} ({sys.platform})")
print(f"Source       : {sourceFile}")
print(f"Intermediates: {intermediatesDir}")
print(f"Libraries    : {librariesDir}")


# ------------------ Funzioni per la compilazione ------------------
def FindMsvcVcvarsall() -> Path | None:
    vsWhere = Path("C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe")
    
    if not vsWhere.exists():
        return None
    
    Result = subprocess.run(
        [str(vsWhere), "-latest", "-property", "installationPath"],
        capture_output=True,
        text=True,
    )
    
    if Result.returncode != 0 or not Result.stdout.strip():
        return None
    
    VsInstallPath = Path(Result.stdout.strip())
    VcVarsAll = VsInstallPath / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat"

    return VcVarsAll if VcVarsAll.exists() else None

def CompileWithMsvc(vcvarsall: Path, outputFile: Path) -> bool:
    objFile = intermediatesDir / (sourceFile.stem + ".obj")
    
    compileCmd = (
        f'"{vcvarsall}" x64 && '
        f'cl /LD /O2 /MD '
        f'/Fo"{objFile}" '       # Intermedi → Binaries-Intermediates/
        f'/Fe:"{outputFile}" '  # Output    → Libraries/
        f'"{sourceFile}"'
    )

    print(f"Using MSVC via: {vcvarsall}")
    print(f"Command  : {compileCmd}")

    result = subprocess.run(
        compileCmd,
        shell=True,          # Necessario per eseguire un comando .bat con &&
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("MSVC compilation failed:")
        print(result.stdout)
        print(result.stderr)
        
        return False

    return True

def CompileWithGcc(outputFile: Path, extraFlags: list[str]) -> bool:
    objFile = intermediatesDir / (sourceFile.stem + ".o")
    compileCmd = ["gcc", "-c", "-O3"] + extraFlags + [
        "-o", str(objFile),
        str(sourceFile),
    ]

    print(f"Using gcc")
    print(f"Step 1 (compile): {' '.join(compileCmd)}")

    result = subprocess.run(compileCmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Compilation step failed:")
        print(result.stderr)
        
        return False

    # Passo 2: link del file oggetto nella shared library
    linkCmd = ["gcc", "-shared", "-o", str(outputFile), str(objFile), "-lm"]

    print(f"Step 2 (link)   : {' '.join(linkCmd)}\n")

    result = subprocess.run(linkCmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Link step failed:")
        print(result.stderr)
        
        return False

    return True

# ------------------ Logica di compilazione ------------------
if sys.platform == "win32":
    # Sistemi Windows
    outputFile = librariesDir / "DtwCore.dll"
    print(f"Output   : {outputFile}\n")
    
    vcVarsAll = FindMsvcVcvarsall()
    if vcVarsAll is not None:
        # Compila con MSVC
        success = CompileWithMsvc(vcVarsAll, outputFile)
    else:
        # Fallback e compila con GCC
        print("MSVC not found, falling back to MinGW gcc...")
        success = CompileWithGcc(outputFile, extraFlags=[])
        
    if not success:
        print("\nERROR: Build failed on Windows.")
        print("Make sure either Visual Studio or MinGW-w64 is installed.")
        print("MinGW-w64: https://www.mingw-w64.org/")
        
        sys.exit(1)  
          
elif sys.platform == "darwin":
    # Sistemi Mac
    outputFile = librariesDir / "DtwCore.dylib"
    print(f"Output   : {outputFile}\n")
    
    # Compila con GCC
    if not CompileWithGcc(outputFile, extraFlags=["-fPIC"]):
        print("\nERROR: Build failed on macOS. Run: xcode-select --install")
        
        sys.exit(1)
        
else:
    # Sistemi Linux e altri sistemi Unix-like
    outputFile = librariesDir / "DtwCore.so"
    print(f"Output   : {outputFile}\n")
    
    # Compila con GCC
    if not CompileWithGcc(outputFile, extraFlags=["-fPIC"]):
        print("\nERROR: Build failed on Linux. Run: sudo apt install gcc  (or equivalent for your distro)")
        
        sys.exit(1)
    
print(f"\nBuild successful!")
print(f"  Library      : {outputFile}")
print(f"  Intermediates: {intermediatesDir}")