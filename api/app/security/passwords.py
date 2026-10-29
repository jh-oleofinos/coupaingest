"""Contraseñas con Argon2id (parámetros por defecto de argon2-cffi, recomendados por OWASP)."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

# Hash de una contraseña aleatoria que nadie conoce. Se verifica contra él cuando el
# usuario no existe, para que la respuesta tarde lo mismo y no revele qué correos existen.
_HASH_SEÑUELO = _hasher.hash("señuelo-no-es-una-contraseña-real-7f3a9c")

LONGITUD_MINIMA = 12
LONGITUD_MAXIMA = 128


def validar_politica(contrasena: str, correo: str) -> list[str]:
    errores: list[str] = []
    if len(contrasena) < LONGITUD_MINIMA:
        errores.append(f"Debe tener al menos {LONGITUD_MINIMA} caracteres.")
    if len(contrasena) > LONGITUD_MAXIMA:
        errores.append(f"Debe tener como máximo {LONGITUD_MAXIMA} caracteres.")
    usuario = correo.split("@", 1)[0].lower()
    if usuario and usuario in contrasena.lower():
        errores.append("No debe contener el nombre de usuario.")
    return errores


def generar_hash(contrasena: str) -> str:
    return _hasher.hash(contrasena)


def verificar(hash_guardado: str | None, contrasena: str) -> bool:
    try:
        return _hasher.verify(hash_guardado or _HASH_SEÑUELO, contrasena) and bool(hash_guardado)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def requiere_rehash(hash_guardado: str) -> bool:
    return _hasher.check_needs_rehash(hash_guardado)
