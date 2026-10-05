param([switch]$NoBrowser, [switch]$Stop)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $RepoRoot
if (!(Get-Command docker -ErrorAction SilentlyContinue)) { throw "Install and start Docker Desktop first: https://www.docker.com/products/docker-desktop/" }
& docker compose version
if ($LASTEXITCODE -ne 0) { throw "Docker Compose v2 is required." }
if ($Stop) { & docker compose down; exit $LASTEXITCODE }
& docker compose up -d --build --wait --wait-timeout 180
if ($LASTEXITCODE -ne 0) { & docker compose logs --tail 60; throw "Deployment failed. See the service logs above." }
$WebAddress = (& docker compose port web 80 | Select-Object -First 1).Trim()
if ($LASTEXITCODE -ne 0 -or !$WebAddress) { throw "Could not determine the published web address." }
$Url = "http://$WebAddress"
$Health = Invoke-RestMethod "$Url/health" -TimeoutSec 10
if ($Health.status -ne "ok") { throw "The application health check failed." }
Write-Host "Reconfigurable SAGIN Copilot $($Health.version) is ready: $Url"
if (!$NoBrowser) { Start-Process $Url -WindowStyle Hidden }
