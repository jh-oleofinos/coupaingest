"""Secretos del proceso.

Orden de búsqueda:
  1. variable de entorno (GRAPH_CLIENT_SECRET, COUPA_API_KEY)
  2. archivo .env en la raíz del repo (está en .gitignore; nunca se versiona)
  3. Administrador de credenciales de Windows (keyring), cargado con
     `coupa-ingest secrets set <nombre>`
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path

import keyring

SERVICE = "coupa-ingest"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# Nombres de secretos que usa el proceso
GRAPH_CLIENT_SECRET = "graph_client_secret"
COUPA_API_KEY = "coupa_api_key"
KNOWN = (GRAPH_CLIENT_SECRET, COUPA_API_KEY)


class MissingSecretError(RuntimeError):
    pass


def _username(name: str, ambiente: str) -> str:
    return f"{ambiente}:{name}"


def read_env_file(path: Path = ENV_FILE) -> dict[str, str]:
    """Lee líneas NOMBRE=valor; ignora vacías y comentarios (#)."""
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_secret(name: str, ambiente: str) -> str:
    var = name.upper()
    value = os.environ.get(var) or read_env_file().get(var)
    if not value:
        value = keyring.get_password(SERVICE, _username(name, ambiente))
    if not value:
        raise MissingSecretError(
            f"Falta el secreto '{name}' ({ambiente}). "
            f"Ponlo en .env como {var}=... o cárgalo con: coupa-ingest secrets set {name}"
        )
    return value


def set_secret_interactive(name: str, ambiente: str) -> None:
    if name not in KNOWN:
        raise ValueError(f"Secreto desconocido: {name}. Válidos: {', '.join(KNOWN)}")
    value = getpass.getpass(f"Valor para {name} ({ambiente}): ")
    if not value:
        raise ValueError("Valor vacío; no se guardó nada.")
    keyring.set_password(SERVICE, _username(name, ambiente), value)
