"""Descarga automática del Excel desde SharePoint / OneDrive con Microsoft Graph.

Dos formas de autenticarse (sharepoint.auth):

- "usuario": con una cuenta de Microsoft 365 que ya puede abrir el archivo.
  Se inicia sesión UNA vez con `coupa-ingest login` (código en el navegador);
  el token se guarda cifrado (DPAPI, por usuario de Windows) y se renueva solo
  en cada corrida. No requiere que TI registre una aplicación.
- "app": registro de aplicación en Entra ID con `Sites.Selected` y client
  secret (lo da TI). Es la opción definitiva; no depende de una persona.

El archivo se ubica por su enlace (sharepoint.file_url) o por ruta dentro del
OneDrive/sitio (sharepoint.file_path).
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from urllib.parse import quote

import msal
import requests

from coupa_ingest.config import SharePointConfig

log = logging.getLogger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"
APP_SCOPE = ["https://graph.microsoft.com/.default"]
USER_SCOPE = ["Files.Read.All"]


class SharePointError(RuntimeError):
    pass


def share_token(url: str) -> str:
    """Convierte un enlace de SharePoint/OneDrive al id que usa /shares de Graph."""
    b64 = base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii").rstrip("=")
    return f"u!{b64}"


def _token_cache(path: Path):
    from msal_extensions import PersistedTokenCache, build_encrypted_persistence

    path.parent.mkdir(parents=True, exist_ok=True)
    return PersistedTokenCache(build_encrypted_persistence(str(path)))


class SharePointClient:
    def __init__(self, cfg: SharePointConfig, client_secret: str | None = None,
                 token_cache: Path | None = None) -> None:
        self.cfg = cfg
        authority = f"https://login.microsoftonline.com/{cfg.tenant_id}"
        if cfg.auth == "app":
            if not client_secret:
                raise SharePointError("auth = 'app' requiere graph_client_secret")
            self._app = msal.ConfidentialClientApplication(
                client_id=cfg.client_id, client_credential=client_secret, authority=authority
            )
        else:
            if token_cache is None:
                raise SharePointError("auth = 'usuario' requiere la ruta del token")
            self._app = msal.PublicClientApplication(
                client_id=cfg.client_id, authority=authority, token_cache=_token_cache(token_cache)
            )
        self._session = requests.Session()

    # --- autenticación ----------------------------------------------------
    def login(self) -> str:
        """Inicio de sesión interactivo (solo auth = 'usuario'). Devuelve la cuenta."""
        flow = self._app.initiate_device_flow(scopes=USER_SCOPE)
        if "user_code" not in flow:
            raise SharePointError(f"No se pudo iniciar sesión: {flow.get('error_description')}")
        print(flow["message"], flush=True)
        result = self._app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise SharePointError(f"Inicio de sesión fallido: {result.get('error_description')}")
        return (result.get("id_token_claims") or {}).get("preferred_username", "?")

    def _token(self) -> str:
        if self.cfg.auth == "app":
            result = self._app.acquire_token_for_client(scopes=APP_SCOPE)
        else:
            accounts = self._app.get_accounts()
            result = self._app.acquire_token_silent(USER_SCOPE, account=accounts[0]) if accounts else None
            if not result:
                raise SharePointError(
                    "No hay sesión de Microsoft guardada o venció. Ejecuta: coupa-ingest login "
                    "(con el mismo usuario de Windows que corre la tarea)."
                )
        if "access_token" not in result:
            # No se loguea el resultado completo: puede traer detalles sensibles
            raise SharePointError(f"No se obtuvo token de Graph: {result.get('error')}")
        return result["access_token"]

    def _get(self, url: str, what: str) -> requests.Response:
        headers = {"Authorization": f"Bearer {self._token()}"}
        resp = self._session.get(url, headers=headers, timeout=self.cfg.timeout_s)
        if resp.status_code in (401, 403):
            raise SharePointError(
                f"Sin permiso para leer {what} ({resp.status_code}). "
                "Revisar que la cuenta (o la app) tenga acceso al archivo."
            )
        if resp.status_code == 404:
            raise SharePointError(f"No se encontró {what}. Revisar file_url o site_path/file_path.")
        resp.raise_for_status()
        return resp

    # --- archivo ----------------------------------------------------------
    def _item(self) -> dict:
        if self.cfg.file_url:
            url = f"{GRAPH}/shares/{share_token(self.cfg.file_url)}/driveItem"
            return self._get(url, "el archivo del enlace").json()
        site = self._get(f"{GRAPH}/sites/{self.cfg.hostname}:{self.cfg.site_path}",
                         f"el sitio {self.cfg.site_path}").json()
        path = quote(self.cfg.file_path)
        return self._get(f"{GRAPH}/sites/{site['id']}/drive/root:{path}",
                         f"el archivo {self.cfg.file_path}").json()

    def get_metadata(self) -> dict:
        """Metadatos del archivo, sin descargarlo (sirve para `check --conexion`)."""
        item = self._item()
        return {
            "drive_id": (item.get("parentReference") or {}).get("driveId"),
            "id": item.get("id"),
            "name": item.get("name"),
            "eTag": item.get("eTag"),
            "lastModifiedDateTime": item.get("lastModifiedDateTime"),
            "lastModifiedBy": (item.get("lastModifiedBy") or {}).get("user", {}).get("displayName"),
            "size": item.get("size"),
        }

    def download_file(self) -> tuple[bytes, dict]:
        """Devuelve (contenido, metadatos) de la última versión guardada."""
        meta = self.get_metadata()
        log.info(
            "Descargando %s (%s bytes, modificado %s)", meta["name"], meta["size"], meta["lastModifiedDateTime"]
        )
        url = f"{GRAPH}/drives/{meta['drive_id']}/items/{meta['id']}/content"
        content = self._get(url, "el contenido del archivo").content
        if meta["size"] and len(content) != meta["size"]:
            raise SharePointError(f"Descarga incompleta: {len(content)} de {meta['size']} bytes")
        return content, meta


def client_from_settings(settings) -> SharePointClient:
    """Arma el cliente según sharepoint.auth (el secreto solo se pide en modo 'app')."""
    from coupa_ingest import secrets

    cfg = settings.sharepoint
    if cfg.auth == "app":
        return SharePointClient(cfg, secrets.get_secret(secrets.GRAPH_CLIENT_SECRET, settings.ambiente))
    return SharePointClient(cfg, token_cache=settings.token_cache)
