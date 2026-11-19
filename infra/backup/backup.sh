#!/bin/bash
# Copias de seguridad de PostgreSQL (pg_dump formato custom) con verificación, cifrado opcional y
# retención. Los respaldos NO contienen PDFs (el sistema no los conserva), pero sí el texto
# extraído de los documentos: tratarlos como información confidencial.
#
# Modos:
#   backup.sh once   hace una copia y termina (código de salida != 0 si falla)
#   backup.sh loop   hace una copia cada INTERVALO_HORAS (por defecto 24)
#
# Variables: PGHOST PGUSER PGPASSWORD PGDATABASE, BACKUP_DIR (/backups), RETENCION_DIAS (14),
#            BACKUP_PASSPHRASE (si existe, se cifra con AES-256), INTERVALO_HORAS (24)
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENCION_DIAS="${RETENCION_DIAS:-14}"
INTERVALO_HORAS="${INTERVALO_HORAS:-24}"
PGDATABASE="${PGDATABASE:-medtender}"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [backup] $*"; }

hacer_copia() {
    local marca archivo tmp
    marca="$(date -u +%Y%m%dT%H%M%SZ)"
    archivo="${BACKUP_DIR}/medtender-${marca}.dump"
    tmp="${archivo}.parcial"
    mkdir -p "$BACKUP_DIR"

    log "Iniciando copia de ${PGDATABASE}@${PGHOST}"
    # -Fc: formato custom comprimido, permite restaurar tablas sueltas y en paralelo.
    pg_dump --format=custom --compress=6 --no-owner --file="$tmp" "$PGDATABASE"

    # Una copia que no se puede listar no sirve: se descarta antes de darla por buena.
    if ! pg_restore --list "$tmp" > /dev/null; then
        rm -f "$tmp"
        log "ERROR: la copia generada no es legible"
        return 1
    fi
    mv "$tmp" "$archivo"

    if [ -n "${BACKUP_PASSPHRASE:-}" ]; then
        openssl enc -aes-256-cbc -pbkdf2 -iter 600000 -salt \
            -pass env:BACKUP_PASSPHRASE -in "$archivo" -out "${archivo}.enc"
        rm -f "$archivo"
        archivo="${archivo}.enc"
    else
        log "AVISO: BACKUP_PASSPHRASE vacío; la copia queda SIN cifrar"
    fi

    # El hash va aparte para detectar corrupción o manipulación antes de restaurar.
    (cd "$BACKUP_DIR" && sha256sum "$(basename "$archivo")" > "$(basename "$archivo").sha256")
    local bytes
    bytes="$(stat -c %s "$archivo")"
    date -u +%s > "${BACKUP_DIR}/ultimo_ok"
    log "Copia lista: $(basename "$archivo") (${bytes} bytes)"

    # Retención: borra copias y hashes más viejos que RETENCION_DIAS.
    find "$BACKUP_DIR" -maxdepth 1 -type f -name 'medtender-*' -mtime "+${RETENCION_DIAS}" -print -delete \
        | sed 's/^/[backup] retención: borrado /' || true
}

case "${1:-once}" in
    once) hacer_copia ;;
    loop)
        while true; do
            hacer_copia || log "La copia falló; se reintentará en el próximo ciclo"
            sleep "$((INTERVALO_HORAS * 3600))"
        done
        ;;
    *) echo "Uso: $0 [once|loop]" >&2; exit 2 ;;
esac
