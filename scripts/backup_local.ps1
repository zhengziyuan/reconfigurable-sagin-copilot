param(
  [string]$Source = "runs",
  [string]$Destination = "runs\backups"
)

$ErrorActionPreference = "Stop"
$sourcePath = Resolve-Path $Source
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$zipPath = Join-Path $Destination "rsagin_backup_$timestamp.zip"

Compress-Archive -Path (Join-Path $sourcePath "*") -DestinationPath $zipPath -Force
Write-Output "Backup written to $zipPath"
