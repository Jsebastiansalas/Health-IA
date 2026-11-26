"""Hash de contraseñas, solo para la CLI de alta de organizaciones.

La autenticación de usuarios (login, JWT) vive en la API Java; este servicio no emite ni valida
tokens de usuario. Los hashes bcrypt ($2b$) son intercambiables entre ambos.
"""

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
