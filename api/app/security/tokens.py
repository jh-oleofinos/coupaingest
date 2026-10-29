"""Tokens entre el servidor de Next.js y esta API.

El navegador nunca habla con la API. El servidor de Next.js firma, en cada llamada, un
JWT HS256 de vida corta con el secreto compartido API_TOKEN_SECRET:

- typ="servicio": para login y para resolver un usuario de Entra ID (aún no hay usuario).
- typ="usuario", sub=<id>, vs=<versión de sesión>: para todo lo demás. Si vs no coincide
  con la base (el usuario cerró sesión o se le cambió la contraseña), se rechaza.
  La API vuelve a leer al usuario y sus permisos de la base en cada petición;
  el token no transporta permisos.
"""

from dataclasses import dataclass
from typing import Literal

import jwt

from app.config import Settings

TIPOS = ("servicio", "usuario")


class TokenInvalido(Exception):
    pass


@dataclass(frozen=True)
class Claims:
    tipo: Literal["servicio", "usuario"]
    usuario_id: int | None
    version_sesion: int | None = None


def validar(token: str, settings: Settings) -> Claims:
    if settings.API_TOKEN_SECRET is None:
        raise TokenInvalido("API sin secreto configurado.")
    try:
        datos = jwt.decode(
            token,
            settings.API_TOKEN_SECRET.get_secret_value(),
            algorithms=["HS256"],
            audience=settings.API_TOKEN_AUDIENCE,
            issuer=settings.API_TOKEN_ISSUER,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "typ"]},
            leeway=10,
        )
    except jwt.PyJWTError as e:
        raise TokenInvalido(str(e)) from e

    if datos["exp"] - datos["iat"] > settings.API_TOKEN_MAX_SEGUNDOS:
        raise TokenInvalido("Vida del token mayor a la permitida.")

    tipo = datos["typ"]
    if tipo not in TIPOS:
        raise TokenInvalido("Tipo de token desconocido.")
    if tipo == "usuario":
        try:
            return Claims(
                tipo="usuario", usuario_id=int(datos["sub"]), version_sesion=int(datos["vs"])
            )
        except (KeyError, TypeError, ValueError) as e:
            raise TokenInvalido("sub o vs inválidos.") from e
    return Claims(tipo="servicio", usuario_id=None)
