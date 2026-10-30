"""Lotes que se ajustan solos al tamaño que acepta Coupa.

1. Antes de enviar: cada lote se corta por filas (batch_rows) o por tamaño del
   JSON (max_batch_mb), lo que se alcance primero.
2. Si Coupa responde 413 (payload demasiado grande), el lote se parte a la mitad
   y se reenvía cada parte; un 413 significa que no se procesó, así que reenviar
   no duplica. Los límites bajan para que los lotes siguientes ya salgan del
   tamaño que funcionó.
3. Si una sola fila no cabe, se detiene con un error claro.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from coupa_ingest.coupa_client import CoupaError, PayloadTooLargeError

log = logging.getLogger(__name__)


def to_json_bytes(records: list[dict]) -> bytes:
    """Serialización única: lo que se mide es exactamente lo que se envía."""
    return json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def record_bytes(record: dict) -> int:
    return len(to_json_bytes([record])) - 1   # sin un corchete; la coma lo compensa


@dataclass
class Limits:
    max_rows: int
    max_bytes: int
    splits: int = 0    # cuántas veces se partió un lote por 413 en la corrida


def split_by_size(records: list[dict], limits: Limits) -> Iterable[list[dict]]:
    chunk: list[dict] = []
    size = 2   # corchetes
    for r in records:
        rb = record_bytes(r)
        if chunk and (len(chunk) >= limits.max_rows or size + rb > limits.max_bytes):
            yield chunk
            chunk, size = [], 2
        chunk.append(r)
        size += rb
    if chunk:
        yield chunk


def send_adaptive(send: Callable[[list[dict], bytes, str], None], records: list[dict],
                  limits: Limits) -> None:
    """Envía `records` con send(chunk, cuerpo_json, nota), partiendo ante 413."""
    for chunk in split_by_size(records, limits):
        _send_chunk(send, chunk, limits, "")


def _send_chunk(send, chunk: list[dict], limits: Limits, note: str) -> None:
    body = to_json_bytes(chunk)
    try:
        send(chunk, body, note)
    except PayloadTooLargeError:
        if len(chunk) == 1:
            raise CoupaError(
                f"Una sola fila ({len(body):,} bytes) excede el tamaño que acepta Coupa"
            ) from None
        half = len(chunk) // 2
        limits.max_rows = min(limits.max_rows, half)
        limits.max_bytes = min(limits.max_bytes, len(body) // 2)
        limits.splits += 1
        log.warning("Coupa rechazó un lote de %d filas (%s bytes) por tamaño; se parte en dos. "
                    "Nuevo límite: %d filas / %s bytes",
                    len(chunk), f"{len(body):,}", limits.max_rows, f"{limits.max_bytes:,}")
        _send_chunk(send, chunk[:half], limits, "parte de lote dividido por 413")
        _send_chunk(send, chunk[half:], limits, "parte de lote dividido por 413")
