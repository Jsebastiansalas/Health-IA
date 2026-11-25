#!/bin/bash
# Pruebas en navegador de la aplicación completa, aislada. Desde la raíz:  bash infra/scripts/e2e.sh
#   CANAL=msedge  usa el Edge o Chrome ya instalado (sin descargar navegadores); sin CANAL usa el de Playwright.
#   DEJAR=1       no destruye la aplicación al terminar (para depurar).
set -euo pipefail
raiz="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$raiz"

export INTERNAL_TOKEN="token-interno-solo-para-pruebas-e2e-0123456789"
export JWT_SECRET="secreto-solo-para-pruebas-e2e-0123456789-abcdefghij"
export DATOS_CLAVE="Y2xhdmUtZGUtcHJ1ZWJhcy1kZS0zMi1ieXRlcy1vayE=" # la misma de las pruebas unitarias
export MT_PG_PORT=15434 MT_REDIS_PORT=16380 MT_CLAMAV_PORT=13310 MT_API_PORT=18010 MT_AGENTE_PORT=18012 MT_WEB_PORT=18088
export POSTGRES_PASSWORD=medtender APP_DB_PASSWORD=medtender_app
# El proyecto se fija además aquí: ningún mandato de este script puede tocar la beta («medtender»).
compose() { docker compose -p medtender-e2e -f "$raiz/infra/docker-compose.yml" -f "$raiz/infra/docker-compose.e2e.yml" "$@"; }

creado_env=""
[ -f agente/.env ] || { : > agente/.env && creado_env=1; }
terminar() {
    local estado=$?
    cd "$raiz" # las pruebas corren desde e2e/
    [ "$estado" -eq 0 ] || compose logs --tail 40 api agente worker 2> /dev/null | tail -60
    if [ -z "${DEJAR:-}" ] && ! compose down -v --remove-orphans > /dev/null 2>&1; then
        echo "AVISO: no se pudo destruir la aplicación de prueba: docker compose -p medtender-e2e down -v" >&2
        estado=1
    fi
    [ -z "$creado_env" ] || rm -f "$raiz/agente/.env"
    exit "$estado"
}
trap terminar EXIT

compose down -v --remove-orphans > /dev/null 2>&1 || true
compose up -d --build --wait --wait-timeout 600 postgres redis api agente web ia-falsa worker

cd e2e
[ -d node_modules ] || npm ci --no-audit --no-fund
npx playwright test "$@"
