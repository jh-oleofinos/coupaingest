"""Secretos en el Administrador de credenciales de Windows (vía keyring).

Nunca se leen de archivos ni de variables en texto plano. Se capturan una vez
en consola con `coupa-ingest secrets set <nombre>` usando la cuenta de servicio
que corre la tarea programada (las credenciales son por usuario de Windows).
"""

from __future__ import annotations

import getpass

import keyring

SERVICE = "coupa-ingest"

# Nombres de secretos que usa el proceso
GRAPH_CLIENT_SECRET = "graph_client_secret"
COUPA_API_KEY = "coupa_api_key"
KNOWN = (GRAPH_CLIENT_SECRET, COUPA_API_KEY)


class MissingSecretError(RuntimeError):
    pass


def _username(name: str, ambiente: str) -> str:
    return f"{ambiente}:{name}"


def get_secret(name: str, ambiente: str) -> str:
    value = keyring.get_password(SERVICE, _username(name, ambiente))
    if not value:
        raise MissingSecretError(
            f"Falta el secreto '{name}' ({ambiente}). "
            f"Cárgalo con: coupa-ingest secrets set {name}"
        )
    return value


def set_secret_interactive(name: str, ambiente: str) -> None:
    if name not in KNOWN:
        raise ValueError(f"Secreto desconocido: {name}. Válidos: {', '.join(KNOWN)}")
    value = getpass.getpass(f"Valor para {name} ({ambiente}): ")
    if not value:
        raise ValueError("Valor vacío; no se guardó nada.")
    keyring.set_password(SERVICE, _username(name, ambiente), value)
