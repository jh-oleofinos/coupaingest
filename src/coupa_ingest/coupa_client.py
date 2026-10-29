"""Cliente de la API de importación de Coupa.

Flujo tomado del documento de ejemplo (llama.ai / LLamasoft):
  1. abrir sesión de importación
  2. enviar lotes por PUT (respuesta 202, asíncrona)
  3. revisar el estado de cada lote
  4. cerrar sesión
  5. consultar resumen y errores

PENDIENTE: confirmar con Coupa rutas exactas, encabezado de autenticación,
formato del cuerpo (CSV) y límites. Las rutas viven en ENDPOINTS para
ajustarlas en un solo lugar.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from coupa_ingest.config import CoupaConfig

log = logging.getLogger(__name__)

# TODO(Coupa): confirmar rutas. {session_id}, {table}, {batch_id} se sustituyen.
ENDPOINTS = {
    "open_session": "/import/sessions",
    "put_batch": "/import/sessions/{session_id}/tables/{table}/batches",
    "batch_status": "/import/sessions/{session_id}/batches/{batch_id}",
    "close_session": "/import/sessions/{session_id}/close",
    "summary": "/import/sessions/{session_id}/summary",
    "errors": "/import/sessions/{session_id}/errors",
}
DONE_STATES = {"completed", "succeeded", "success"}
FAILED_STATES = {"failed", "error", "rejected"}


class CoupaError(RuntimeError):
    pass


@dataclass
class BatchResult:
    batch_id: str
    rows_sent: int
    status: str = "pending"
    detail: dict = field(default_factory=dict)


class CoupaClient:
    def __init__(self, cfg: CoupaConfig, api_key: str) -> None:
        self.cfg = cfg
        self.base = str(cfg.base_url).rstrip("/")
        self.s = requests.Session()
        # TODO(Coupa): confirmar el encabezado (Bearer, X-API-Key, etc.)
        self.s.headers.update({"Authorization": f"Bearer {api_key}", "Accept": "application/json"})
        # Reintentos automáticos solo en GET (consultas). Un POST o PUT que falla
        # con 5xx pudo haberse procesado del lado de Coupa; repetirlo podría
        # abrir otra sesión o duplicar un lote, así que se deja como falla.
        retry = Retry(
            total=4,
            backoff_factor=2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
        )
        self.s.mount("https://", HTTPAdapter(max_retries=retry))

    def _url(self, name: str, **kw) -> str:
        return self.base + ENDPOINTS[name].format(**kw)

    def _req(self, method: str, url: str, **kw) -> requests.Response:
        # 429 = Coupa no procesó la petición: es seguro esperar y repetir.
        for attempt in range(5):
            resp = self.s.request(method, url, timeout=self.cfg.timeout_s, **kw)
            if resp.status_code != 429 or method == "GET":
                break
            wait = int(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
            log.warning("Coupa respondió 429; reintento en %ss", wait)
            time.sleep(wait)
        if resp.status_code >= 400:
            raise CoupaError(f"{method} {url} -> {resp.status_code}: {resp.text[:300]}")
        return resp

    # --- sesión -----------------------------------------------------------
    def open_session(self, run_id: str) -> str:
        resp = self._req("POST", self._url("open_session"), json={"reference": run_id})
        session_id = resp.json().get("id") or resp.json().get("session_id")
        if not session_id:
            raise CoupaError(f"Respuesta sin id de sesión: {resp.text[:300]}")
        log.info("Sesión de importación abierta: %s", session_id)
        return str(session_id)

    def close_session(self, session_id: str) -> None:
        self._req("POST", self._url("close_session", session_id=session_id))
        log.info("Sesión %s cerrada", session_id)

    # --- lotes ------------------------------------------------------------
    def put_batch(self, session_id: str, table: str, csv_bytes: bytes, rows: int) -> BatchResult:
        resp = self._req(
            "PUT",
            self._url("put_batch", session_id=session_id, table=table),
            data=csv_bytes,
            headers={"Content-Type": "text/csv; charset=utf-8"},
        )
        if resp.status_code != 202:
            log.warning("PUT devolvió %s (se esperaba 202)", resp.status_code)
        body = resp.json() if resp.content else {}
        batch_id = str(body.get("id") or body.get("batch_id") or "")
        if not batch_id:
            raise CoupaError(f"Respuesta sin id de lote: {resp.text[:300]}")
        return BatchResult(batch_id=batch_id, rows_sent=rows)

    def wait_batch(self, session_id: str, batch: BatchResult) -> BatchResult:
        deadline = time.monotonic() + self.cfg.poll_max_min * 60
        while time.monotonic() < deadline:
            body = self._req(
                "GET", self._url("batch_status", session_id=session_id, batch_id=batch.batch_id)
            ).json()
            status = str(body.get("status", "")).lower()
            if status in DONE_STATES | FAILED_STATES:
                batch.status, batch.detail = status, body
                return batch
            time.sleep(self.cfg.poll_interval_s)
        batch.status = "timeout"
        return batch

    # --- resultados -------------------------------------------------------
    def summary(self, session_id: str) -> dict:
        return self._req("GET", self._url("summary", session_id=session_id)).json()

    def errors(self, session_id: str) -> list | dict:
        return self._req("GET", self._url("errors", session_id=session_id)).json()
