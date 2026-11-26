#!/bin/bash
# Prueba del reenvío de errores de la web en Caddy, con servidores de eco: la recepción va a GlitchTip sin
# datos del navegador y todo lo demás de /api sigue yendo a la API. Desde la raíz: bash infra/scripts/probar_proxy_errores.sh
set -euo pipefail
export MSYS_NO_PATHCONV=1
raiz="$(cd "$(dirname "$0")/../.." && pwd)"
command -v cygpath > /dev/null && raiz="$(cygpath -m "$raiz")"
id="mtproxy-$$"
puerto=18931
fallos=0
limpiar() { docker rm -f "$id-api" "$id-gt" "$id-caddy" > /dev/null 2>&1 || true; docker network rm "$id" > /dev/null 2>&1 || true; }
trap limpiar EXIT

# Cada eco responde quién es y las cabeceras que le llegaron.
eco='
import sys, http.server
class E(http.server.BaseHTTPRequestHandler):
    def do_POST(s):
        s.rfile.read(int(s.headers.get("Content-Length", 0)))
        cuerpo = (sys.argv[1] + " " + s.path + "\n" + str(s.headers)).encode()
        s.send_response(200); s.send_header("Content-Length", str(len(cuerpo))); s.end_headers(); s.wfile.write(cuerpo)
    do_GET = do_POST
http.server.ThreadingHTTPServer(("0.0.0.0", int(sys.argv[2])), E).serve_forever()
'
docker network create "$id" > /dev/null
docker run -d --name "$id-api" --network "$id" --network-alias api python:3.12-slim python -c "$eco" SOY-LA-API 8080 > /dev/null
docker run -d --name "$id-gt" --network "$id" --network-alias glitchtip python:3.12-slim python -c "$eco" SOY-GLITCHTIP 8000 > /dev/null
arrancar_caddy() { # arrancar_caddy [opciones de docker]
    docker rm -f "$id-caddy" > /dev/null 2>&1 || true
    docker run -d --name "$id-caddy" --network "$id" -p "127.0.0.1:$puerto:80" -e DOMINIO=:80 -e ACME_EMAIL=a@prueba.local "$@" \
        -v "$raiz/frontend/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2-alpine > /dev/null
    for _ in $(seq 1 30); do curl -s "http://127.0.0.1:$puerto/" > /dev/null && return 0; sleep 1; done
    docker logs "$id-caddy" | tail -5
    return 1
}
pedir() {
    curl -s -X POST "http://127.0.0.1:$puerto$1" -d '{}' -H 'Cookie: sesion=secreta' -H 'Authorization: Bearer secreto' \
        -H 'User-Agent: NavegadorDeAna' -H 'Referer: https://sitio/expedientes/ana' -H 'Accept-Language: es-CO' -H 'Cf-Connecting-Ip: 190.1.2.3'
}
comprobar() { # comprobar "nombre" condición
    if eval "$2"; then echo "OK     $1"; else echo "FALLA  $1"; fallos=$((fallos + 1)); fi
}

arrancar_caddy -e ERRORES_UPSTREAM=glitchtip:8000
r="$(pedir /api/1/envelope/)"
comprobar "la recepción de errores va a GlitchTip" 'grep -q "^SOY-GLITCHTIP /api/1/envelope/" <<< "$r"'
comprobar "sin cookies, sesión, página, navegador, idioma ni IP" \
    '! grep -qiE "secreta|secreto|NavegadorDeAna|expedientes/ana|es-CO|190\.1\.2\.3|^X-Forwarded-For|^Cf-Connecting-Ip" <<< "$r"'
comprobar "lo demás de GlitchTip no se publica" 'pedir /api/0/organizations/ | grep -q "^SOY-LA-API"'
comprobar "la API sigue recibiendo lo suyo con su sesión" 'pedir /api/v1/auth/login | grep -q "secreto"'

robots="$(curl -s -H 'Host: medtender.ejemplo' "http://127.0.0.1:$puerto/robots.txt")"
comprobar "robots.txt protege lo privado y señala el mapa del sitio" \
    'grep -qx "Disallow: /expedientes" <<< "$robots" && grep -qx "Sitemap: https://medtender.ejemplo/sitemap.xml" <<< "$robots"'
mapa="$(curl -s -H 'Host: medtender.ejemplo' "http://127.0.0.1:$puerto/sitemap.xml")"
comprobar "el mapa del sitio es XML y solo lista páginas públicas" \
    'head -1 <<< "$mapa" | grep -q "^<?xml" && [ "$(grep -c "<loc>https://medtender.ejemplo/" <<< "$mapa")" = 4 ]'

arrancar_caddy
comprobar "sin GlitchTip configurado la recepción no llega a ningún lado" \
    '[ "$(curl -s -w "
%{http_code}" -X POST http://127.0.0.1:$puerto/api/1/envelope/ -d x | tail -1)" = 404 ]'

echo
if [ "$fallos" -eq 0 ]; then echo "Proxy de errores: todas las comprobaciones pasaron"; else echo "Proxy de errores: $fallos fallaron"; fi
exit "$fallos"
