# Esegue lint, type check e test nel venv 3.12.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$venvPy = Join-Path $root ".venv312\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { $venvPy = "python" }

Write-Host "=== Ruff ===" -ForegroundColor Cyan
& $venvPy -m ruff check .
Write-Host "=== Mypy ===" -ForegroundColor Cyan
& $venvPy -m mypy
Write-Host "=== Pytest ===" -ForegroundColor Cyan
& $venvPy -m pytest
