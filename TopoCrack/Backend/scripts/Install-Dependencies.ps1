$ErrorActionPreference = "Stop"
$grandParent = Split-Path $PSScriptRoot -Parent
$venvDir = Join-Path $grandParent ".venv"

$pythonCmd = $env:PYTHON_CMD
if (-not $pythonCmd)
{
    if (Get-Command python3 -ErrorAction SilentlyContinue) { $pythonCmd = "python3" }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $pythonCmd = "python" }
    else { Write-Error "Nessun interprete Python trovato."; exit 1 }
}

if (-not (Test-Path $venvDir))
{
    Write-Output "Creazione virtualenv in $venvDir..."
    & $pythonCmd -m venv $venvDir
}
else
{
    Write-Output "Virtualenv $venvDir gia' presente."
}

$activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
if (Test-Path $activateScript)
{
    & $activateScript
} 
else
{
    Write-Error "Attivazione non trovata: $activateScript"
    exit 1
}

if (Test-Path "$grandParent\Dependencies.txt") {
    Write-Output "Upgrade di pip..."
    python -m pip install --upgrade pip
    Write-Output "Installazione da Dependencies.txt..."
    pip install -r $grandParent\Dependencies.txt
    exit 0
}

Write-Output "Nessun file di dipendenze trovato. Virtualenv pronto in $venvDir."
