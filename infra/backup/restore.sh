#!/bin/bash
# Restaura una copia en una base de datos NUEVA y verifica su contenido. Nunca sobrescribe la
# base de producción: para recuperar de un desastre, restaure aquí y luego renombre/apunte la
# aplicación a la base restaurada.
#
# Uso: restore.sh <archivo.dump[.enc]> [base_destino]
# Variables: PGHOST PGUSER PGPASSWORD, BACKUP_PASSPHRASE (si el archivo es .enc),
#            BASE_ORIGEN (opcional): compara los conteos con esa base y falla si difieren.
set -euo pipefail

archivo="${1:?Uso: restore.sh <archivo.dump[.enc]> [base_destino]}"
destino="${2:-medtender_restore_$(date -u +%Y%m%d%H%M%S)}"
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [restore] $*"; }

[ -f "$archivo" ] || { log "ERROR: no existe $archivo"; exit 1; }

# 1. Integridad del archivo.
if [ -f "${archivo}.sha256" ]; then
    (cd "$(dirname "$archivo")" && sha256sum --check --status "$(basename "$archivo").sha256") \
        || { log "ERROR: el hash SHA-256 no coincide; la copia está dañada o fue alterada"; exit 1; }
    log "Hash SHA-256 verificado"
else
    log "AVISO: no hay archivo .sha256; no se pudo verificar la integridad"
fi

# 2. Descifrado a un temporal que se borra siempre.
trabajo="$archivo"
tmp=""
trap '[ -n "$tmp" ] && rm -f "$tmp"' EXIT
if [[ "$archivo" == *.enc ]]; then
    : "${BACKUP_PASSPHRASE:?La copia está cifrada: defina BACKUP_PASSPHRASE}"
    tmp="$(mktemp)"
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -pass env:BACKUP_PASSPHRASE \
        -in "$archivo" -out "$tmp" || { log "ERROR: no se pudo descifrar (¿clave incorrecta?)"; exit 1; }
    trabajo="$tmp"
fi

# 3. Restauración en una base nueva.
if psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${destino}'" | grep -q 1; then
    log "ERROR: la base ${destino} ya existe; elija otro nombre"
    exit 1
fi
psql -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"${destino}\""
log "Restaurando en ${destino}"
pg_restore --no-owner --exit-on-error --dbname="$destino" "$trabajo"

# 4. Verificación: tablas clave, vectores, índices y migración aplicada.
conteo() { psql -d "$1" -tAc "SELECT count(*) FROM $2"; }
# Todas las tablas del esquema público (salvo el control de migraciones), no una lista fija: así
# la verificación cubre también las tablas que añadan migraciones futuras.
tablas="$(psql -d "$destino" -tAc "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version' ORDER BY tablename")"
estado=0
log "Contenido restaurado:"
for t in $tablas; do
    n="$(conteo "$destino" "$t")"
    linea="  $t: $n"
    if [ -n "${BASE_ORIGEN:-}" ]; then
        o="$(conteo "$BASE_ORIGEN" "$t")"
        if [ "$n" != "$o" ]; then linea="$linea  (DIFERENTE: origen $o)"; estado=1; fi
    fi
    echo "$linea"
done
vectores="$(psql -d "$destino" -tAc "SELECT count(*) FROM fragmentos WHERE embedding IS NOT NULL")"
hnsw="$(psql -d "$destino" -tAc "SELECT count(*) FROM pg_indexes WHERE indexname='idx_fragmentos_embedding_hnsw'")"
version="$(psql -d "$destino" -tAc "SELECT version_num FROM alembic_version")"
echo "  fragmentos con vector: $vectores | índice HNSW: $hnsw | migración: $version"
[ "$hnsw" = "1" ] || { log "ERROR: falta el índice HNSW"; estado=1; }

# 5. Una búsqueda vectorial real prueba que pgvector y el índice funcionan tras restaurar.
if [ "$vectores" -gt 0 ]; then
    psql -d "$destino" -tAc "SELECT count(*) FROM (SELECT id FROM fragmentos WHERE embedding IS NOT NULL ORDER BY embedding <=> (SELECT embedding FROM fragmentos WHERE embedding IS NOT NULL LIMIT 1) LIMIT 5) s" \
        | grep -q '^[1-5]$' || { log "ERROR: la búsqueda vectorial falló"; estado=1; }
    log "Búsqueda vectorial de prueba: OK"
fi

if [ "$estado" -eq 0 ]; then
    log "Restauración verificada en la base ${destino}"
else
    log "Restauración COMPLETADA CON DIFERENCIAS en ${destino}"
fi
exit "$estado"
