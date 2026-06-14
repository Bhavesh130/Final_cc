# Stop and remove the FinAlly container (data volume is preserved).
$ErrorActionPreference = "Stop"
$Container = "finally"

$existing = docker ps -aq -f "name=^$Container$"
if ($existing) {
    docker rm -f $Container | Out-Null
    Write-Host "Stopped and removed container '$Container'. Data volume 'finally-data' kept."
} else {
    Write-Host "No container named '$Container' is running."
}
