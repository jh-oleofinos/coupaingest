"""Lectura directa de las vistas de SAP Datasphere (HANA Cloud) con hdbcli.

Mismo origen que usa el Excel de Simón (ODBC `DATASPHERE_OLEOFINOS`, esquema
OLEOFINOS), pero sin Excel de por medio. Requisitos (los da el administrador
de Datasphere): un usuario de base de datos del espacio con lectura SQL, las
vistas expuestas para consumo y la IP del equipo en la lista permitida.

Cada vista se lee por bloques (fetch_rows) y se escribe a CSV con todos los
valores como texto. Antes de leer se cuenta con COUNT(*) y, si lo leído no
coincide, la corrida se detiene antes de enviar nada a Coupa.
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
from decimal import Decimal
from pathlib import Path

from coupa_ingest.config import DatasphereConfig
from coupa_ingest.transform import SheetResult, ValidationError, safe_filename

log = logging.getLogger(__name__)


class DatasphereError(RuntimeError):
    pass


def to_text(value) -> str:
    """Valor de HANA a texto, sin redondeos ni formato regional."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return format(value, "f")          # exacto, sin notación científica
    if isinstance(value, dt.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, bytes | bytearray | memoryview):
        return bytes(value).hex()
    return str(value)


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _explain(exc: Exception) -> str:
    """Pista de qué revisar según el error de conexión."""
    msg = str(exc)
    low = msg.lower()
    if "authentication failed" in low or "invalid user" in low:
        hint = "usuario o contraseña (DATASPHERE_PASSWORD)"
    elif "timeout" in low or "timed out" in low or "connection refused" in low or "-10709" in msg:
        hint = "red: salida por 443 hacia el host, o la IP no está en la IP Allowlist de Datasphere"
    elif "insufficient privilege" in low:
        hint = "permisos del usuario de base de datos sobre el esquema"
    else:
        hint = "host, puerto, usuario y red"
    return f"{msg} → revisar {hint}"


class DatasphereClient:
    def __init__(self, cfg: DatasphereConfig, password: str, connect=None) -> None:
        self.cfg = cfg
        self._password = password
        self._connect = connect
        self._conn = None

    def __enter__(self):
        connect = self._connect
        if connect is None:
            from hdbcli import dbapi

            connect = dbapi.connect
        try:
            self._conn = connect(
                address=self.cfg.host, port=self.cfg.port, user=self.cfg.user,
                password=self._password, encrypt=True, sslValidateCertificate=True,
                connectTimeout=self.cfg.timeout_s * 1000,
            )
        except Exception as exc:  # hdbcli lanza varios tipos de error
            raise DatasphereError(f"No se pudo conectar a Datasphere: {_explain(exc)}") from exc
        return self

    def __exit__(self, *exc) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _fq(self, view: str) -> str:
        return f"{quote_ident(self.cfg.schema_)}.{quote_ident(view)}"

    def visible_views(self) -> set[str]:
        cur = self._conn.cursor()
        try:
            cur.execute("SELECT VIEW_NAME FROM SYS.VIEWS WHERE SCHEMA_NAME = ?", (self.cfg.schema_,))
            return {r[0] for r in cur.fetchall()}
        finally:
            cur.close()

    def count(self, view: str) -> int:
        cur = self._conn.cursor()
        try:
            cur.execute(f"SELECT COUNT(*) FROM {self._fq(view)}")
            return int(cur.fetchone()[0])
        finally:
            cur.close()

    def check(self, views: list[str]) -> dict[str, int]:
        """Que el esquema tenga cada vista y cuántas filas trae (sin leer datos)."""
        missing = sorted(set(views) - self.visible_views())
        if missing:
            raise DatasphereError(
                f"El usuario {self.cfg.user} no ve estas vistas en {self.cfg.schema_}: {missing}. "
                "Revisar que estén expuestas para consumo (Expose for Consumption)."
            )
        return {v: self.count(v) for v in views}

    def extract(self, view: str, path: Path) -> int:
        """Lee la vista completa por bloques y la escribe a CSV (todo texto)."""
        expected = self.count(view)
        rows = 0
        cur = self._conn.cursor()
        try:
            cur.execute(f"SELECT * FROM {self._fq(view)}")
            columns = [d[0] for d in cur.description]
            if len(set(columns)) != len(columns):
                raise ValidationError(f"[{view}] columnas repetidas: {columns}")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh, lineterminator="\n")
                w.writerow(columns)
                while chunk := cur.fetchmany(self.cfg.fetch_rows):
                    w.writerows([to_text(v) for v in r] for r in chunk)
                    rows += len(chunk)
        finally:
            cur.close()
        if rows != expected:
            raise DatasphereError(
                f"[{view}] COUNT(*) dio {expected} y se leyeron {rows}; "
                "la vista cambió durante la lectura. Volver a correr."
            )
        log.info("[%s] %d filas, %d columnas -> %s", view, rows, len(columns), path.name)
        return rows


def extract_views(client: DatasphereClient, views: list[str], out_dir: Path,
                  allow_empty: bool = False) -> list[SheetResult]:
    """Extrae cada vista a out_dir/<vista>.csv. Tabla destino = nombre de la vista."""
    results = []
    for view in views:
        path = out_dir / f"{safe_filename(view)}.csv"
        rows = client.extract(view, path)
        if rows == 0 and not allow_empty:
            raise ValidationError(f"[{view}] la vista no trajo filas (allow_empty_sheets = false)")
        results.append(SheetResult(view, view, rows, path))
    return results
