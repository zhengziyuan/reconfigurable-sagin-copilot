$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (!(Test-Path $Python)) {
  throw "Virtual environment not found. Run scripts/setup.ps1 first."
}

Set-Location $RepoRoot

& $Python -m rsagin_core.cli validate --config configs\scenarios\demo_low_altitude_emergency.yaml
& $Python -m rsagin_core.cli simulate --config configs\scenarios\demo_low_altitude_emergency.yaml --out runs\baseline
& $Python -m rsagin_core.cli optimize --config configs\scenarios\demo_low_altitude_emergency.yaml --out runs\optimized

Write-Host "Demo artifacts written to runs\baseline and runs\optimized."

