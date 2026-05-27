param(
    [string]$Python = "python",
    [string]$VenvDir = ".venv",
    [switch]$NoRun
)

$ErrorActionPreference = "Stop"

Write-Host ">> Using Python: $Python"
Write-Host ">> Creating virtual environment at: $VenvDir"
& $Python -m venv $VenvDir

$activate = Join-Path $VenvDir "Scripts\Activate.ps1"
if (-not (Test-Path $activate)) {
    throw "Virtual environment activation script not found: $activate"
}

. $activate

Write-Host ">> Upgrading pip/setuptools/wheel"
python -m pip install --upgrade pip setuptools wheel

Write-Host ">> Installing pinned dependencies"
pip install -r requirements.txt

Write-Host ">> Setup complete."
Write-Host ">> To activate later: .\$VenvDir\Scripts\Activate.ps1"

if (-not $NoRun) {
    Write-Host ">> Launching app..."
    python main.py
}
else {
    Write-Host ">> Skipping run (-NoRun provided)."
}
