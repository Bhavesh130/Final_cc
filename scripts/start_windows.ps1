# Build (if needed) and run the FinAlly container on Windows.
# Usage: ./scripts/start_windows.ps1 [-Build]
param([switch]$Build)

$ErrorActionPreference = "Stop"

$Image     = "finally:latest"
$Container = "finally"
$Volume    = "finally-data"
$Port      = "8000"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".env")) {
    Write-Host "No .env found - creating one from .env.example."
    Copy-Item ".env.example" ".env"
    Write-Host "  -> Edit .env and add your OPENROUTER_API_KEY, then re-run this script."
}

$existingImage = docker images -q $Image
if ($Build -or [string]::IsNullOrWhiteSpace($existingImage)) {
    Write-Host "Building image $Image ..."
    docker build -t $Image .
}

$existing = docker ps -aq -f "name=^$Container$"
if ($existing) {
    Write-Host "Removing existing container ..."
    docker rm -f $Container | Out-Null
}

Write-Host "Starting container ..."
docker run -d `
    --name $Container `
    -p "$($Port):8000" `
    -v "$($Volume):/app/db" `
    --env-file .env `
    $Image | Out-Null

$Url = "http://localhost:$Port"
Write-Host "FinAlly is running at $Url"
Start-Process $Url
