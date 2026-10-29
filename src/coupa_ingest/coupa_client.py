"""Cliente de la Import Session API de llama.ai (Coupa Supply Chain Design).

Flujo según "LLAPI Ingest Examples.pdf" (lo mandó Coupa):
  1. POST /v4/import/session            {"fileId": <modelId>}  -> sessionId
  2. PUT  /v4/import/session/{sid}/table/{tabla}/record   arreglo JSON -> 202 + Location
  3. GET  <host><Location>              true = el lote terminó (no dice si salió bien)
  4. PUT  /v4/import/session/{sid}/close
  5. GET  /v4/import/session/{sid}      resumen: exitosos y con error
     GET  /v4/import/session/{sid}/status?pageSize&pageIndex
     GET  /v4/import/session/{sid}/error?pageSize&pageIndex

SUPUESTOS (el PDF no muestra las respuestas): el campo donde viene el sessionId,
los nombres de los campos del resumen y la forma de las páginas. Están aislados
en _session_id_from, SUMMARY_KEYS y page_items.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from coupa_ingest.config import CoupaConfig
from coupa_ingest.control import now_iso

log = logging.getLogger(__name__)

ENDPOINTS = {
    "models": "/v3/model",
    "open_session": "/v4/import/session",
    "put_records": "/v4/import/session/{session_id}/table/{table}/record",
    "close_session": "/v4/import/session/{session_id}/close",
    "summary": "/v4/import/session/{session_id}",
    "status": "/v4/import/session/{session_id}/status",
    "errors": "/v4/import/session/{session_id}/error",
}
PAGE_SIZE = 1000
MAX_PAGES = 500
# 429 y 503 = Coupa no procesó la petición: es seguro esperar y repetir.
RETRY_STATUS = (429, 503)

# SUPUESTO: posibles nombres de los totales en el resumen (se comparan sin
# mayúsculas, guiones ni guiones bajos).
SUMMARY_KEYS = {
    "success": ("successcount", "totalsuccess", "successfulrecords", "success",
                "succeeded", "recordssucceeded", "upserted", "upsertedcount"),
    "errors": ("errorcount", "totalerrors", "errorrecords", "errors", "failed",
               "failedcount", "recordsfailed"),
}


class CoupaError(RuntimeError):
    pass


@dataclass
class BatchResult:
    """Registro de un lote: lo que se envió y cómo terminó."""

    table: str
    n: int
    rows: int
    http_status: int | None = None
    location: str | None = None
    operation_id: str | None = None
    sent_at: str | None = None
    finished_at: str | None = None
    seconds: float | None = None
    polls: int = 0
    status: str = "pending"        # pending | terminado | timeout
    detail: dict = field(default_factory=dict)


def _norm(key: str) -> str:
    return key.lower().replace("_", "").replace("-", "")


def _json(resp: requests.Response):
    """Lee JSON sin caerse si Coupa responde texto o XML."""
    try:
        return resp.json()
    except ValueError:
        return resp.text


def _session_id_from(body) -> str | None:
    """SUPUESTO: el sessionId llega como texto suelto o en un campo id/sessionId."""
    if isinstance(body, str | int):
        return str(body).strip().strip('"') or None
    if isinstance(body, dict):
        by_key = {_norm(k): v for k, v in body.items()}
        for k in ("sessionid", "id", "importsessionid"):
            if by_key.get(k):
                return str(by_key[k])
    return None


def page_items(body) -> list:
    """SUPUESTO: una página es una lista o un objeto con una lista adentro."""
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for v in body.values():
            if isinstance(v, list):
                return v
    return []


def summary_totals(summary) -> tuple[int | None, int | None]:
    """(exitosos, con error) del resumen; None si no se reconoce el campo."""
    found: dict[str, int | None] = {"success": None, "errors": None}

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                for what, names in SUMMARY_KEYS.items():
                    if found[what] is None and _norm(k) in names and isinstance(v, int | str):
                        try:
                            found[what] = int(v)
                        except ValueError:
                            pass
                walk(v)

    walk(summary)
    return found["success"], found["errors"]


class CoupaClient:
    def __init__(self, cfg: CoupaConfig, api_key: str) -> None:
        self.cfg = cfg
        self.base = str(cfg.base_url).rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"X-API-Key": api_key, "Accept": "application/json"})
        # Reintentos automáticos solo en GET (consultas). Un POST o PUT que falla
        # con otro 5xx pudo haberse procesado; repetirlo duplicaría un lote.
        retry = Retry(
            total=4,
            backoff_factor=2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
        )
        self.s.mount("https://", HTTPAdapter(max_retries=retry))

    def _url(self, name: str, **kw) -> str:
        return self.base + ENDPOINTS[name].format(**{k: quote(str(v), safe="") for k, v in kw.items()})

    def _req(self, method: str, url: str, **kw) -> requests.Response:
        for attempt in range(6):
            resp = self.s.request(method, url, timeout=self.cfg.timeout_s, **kw)
            if resp.status_code not in RETRY_STATUS or method == "GET":
                break
            try:
                wait = float(resp.headers["Retry-After"])
            except (KeyError, ValueError):
                wait = 2 ** (attempt + 1) + random.uniform(0, 1)
            log.warning("Coupa respondió %s; reintento en %.0fs", resp.status_code, wait)
            time.sleep(wait)
        if resp.status_code >= 400:
            raise CoupaError(f"{method} {url} -> {resp.status_code}: {resp.text[:500]}")
        return resp

    # --- modelos (solo lectura, para encontrar el modelId) ------------------
    def list_models(self):
        return _json(self._req("GET", self._url("models")))

    # --- sesión -----------------------------------------------------------
    def open_session(self) -> str:
        resp = self._req("POST", self._url("open_session"), json={"fileId": self.cfg.model_id})
        session_id = _session_id_from(_json(resp))
        if not session_id:
            raise CoupaError(f"Respuesta sin sessionId: {resp.text[:500]}")
        log.info("Sesión de importación abierta: %s", session_id)
        return session_id

    def close_session(self, session_id: str) -> None:
        self._req("PUT", self._url("close_session", session_id=session_id), data=b"")
        log.info("Sesión %s cerrada", session_id)

    # --- lotes ------------------------------------------------------------
    def put_batch(self, session_id: str, table: str, records: list[dict], n: int) -> BatchResult:
        batch = BatchResult(table=table, n=n, rows=len(records), sent_at=now_iso())
        resp = self._req(
            "PUT",
            self._url("put_records", session_id=session_id, table=table),
            json=records,
            headers={"Content-Type": "application/json"},
        )
        batch.http_status = resp.status_code
        if resp.status_code != 202:
            log.warning("PUT devolvió %s (se esperaba 202)", resp.status_code)
        batch.location = resp.headers.get("Location")
        if not batch.location:
            raise CoupaError(f"PUT sin encabezado Location: {resp.status_code} {resp.text[:300]}")
        batch.operation_id = batch.location.rstrip("/").rsplit("/", 1)[-1]
        return batch

    def wait_batch(self, batch: BatchResult) -> BatchResult:
        """Consulta el Location hasta que Coupa diga true (lote terminado)."""
        url = batch.location if batch.location.startswith("http") else self.base + batch.location
        start = time.monotonic()
        deadline = start + self.cfg.poll_max_min * 60
        while time.monotonic() < deadline:
            body = _json(self._req("GET", url))
            batch.polls += 1
            if body is True or str(body).strip().lower() == "true":
                batch.status = "terminado"
                break
            if isinstance(body, dict):   # por si responde un objeto en vez de true/false
                batch.detail = body
            time.sleep(self.cfg.poll_interval_s)
        else:
            batch.status = "timeout"
        batch.finished_at = now_iso()
        batch.seconds = round(time.monotonic() - start, 1)
        return batch

    # --- resultados -------------------------------------------------------
    def summary(self, session_id: str):
        return _json(self._req("GET", self._url("summary", session_id=session_id)))

    def _pages(self, name: str, session_id: str) -> list:
        pages = []
        for index in range(1, MAX_PAGES + 1):
            body = _json(self._req(
                "GET", self._url(name, session_id=session_id),
                params={"pageSize": PAGE_SIZE, "pageIndex": index},
            ))
            pages.append(body)
            if len(page_items(body)) < PAGE_SIZE:
                break
        return pages

    def status_pages(self, session_id: str) -> list:
        return self._pages("status", session_id)

    def error_pages(self, session_id: str) -> list:
        return self._pages("errors", session_id)
