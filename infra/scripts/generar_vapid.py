"""Genera el par de claves VAPID de las notificaciones push. Imprime las líneas para infra/.env.

Uso, desde agente/ (usa su dependencia `cryptography`):  uv run python ../infra/scripts/generar_vapid.py
"""

import base64

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def main() -> None:
    clave = ec.generate_private_key(ec.SECP256R1())
    publica = clave.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    print(f"PUSH_CLAVE_PUBLICA={b64(publica)}")
    print(f"PUSH_CLAVE_PRIVADA={b64(clave.private_numbers().private_value.to_bytes(32, 'big'))}")


if __name__ == "__main__":
    main()
