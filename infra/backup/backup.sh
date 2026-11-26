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
#            BACKUP_REMOTO (destino de rclone, p. ej. remoto:bucket/medtender; vacío: sin copia fuera),
#            BACKUP_REMOTO_RETENCION_DIAS (14, lo que promete el consentimiento), RESTAURACION_INTERVALO_DIAS (30; solo en modo loop)
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENCION_DIAS="${RETENCION_DIAS:-14}"
INTERVALO_HORAS="${INTERVALO_HORAS:-24}"
PGDATABASE="${PGDATABASE:-medtender}"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [backup] $*"; }
# shellcheck source=estado.sh
source "$(dirname "$0")/estado.sh"

# pg_dump y el conteo de filas ven la misma foto de la base: así la restauración de prueba puede
# exigir los conteos exactos aunque la aplicación siga escribiendo mientras se copia.
volcar_con_conteos() { # volcar_con_conteos <archivo> <archivo_de_conteos>
    local foto linea estado=0
    coproc SESION { psql -qtAX -v ON_ERROR_STOP=1 -d "$PGDATABASE"; }
    local lee="${SESION[0]}" escribe="${SESION[1]}" pid="$SESION_PID"
    echo "BEGIN ISOLATION LEVEL REPEATABLE READ; SELECT pg_export_snapshot();" >&"$escribe"
    read -r -t 60 foto <&"$lee" || { log "ERROR: no se pudo abrir la foto de la base"; return 1; }
    # -Fc: formato custom comprimido, permite restaurar tablas sueltas y en paralelo.
    pg_dump --format=custom --compress=6 --no-owner --snapshot="$foto" --file="$1" "$PGDATABASE" || estado=1
    cat >&"$escribe" <<'SQL'
SELECT format('%s %s', tablename, (xpath('/row/c/text()',
           query_to_xml(format('SELECT count(*) AS c FROM public.%I', tablename), false, true, '')))[1]::text)
FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'flyway_schema_history' ORDER BY tablename;
SELECT '__fin__';
SQL
    : > "$2"
    while read -r -t 300 linea <&"$lee"; do
        [ "$linea" = "__fin__" ] && break
        echo "$linea" >> "$2"
    done
    [ "$linea" = "__fin__" ] || estado=1
    echo "COMMIT;" >&"$escribe"
    echo '\q' >&"$escribe"
    wait "$pid" || estado=1
    return "$estado"
}

# Copia fuera del equipo: solo lo cifrado (con su hash y sus conteos, que no llevan contenido).
subir_fuera() { # subir_fuera <archivo>
    [ -n "${BACKUP_REMOTO:-}" ] || return 0
    local nombre
    nombre="$(basename "$1")"
    rclone copy "$BACKUP_DIR" "$BACKUP_REMOTO" --include "${nombre}*" \
        && rclone check "$BACKUP_DIR" "$BACKUP_REMOTO" --one-way --include "${nombre}*" \
        || { log "ERROR: la copia fuera del equipo falló"; return 1; }
    date -u +%s > "${BACKUP_DIR}/remoto_ok"
    log "Copia fuera del equipo lista y comprobada"
    rclone delete "$BACKUP_REMOTO" --min-age "$((${BACKUP_REMOTO_RETENCION_DIAS:-14} - 1))d" --include 'medtender-*' --b2-hard-delete \
        || log "AVISO: no se pudo aplicar la retención en el destino remoto"
}

toca_verificar() {
    local ultima
    ultima="$(cat "${BACKUP_DIR}/restauracion_ok" 2> /dev/null || echo 0)"
    [ -f "${BACKUP_DIR}/restauracion_fallo" ] \
        || [ $(($(date -u +%s) - ultima)) -ge $((${RESTAURACION_INTERVALO_DIAS:-30} * 86400)) ]
}

hacer_copia() {
    local marca archivo tmp
    marca="$(date -u +%Y%m%dT%H%M%SZ)"
    archivo="${BACKUP_DIR}/medtender-${marca}.dump"
    tmp="${archivo}.parcial"
    mkdir -p "$BACKUP_DIR"
    if [ -n "${BACKUP_REMOTO:-}" ] && [ -z "${BACKUP_PASSPHRASE:-}" ]; then
        log "ERROR: con BACKUP_REMOTO hace falta BACKUP_PASSPHRASE; nada sale sin cifrar"
        return 1
    fi

    log "Iniciando copia de ${PGDATABASE}@${PGHOST}"
    if ! volcar_con_conteos "$tmp" "${tmp}.conteos"; then
        rm -f "$tmp" "${tmp}.conteos"
        log "ERROR: no se pudo copiar la base"
        return 1
    fi

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

    mv "${tmp}.conteos" "${archivo}.conteos"

    # El hash va aparte para detectar corrupción o manipulación antes de restaurar.
    (cd "$BACKUP_DIR" && sha256sum "$(basename "$archivo")" > "$(basename "$archivo").sha256")
    local bytes
    bytes="$(stat -c %s "$archivo")"
    date -u +%s > "${BACKUP_DIR}/ultimo_ok"
    log "Copia lista: $(basename "$archivo") (${bytes} bytes)"

    # Retención: RETENCION_DIAS es el máximo que vive una copia. La limpieza es diaria, así que se borra ya lo
    # que lo superaría antes de la siguiente.
    find "$BACKUP_DIR" -maxdepth 1 -type f -name 'medtender-*' -mmin "+$(((RETENCION_DIAS - 1) * 1440))" -print -delete \
        | sed 's/^/[backup] retención: borrado /' || true

    subir_fuera "$archivo"
}

case "${1:-once}" in
    once)
        trap publicar_estado EXIT
        hacer_copia
        ;;
    loop)
        while true; do
            # En un proceso aparte: llamar aquí a la función con «||» apagaría `set -e` dentro de ella, y un paso
            # fallido (p. ej. el cifrado) dejaría la copia anotada como correcta.
            bash "$0" once || log "La copia falló; se reintentará en el próximo ciclo"
            if toca_verificar; then
                bash "$(dirname "$0")/verificar-restauracion.sh" \
                    || log "ERROR: la restauración de prueba falló; revisa el registro"
            fi
            publicar_estado
            sleep "$((INTERVALO_HORAS * 3600))"
        done
        ;;
    *) echo "Uso: $0 [once|loop]" >&2; exit 2 ;;
esac
