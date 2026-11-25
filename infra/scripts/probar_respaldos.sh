#!/bin/bash
# Prueba de punta a punta de los respaldos, con PostgreSQL real en contenedores y datos inventados:
# copia cifrada → copia fuera del equipo → restauración de prueba con conteos y aislamiento (RLS).
# El «bucket» es una carpeta (rclone también copia a carpetas): no sale nada a internet.
# No toca ningún contenedor ni volumen del proyecto. Uso, desde la raíz:  bash infra/scripts/probar_respaldos.sh
set -euo pipefail
export MSYS_NO_PATHCONV=1 # Git Bash en Windows: no convertir las rutas de dentro del contenedor

raiz="$(cd "$(dirname "$0")/../.." && pwd)"
command -v cygpath > /dev/null && raiz="$(cygpath -m "$raiz")"
id="mtprueba-$$"
imagen="medtender-backup:prueba"
fallos=0

limpiar() {
    docker rm -f "$id-db" > /dev/null 2>&1 || true
    docker volume rm "$id-copias" "$id-bucket" > /dev/null 2>&1 || true
    docker network rm "$id" > /dev/null 2>&1 || true
}
trap limpiar EXIT

docker build -q -t "$imagen" "$raiz/infra/backup" > /dev/null
docker network create "$id" > /dev/null
docker run -d --name "$id-db" --network "$id" -e POSTGRES_USER=medtender -e POSTGRES_PASSWORD=prueba \
    -e POSTGRES_DB=medtender pgvector/pgvector:pg16 > /dev/null
for _ in $(seq 1 60); do
    docker exec "$id-db" psql -h 127.0.0.1 -U medtender -tAc 'select 1' medtender > /dev/null 2>&1 && break
    sleep 1
done

sql() { docker exec -i "$id-db" psql -q -v ON_ERROR_STOP=1 -U medtender -d medtender "$@"; }

# El esquema real: las migraciones de Flyway en orden.
for f in $(ls "$raiz"/api-java/src/main/resources/db/migration/V*.sql | sort -V); do
    sed 's/\${app_password}/prueba-app/g' "$f" | sql > /dev/null
done
# Flyway lleva su historial en esta tabla; aquí las migraciones se aplican con psql, así que se simula.
echo "CREATE TABLE flyway_schema_history (installed_rank int, version text, success boolean); INSERT INTO flyway_schema_history VALUES (1, 'prueba', true);" | sql
sql > /dev/null <<'SQL'
INSERT INTO tenants (id, nombre, nit) VALUES ('11111111-1111-1111-1111-111111111111', 'Cuenta inventada', 'P-1');
INSERT INTO usuarios (id, tenant_id, email, password_hash, nombre_completo, rol_global)
VALUES ('22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111', 'inventada@ejemplo.co', 'x', 'Persona Inventada', 'ADMIN_TENANT');
INSERT INTO expedientes (id, tenant_id, codigo_expediente, titulo, tipo_expediente, created_by)
VALUES ('33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', 'X-1', 'Inventado', 'AUDITORIA_CLINICA', '22222222-2222-2222-2222-222222222222');
INSERT INTO consultas (tenant_id, expediente_id, usuario_id, pregunta, respuesta, sin_evidencia, modelo_embeddings, latencia_ms)
VALUES ('11111111-1111-1111-1111-111111111111', '33333333-3333-3333-3333-333333333333', '22222222-2222-2222-2222-222222222222', 'pregunta inventada', '{}', false, 'm', 1);
SQL

en_respaldos() { # en_respaldos [opciones de docker...] -- script args
    local opciones=()
    while [ "$1" != "--" ]; do opciones+=("$1"); shift; done
    shift
    docker run --rm --network "$id" -v "$raiz/infra/backup:/scripts:ro" -v "$id-copias:/backups" -v "$id-bucket:/bucket" \
        -e PGHOST="$id-db" -e PGUSER=medtender -e PGPASSWORD=prueba -e PGDATABASE=medtender \
        -e BACKUP_PASSPHRASE=frase-de-prueba-larga "${opciones[@]}" --entrypoint bash "$imagen" "$@"
}

comprobar() { # comprobar "nombre" esperado(0|1) comando...  (con MENSAJE=..., la salida debe contenerlo)
    local nombre="$1" esperado="$2" salida estado=0
    shift 2
    salida="$("$@" 2>&1)" || estado=1
    if [ "$estado" = "$esperado" ] && { [ -z "${MENSAJE:-}" ] || grep -q "$MENSAJE" <<< "$salida"; }; then
        echo "OK     $nombre"
    else
        echo "FALLA  $nombre (salida $estado, se esperaba $esperado)"
        echo "$salida" | tail -15 | sed 's/^/         /'
        fallos=$((fallos + 1))
    fi
}

comprobar "copia cifrada y copia fuera del equipo" 0 \
    en_respaldos -e BACKUP_REMOTO=/bucket -- /scripts/backup.sh once
comprobar "al bucket solo llega lo cifrado, con su hash y sus conteos" 0 \
    en_respaldos -- -c 'ls /bucket | grep -q "\.dump\.enc$" && ls /bucket | grep -q "\.conteos$" && ! ls /bucket | grep -q "\.dump$"'
MENSAJE="nada sale sin cifrar" comprobar "sin frase de cifrado no se sube nada" 1 \
    en_respaldos -e BACKUP_REMOTO=/bucket -e BACKUP_PASSPHRASE= -- /scripts/backup.sh once
comprobar "restauración de prueba desde la copia de fuera, con conteos y RLS" 0 \
    en_respaldos -e BACKUP_REMOTO=/bucket -- /scripts/verificar-restauracion.sh
comprobar "deja constancia de que pasó" 0 \
    en_respaldos -- -c 'test -f /backups/restauracion_ok && test ! -f /backups/restauracion_fallo'

# El consentimiento promete que las copias conservan los datos hasta 14 días: fuera del equipo también.
en_respaldos -- -c 'touch -d "13 days ago 2 hours ago" /bucket/medtender-00-viejo.dump.enc /backups/medtender-00-viejo.dump.enc; touch -d "10 days ago" /bucket/medtender-00-reciente.dump.enc /backups/medtender-00-reciente.dump.enc'
sleep 1
comprobar "otra copia, que aplica la retención por defecto fuera del equipo" 0 \
    en_respaldos -e BACKUP_REMOTO=/bucket -- /scripts/backup.sh once
comprobar "ni dentro ni fuera sobrevive una copia que pasaría de 14 días antes de la próxima limpieza" 0 \
    en_respaldos -- -c 'test ! -e /bucket/medtender-00-viejo.dump.enc && test ! -e /backups/medtender-00-viejo.dump.enc && test -e /bucket/medtender-00-reciente.dump.enc && test -e /backups/medtender-00-reciente.dump.enc && rm /bucket/medtender-00-reciente.dump.enc /backups/medtender-00-reciente.dump.enc'

MENSAJE="consultas tiene 1 filas y al copiar había 999" comprobar "si los conteos no cuadran, falla" 1 \
    en_respaldos -- -c 'f=$(ls /backups/*.conteos | tail -1); sed -i "s/^consultas .*/consultas 999/" "$f"; bash /scripts/verificar-restauracion.sh'
comprobar "y deja la señal de fallo para la alerta" 0 \
    en_respaldos -- -c 'test -f /backups/restauracion_fallo'

echo "ALTER TABLE consultas DISABLE ROW LEVEL SECURITY;" | sql > /dev/null
sleep 1 # que la copia nueva tenga otra marca de tiempo
comprobar "copia de una base con el aislamiento roto" 0 en_respaldos -- /scripts/backup.sh once
MENSAJE="sin aislamiento por cuenta (RLS): consultas" comprobar "la restauración de prueba detecta el RLS roto" 1 en_respaldos -- /scripts/verificar-restauracion.sh

echo
if [ "$fallos" -eq 0 ]; then echo "Respaldos: todas las comprobaciones pasaron"; else echo "Respaldos: $fallos comprobación(es) fallaron"; fi
exit "$fallos"
