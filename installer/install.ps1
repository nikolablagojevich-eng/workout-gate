# Workout Gate - installazione (Windows, senza privilegi admin).
# Crea un venv Python 3.12, installa il pacchetto, verifica l'ambiente e
# registra l'avvio automatico al login.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File installer\install.ps1
#   powershell -ExecutionPolicy Bypass -File installer\install.ps1 -NoAutostart

param(
    [switch]$NoAutostart
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Write-Host "Workout Gate - installazione in $root" -ForegroundColor Cyan

# 1. Verifica Python 3.12.
$py = $null
try { py -3.12 --version *> $null; if ($LASTEXITCODE -eq 0) { $py = "py -3.12" } } catch {}
if (-not $py) {
    Write-Host "Python 3.12 non trovato. Installalo con:" -ForegroundColor Yellow
    Write-Host "  winget install --id Python.Python.3.12 --scope user" -ForegroundColor Yellow
    Write-Host "(MediaPipe non supporta Python 3.14; serve 3.11-3.13.)" -ForegroundColor Yellow
    exit 1
}

# 2. Crea il venv.
if (-not (Test-Path ".venv312")) {
    Write-Host "Creo il virtualenv .venv312..."
    & py -3.12 -m venv .venv312
}
$venvPy = Join-Path $root ".venv312\Scripts\python.exe"

# 3. Installa il pacchetto.
Write-Host "Installo le dipendenze (puo' richiedere qualche minuto)..."
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -e .

# 4. Diagnostica.
Write-Host "`nDiagnostica ambiente:" -ForegroundColor Cyan
& $venvPy -m workout_gate doctor

# 5. Avvio automatico + icona ON/OFF sul desktop.
if (-not $NoAutostart) {
    Write-Host "`nRegistro l'avvio automatico al login..."
    & $venvPy -m workout_gate install-autostart
}
Write-Host "Creo l'icona ON/OFF sul desktop..."
& $venvPy -m workout_gate install-desktop-icon

$venvPyw = Join-Path $root ".venv312\Scripts\pythonw.exe"
Write-Host "`nFatto." -ForegroundColor Green
Write-Host "Avvia ora (in background):  $venvPyw -m workout_gate run"
Write-Host "Prova webcam (inquadratura): $venvPy -m workout_gate test-camera"
Write-Host "Test rapido a 30s:           $venvPy -m workout_gate run --work-interval-seconds 30"
