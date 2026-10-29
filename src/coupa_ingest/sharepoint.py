"""Descarga automática del Excel desde SharePoint / OneDrive con Microsoft Graph.

No hay intervención manual: el proceso se autentica como aplicación
(client credentials) y descarga la última versión guardada del archivo.

Requisito (lo da TI): registro de aplicación en Entra ID con permiso de
aplicación `Sites.Selected` y una concesión de lectura sobre el sitio donde
vive el archivo. Un OneDrive personal también es un sitio
(`<tenant>-my.sharepoint.com/personal/<usuario>`).
"""

from __future__ import annotations

import logging
from urllib.parse import quote

import msal
import requests

from coupa_ingest.config import SharePointConfig

log = logging.getLogger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = ["https://graph.microsoft.com/.default"]


class SharePointError(RuntimeError):
    pass


class SharePointClient:
    def __init__(self, cfg: SharePointConfig, client_secret: str) -> None:
        self.cfg = cfg
        self._app = msal.ConfidentialClientApplication(
            client_id=cfg.client_id,
            client_credential=client_secret,
            authority=f"https://login.microsoftonline.com/{cfg.tenant_id}",
        )
        self._session = requests.Session()

    def _token(self) -> str:
        result = self._app.acquire_token_for_client(scopes=SCOPE)
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
                "Revisar la concesión Sites.Selected sobre el sitio."
            )
        if resp.status_code == 404:
            raise SharePointError(f"No se encontró {what}. Revisar hostname, site_path y file_path.")
        resp.raise_for_status()
        return resp

    def _site_id(self) -> str:
        url = f"{GRAPH}/sites/{self.cfg.hostname}:{self.cfg.site_path}"
        return self._get(url, f"el sitio {self.cfg.site_path}").json()["id"]

    def get_metadata(self) -> dict:
        """Metadatos del archivo, sin descargarlo (sirve para `check --conexion`)."""
        site_id = self._site_id()
        path = quote(self.cfg.file_path)
        item = self._get(f"{GRAPH}/sites/{site_id}/drive/root:{path}", f"el archivo {self.cfg.file_path}").json()
        return {
            "site_id": site_id,
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
        url = f"{GRAPH}/sites/{meta['site_id']}/drive/items/{meta['id']}/content"
        content = self._get(url, "el contenido del archivo").content
        if meta["size"] and len(content) != meta["size"]:
            raise SharePointError(f"Descarga incompleta: {len(content)} de {meta['size']} bytes")
        return content, meta
