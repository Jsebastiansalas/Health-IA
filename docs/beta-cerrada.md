# Beta cerrada desde tu PC con Cloudflare Tunnel

Para que unas pocas personas que conoces usen MedTender **sin pagar servidor ni dominio**. Tu PC corre todo (los datos quedan en tu casa) y Cloudflare solo le presta una dirección pública con HTTPS.

> **Antes de invitar a alguien:** que haya aceptado el consentimiento (la aplicación se lo pide sola), que entienda que es una **prueba** y qué proveedor de IA recibe el texto: el consentimiento lo dice según lo que esté configurado en `agente/.env`. Con la API gratuita de Gemini (lo normal en la beta), Google puede usar lo que se le envía; con Vertex AI no. Invita solo a quien conozcas.

## Lo que necesitas
- MedTender corriendo en Docker (`docker compose -f infra/docker-compose.yml up -d`).
- Brevo configurado (para que lleguen los correos de confirmación) y `infra/.env` completo.
- El PC **encendido, conectado y sin dormirse** mientras haya gente usándolo (Configuración → Sistema → Energía: «Suspender: nunca» mientras dure la prueba).

## 1. Instalar cloudflared (una sola vez)
En PowerShell:
```powershell
winget install --id Cloudflare.cloudflared
```
Cierra y vuelve a abrir PowerShell. Comprueba:
```powershell
cloudflared --version
```

## 2. Abrir el túnel
```powershell
cloudflared tunnel --url http://localhost:8088
```
Tras unos segundos imprime una dirección como `https://algo-aleatorio.trycloudflare.com`. **Esa es la dirección pública.** Deja esa ventana abierta: si la cierras, el túnel se cae. No necesitas cuenta de Cloudflare para esto.

> **La dirección cambia cada vez que abres el túnel.** Para una dirección fija necesitas un dominio propio y una cuenta gratuita de Cloudflare (túnel con nombre). Para empezar no hace falta.

## 3. Decirle a MedTender cuál es su dirección
Los enlaces de los correos de confirmación usan esa dirección. En `infra/.env` cambia:
```
CORREO_BASE_URL=https://algo-aleatorio.trycloudflare.com
CONFIAR_PROXY=true
CORREO_VERIFICACION_OBLIGATORIA=true
```
Y reinicia solo la API:
```powershell
docker compose -f infra/docker-compose.yml up -d api
```
(`CONFIAR_PROXY=true` hace que los límites de intentos se apliquen a cada visitante y no a todos juntos. La configuración de Caddy ya lee la IP real que manda Cloudflare.)

## 4. Probar tú primero
1. Abre la dirección pública desde **tu teléfono con datos móviles** (no desde tu Wi-Fi): así compruebas que funciona desde afuera.
2. Regístrate con un correo tuyo, confirma el correo desde el mensaje, acepta el consentimiento y sube un documento inventado.
3. Si todo funciona, comparte la dirección **solo por mensaje privado** a quien quieras invitar.

## 5. Mientras dure la prueba
- **El registro está abierto** para cualquiera que tenga la dirección. Si la compartes en un grupo grande, entra gente que no conoces. Cuando tus invitados ya estén registrados, ciérralo poniendo `REGISTRO_PERSONAL_ABIERTO=false` en `infra/.env` y reiniciando la API.
- **Límites que ya tienes:** 5 registros por hora por visitante, 20 consultas por minuto por usuario, y los correos solo se activan con el enlace.
- **Respaldo:** antes de cada sesión larga haz una copia de la base: `docker exec medtender-postgres-1 pg_dump -U medtender -Fc medtender > "$HOME\medtender-respaldos\copia.dump"`.
- **Cuenta de prueba eliminada:** pide a cada invitado que, al terminar, use «Eliminar mi cuenta».

## 6. Apagar
`Ctrl + C` en la ventana del túnel. La dirección deja de existir de inmediato; los datos siguen en tu PC.

## Qué no cubre esto
- **No es producción:** sin dominio propio, sin garantías de disponibilidad (el túnel «rápido» de Cloudflare no promete estar siempre) y con tu PC como único servidor.
- **Seguridad del PC:** estás exponiendo un servicio desde tu casa. Mantén Windows y Docker actualizados y no abras otros puertos en tu router (con el túnel no hace falta abrir ninguno).
- **Lo legal sigue pendiente:** esta guía no sustituye la revisión del abogado (`docs/revision-legal.md`).

## Si algo falla
| Síntoma | Qué mirar |
|---|---|
| La dirección pública no abre | ¿Sigue abierta la ventana de `cloudflared`? ¿Está corriendo Docker (`docker ps`)? |
| El enlace del correo lleva a `localhost` | `CORREO_BASE_URL` no tiene la dirección nueva, o no reiniciaste la API. |
| «Demasiadas solicitudes» para todos | `CONFIAR_PROXY` está en `false`: todos los visitantes cuentan como uno. |
| No llegan correos | `docker logs medtender-api-1 2>&1 \| Select-String correo` y el panel de Brevo → Transaccional → Logs. |
| Las respuestas tardan o dan «servicio de IA no disponible» | Google a veces sobrecarga el modelo gratuito; reintenta en un minuto. |

## Usar Gemini en Google Cloud (Vertex) en lugar de la API gratuita

1. Crea en Google Cloud el proyecto con facturación, habilita la API `aiplatform.googleapis.com`, crea una cuenta de servicio con el rol «Agent Platform User» y descarga su clave JSON fuera del repositorio. El crédito de prueba de Google no paga Gemini para cuentas creadas desde el 16-nov-2026: se cobra desde la primera llamada.
2. En `infra/.env` añade `VERTEX_PROYECTO` y `VERTEX_CREDENCIALES_ARCHIVO` (ruta de la clave, con `/`).
3. Pon un tope en `agente/.env`: `IA_TOPE_DIARIO_USD=2`.
4. Levanta con los dos archivos: `docker compose -f infra/docker-compose.yml -f infra/docker-compose.vertex.yml up -d --build`.
5. El consentimiento cambia solo: cada invitado lo acepta de nuevo.

Para volver a la API gratuita, repite el paso 4 sin el segundo `-f`.
