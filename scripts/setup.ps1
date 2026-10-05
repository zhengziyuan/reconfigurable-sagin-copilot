$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = "python"
$Pnpm = "pnpm"
foreach ($Tool in @("python", "node", "pnpm")) {
  if (!(Get-Command $Tool -ErrorAction SilentlyContinue)) { throw "$Tool is required on PATH. See README.md for prerequisites." }
}

Set-Location $RepoRoot

if (!(Test-Path ".venv")) {
  & $Python -m venv .venv
  if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment." }
}

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }
& $VenvPython -m pip install -e ".\packages\rsagin-core[test]" -e .\apps\api
if ($LASTEXITCODE -ne 0) {
  Write-Host "Default PyPI install failed; retrying with Tsinghua mirror."
  & $VenvPython -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e ".\packages\rsagin-core[test]" -e .\apps\api
  if ($LASTEXITCODE -ne 0) { throw "Failed to install Python dependencies." }
}
& $Pnpm install --frozen-lockfile
if ($LASTEXITCODE -ne 0) { throw "Failed to install web dependencies." }

Write-Host "Setup complete."
