# Workout Gate - disinstallazione.
# Rimuove l'avvio automatico. Con -Purge cancella anche i dati locali
# (statistiche, configurazione) dopo conferma.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File installer\uninstall.ps1
#   powershell -ExecutionPolicy Bypass -File installer\uninstall.ps1 -Purge

param(
    [switch]$Purge
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venvPy = Join-Path $root ".venv312\Scripts\python.exe"
if (Test-Path $venvPy) {
    Write-Host "Rimuovo l'avvio automatico..."
    & $venvPy -m workout_gate remove-autostart
} else {
    Write-Host "Venv non trovato, salto la rimozione autostart." -ForegroundColor Yellow
}

$dataDir = Join-Path $env:LOCALAPPDATA "WorkoutGate"
if ($Purge) {
    if (Test-Path $dataDir) {
        $reply = Read-Host "Cancellare TUTTI i dati locali (statistiche, config) in $dataDir? [y/N]"
        if ($reply -match '^(y|s|si|yes)$') {
            Remove-Item -Recurse -Force $dataDir
            Write-Host "Dati locali eliminati."
        } else {
            Write-Host "Dati conservati."
        }
    }
} else {
    Write-Host "Statistiche e configurazione conservate in: $dataDir"
    Write-Host "(Usa -Purge per cancellarle.)"
}

Write-Host "`nPer rimuovere completamente il codice elimina la cartella del progetto e .venv312." -ForegroundColor Green
