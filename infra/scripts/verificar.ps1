<#
.SYNOPSIS
  Ejecuta todas las verificaciones del proyecto y se detiene en la primera que falle.
.DESCRIPTION
  Requiere Docker en ejecucion (Testcontainers). Uso:  powershell -File infra/scripts/verificar.ps1
  Parametro -Rapido omite las pruebas de integracion de Java (las mas lentas, ~6 min).
#>
param([switch]$Rapido)

$ErrorActionPreference = "Stop"
$raiz = Resolve-Path (Join-Path $PSScriptRoot "..\..")

function Paso($nombre, [scriptblock]$accion) {
    Write-Host "`n=== $nombre ===" -ForegroundColor Cyan
    & $accion
    if ($LASTEXITCODE -ne 0) { Write-Host "FALLO: $nombre" -ForegroundColor Red; exit 1 }
}

Paso "Compose de produccion: solo Caddy publica puertos" {
    $env:POSTGRES_PASSWORD = "x"; $env:APP_DB_PASSWORD = "x"; $env:REDIS_PASSWORD = "x"
    $env:JWT_SECRET = "x"; $env:INTERNAL_TOKEN = "x"; $env:METRICS_TOKEN = "x"
    $env:DOMINIO = "x.co"; $env:ACME_EMAIL = "a@b.co"; $env:BACKUP_PASSPHRASE = "x"
    $json = docker compose -f "$raiz\infra\docker-compose.prod.yml" config --format json | ConvertFrom-Json
    $expuestos = $json.services.PSObject.Properties | Where-Object { $_.Value.ports } | ForEach-Object { $_.Name }
    if ($expuestos -ne "caddy") { Write-Host "Servicios con puertos publicados: $expuestos"; $global:LASTEXITCODE = 1 } else { $global:LASTEXITCODE = 0 }
}

Paso "Python: ruff" { Push-Location "$raiz\agente"; uv run ruff check .; Pop-Location }
Paso "Python: pytest" { Push-Location "$raiz\agente"; uv run python -m pytest -q; Pop-Location }
Paso "Frontend: tsc" { Push-Location "$raiz\frontend"; npx tsc --noEmit -p .; Pop-Location }
Paso "Frontend: vitest" { Push-Location "$raiz\frontend"; npm test; Pop-Location }
if ($Rapido) {
    Paso "Java: compilacion" { Push-Location "$raiz\api-java"; mvn -q -o compile; Pop-Location }
} else {
    Paso "Java: mvn test" { Push-Location "$raiz\api-java"; mvn -q test; Pop-Location }
}

Write-Host "`nTodo en orden." -ForegroundColor Green
