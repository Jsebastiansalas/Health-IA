#!/bin/bash
# Restauración de prueba: demuestra que la última copia sirve. La restaura en un PostgreSQL desechable que
# arranca dentro de ESTE contenedor (nunca toca el servidor de la base) y comprueba:
#   1. la integridad y el descifrado (restore.sh),
#   2. que cada tabla tiene exactamente las filas que había al copiar,
#   3. que el aislamiento entre cuentas (RLS) viaja en la copia y funciona.
# Con BACKUP_REMOTO baja la copia de fuera del equipo, así también se prueba esa.
#
# Deja /backups/restauracion_ok (fecha) o /backups/restauracion_fallo, que pone el contenedor en «unhealthy».
# Uso: verificar-restauracion.sh   (en modo loop, backup.sh lo ejecuta cada RESTAURACION_INTERVALO_DIAS)
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [verificar] $*"; }

trabajo="$(mktemp -d)"
datos="${trabajo}/pg"
terminar() {
    local estado=$?
    [ -f "${datos}/postmaster.pid" ] && gosu postgres pg_ctl -D "$datos" -m immediate stop > /dev/null 2>&1 || true
    rm -rf "$trabajo"
    if [ "$estado" -eq 0 ]; then
        date -u +%s > "${BACKUP_DIR}/restauracion_ok"
        rm -f "${BACKUP_DIR}/restauracion_fallo"
        log "La última copia se restaura bien y conserva el aislamiento entre cuentas"
    else
        date -u +%s > "${BACKUP_DIR}/restauracion_fallo"
        log "ERROR: la restauración de prueba FALLÓ"
    fi
}
trap terminar EXIT

# 1. La copia más reciente: la de fuera si la hay.
if [ -n "${BACKUP_REMOTO:-}" ]; then
    nombre="$(rclone lsf "$BACKUP_REMOTO" --files-only --include 'medtender-*.dump.enc' | sort | tail -1)"
    [ -n "$nombre" ] || { log "ERROR: no hay copias en el destino remoto"; exit 1; }
    mkdir -p "${trabajo}/copia"
    rclone copy "$BACKUP_REMOTO" "${trabajo}/copia" --include "${nombre}*"
    copia="${trabajo}/copia/${nombre}"
    log "Probando la copia de fuera del equipo: ${nombre}"
else
    copia="$(find "$BACKUP_DIR" -maxdepth 1 -type f \( -name 'medtender-*.dump' -o -name 'medtender-*.dump.enc' \) | sort | tail -1)"
    [ -n "$copia" ] || { log "ERROR: no hay copias en ${BACKUP_DIR}"; exit 1; }
    log "Probando la copia local: $(basename "$copia")"
fi
[ -f "${copia}.conteos" ] || { log "ERROR: la copia no trae sus conteos"; exit 1; }

# 2. Un servidor desechable, sin red: solo un socket dentro del directorio temporal.
chown postgres "$trabajo"
gosu postgres initdb -D "$datos" -U medtender --auth=trust --encoding=UTF8 > /dev/null
gosu postgres pg_ctl -D "$datos" -w -o "-c listen_addresses='' -k ${trabajo}" -l "${trabajo}/pg.log" start > /dev/null
export PGHOST="$trabajo" PGUSER=medtender PGPORT=5432
unset PGPASSWORD
# El rol de la aplicación no viaja en la copia de una base; sin él no se restauran sus permisos.
psql -d postgres -qc 'CREATE ROLE medtender_app NOLOGIN'

# 3. Restaurar y exigir los conteos.
CONTEOS="${copia}.conteos" BASE_ORIGEN="" bash "$(dirname "$0")/restore.sh" "$copia" medtender_prueba

# 4. Aislamiento: toda tabla con datos de una cuenta tiene RLS con su política...
sin_rls="$(psql -d medtender_prueba -qtAc "
    SELECT string_agg(c.relname, ', ' ORDER BY c.relname)
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'r'
      AND (c.relname = 'tenants' OR EXISTS (SELECT 1 FROM pg_attribute a
           WHERE a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped))
      AND (NOT c.relrowsecurity OR NOT EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid))")"
if [ -n "$sin_rls" ]; then
    log "ERROR: sin aislamiento por cuenta (RLS): ${sin_rls}"
    exit 1
fi
# ... y de verdad filtra: la aplicación, sin identificar ninguna cuenta, no ve una sola fila.
for t in tenants usuarios expedientes fragmentos consultas; do
    visibles="$(psql -d medtender_prueba -qtAc "SET ROLE medtender_app; SELECT count(*) FROM ${t}")"
    if [ "$visibles" != "0" ]; then
        log "ERROR: sin identificar una cuenta, la aplicación ve ${visibles} filas de ${t}"
        exit 1
    fi
done
log "Aislamiento por cuenta comprobado"
