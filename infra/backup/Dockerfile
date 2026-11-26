# Respaldos: las herramientas de PostgreSQL de la misma versión que la base, y rclone (del repositorio de
# Debian) para la copia fuera del equipo. Los scripts se montan desde infra/backup.
FROM pgvector/pgvector:pg16

# Parches de seguridad del sistema y fuera `gosu` (un binario de Go con vulnerabilidades que solo usa el arranque
# del servidor PostgreSQL, que este contenedor no usa; verificar-restauracion.sh usa `runuser`).
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends rclone ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/local/bin/gosu
