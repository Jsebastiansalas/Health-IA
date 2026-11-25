"""Token de acceso de Google Cloud para Vertex AI, sin la librería google-auth.

Dos orígenes, en este orden:
1. **Archivo de cuenta de servicio** (`VERTEX_CREDENCIALES`, el JSON que descarga la consola): se
   firma un JWT con su clave privada (RS256) y se cambia por un token en `token_uri`. La clave
   nunca sale del servidor; solo viaja el JWT firmado.
2. **Servidor de metadatos** de la máquina, si el agente corre dentro de Google Cloud (Compute
   Engine, Cloud Run) con una cuenta de servicio asignada.

El token dura una hora; se guarda y se renueva un minuto antes de vencer.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import jwt

ALCANCE = "https://www.googleapis.com/auth/cloud-platform"
_METADATOS = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
)
_MARGEN_S = 60


def vertex_url(proyecto: str, region: str, modelo: str, metodo: str) -> str:
    """URL de un modelo de Google en Vertex AI. «global» no lleva la región en el host."""
    host = "aiplatform.googleapis.com"
    if region != "global":
        host = f"{region}-{host}"
    return (
        f"https://{host}/v1/projects/{proyecto}/locations/{region}"
        f"/publishers/google/models/{modelo}:{metodo}"
    )


class ErrorCredencial(Exception):
    pass


@dataclass
class CredencialGoogle:
    ruta: str = ""  # JSON de la cuenta de servicio; vacío = servidor de metadatos
    timeout_s: float = 10.0
    _token: str = ""
    _vence: float = 0.0
    _cerrojo: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def token(self) -> str:
        if self._token and time.time() < self._vence - _MARGEN_S:
            return self._token
        async with self._cerrojo:
            if self._token and time.time() < self._vence - _MARGEN_S:
                return self._token
            token, dura = await (self._de_cuenta() if self.ruta else self._de_metadatos())
            self._token, self._vence = token, time.time() + dura
            return token

    def _cuenta(self) -> dict:
        try:
            datos = json.loads(Path(self.ruta).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ErrorCredencial(
                f"No se pudo leer VERTEX_CREDENCIALES: {type(exc).__name__}"
            ) from None
        faltan = [k for k in ("client_email", "private_key", "token_uri") if not datos.get(k)]
        if datos.get("type") != "service_account" or faltan:
            raise ErrorCredencial("VERTEX_CREDENCIALES no es una clave de cuenta de servicio")
        return datos

    async def _de_cuenta(self) -> tuple[str, float]:
        cuenta = self._cuenta()
        ahora = int(time.time())
        afirmacion = jwt.encode(
            {
                "iss": cuenta["client_email"],
                "scope": ALCANCE,
                "aud": cuenta["token_uri"],
                "iat": ahora,
                "exp": ahora + 3600,
            },
            cuenta["private_key"],
            algorithm="RS256",
            headers={"kid": cuenta.get("private_key_id", "")},
        )
        return await self._pedir(
            "post",
            cuenta["token_uri"],
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": afirmacion,
            },
        )

    async def _de_metadatos(self) -> tuple[str, float]:
        return await self._pedir("get", _METADATOS, headers={"Metadata-Flavor": "Google"})

    async def _pedir(self, metodo: str, url: str, **kwargs) -> tuple[str, float]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as cliente:
                r = await getattr(cliente, metodo)(url, **kwargs)
        except httpx.TransportError as exc:
            origen = "cuenta de servicio" if self.ruta else "servidor de metadatos"
            raise ErrorCredencial(f"Sin token de Google ({origen}): {type(exc).__name__}") from exc
        if r.status_code != 200:
            # El cuerpo de error de Google no contiene la clave; se recorta igual.
            raise ErrorCredencial(
                f"Google rechazó la credencial: HTTP {r.status_code} {r.text[:200]}"
            )
        datos = r.json()
        return datos["access_token"], float(datos.get("expires_in", 3600))


_credenciales: dict[str, CredencialGoogle] = {}


def credencial_para(ruta: str) -> CredencialGoogle:
    """Una sola credencial (y un solo token en caché) por archivo, compartida entre el modelo
    generativo y los embeddings."""
    if ruta not in _credenciales:
        _credenciales[ruta] = CredencialGoogle(ruta)
    return _credenciales[ruta]
