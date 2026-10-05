param([switch]$Setup, [switch]$NoBrowser)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $RepoRoot
if ($Setup -or !(Test-Path -LiteralPath ".venv\Scripts\python.exe")) { & "$PSScriptRoot\setup.ps1" }
if (!(Get-Command pnpm -ErrorAction SilentlyContinue)) { throw "pnpm is required on PATH." }
foreach ($Port in @(8000, 5174)) {
  if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw "Port $Port is already in use. Stop the existing service first." }
}
$LogRoot = Join-Path $RepoRoot "runs\logs"
New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
Start-Process -FilePath (Join-Path $RepoRoot ".venv\Scripts\python.exe") -ArgumentList "apps\api\main.py" -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LogRoot "api.stdout.log") -RedirectStandardError (Join-Path $LogRoot "api.stderr.log")
Start-Process -FilePath (Get-Command pnpm).Source -ArgumentList "--dir", "apps\web", "dev", "--host", "127.0.0.1", "--port", "5174", "--strictPort" -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LogRoot "web.stdout.log") -RedirectStandardError (Join-Path $LogRoot "web.stderr.log")
Write-Host "Development services started. Logs: runs/logs. URL: http://127.0.0.1:5174"
if (!$NoBrowser) { Start-Process "http://127.0.0.1:5174" -WindowStyle Hidden }
