"""Descarga del Excel desde SharePoint con Microsoft Graph.

Autenticación: registro de aplicación en Entra ID con permiso de aplicación
`Sites.Selected`, autorizado solo sobre el sitio del archivo (lo otorga TI).
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


class SharePointClient:
    def __init__(self, cfg: SharePointConfig, client_secret: str, timeout_s: int = 120) -> None:
        self.cfg = cfg
        self.timeout_s = timeout_s
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
            raise RuntimeError(f"No se obtuvo token de Graph: {result.get('error')}")
        return result["access_token"]

    def _get(self, url: str, **kwargs) -> requests.Response:
        headers = {"Authorization": f"Bearer {self._token()}"}
        resp = self._session.get(url, headers=headers, timeout=self.timeout_s, **kwargs)
        resp.raise_for_status()
        return resp

    def _site_id(self) -> str:
        url = f"{GRAPH}/sites/{self.cfg.hostname}:{self.cfg.site_path}"
        return self._get(url).json()["id"]

    def download_file(self) -> tuple[bytes, dict]:
        """Devuelve (contenido, metadatos) del archivo configurado."""
        site_id = self._site_id()
        path = quote(self.cfg.file_path)
        item = self._get(f"{GRAPH}/sites/{site_id}/drive/root:{path}").json()
        meta = {
            "name": item.get("name"),
            "id": item.get("id"),
            "eTag": item.get("eTag"),
            "lastModifiedDateTime": item.get("lastModifiedDateTime"),
            "lastModifiedBy": (item.get("lastModifiedBy") or {}).get("user", {}).get("displayName"),
            "size": item.get("size"),
        }
        log.info("Descargando %s (modificado %s)", meta["name"], meta["lastModifiedDateTime"])
        content = self._get(f"{GRAPH}/sites/{site_id}/drive/items/{item['id']}/content").content
        return content, meta
