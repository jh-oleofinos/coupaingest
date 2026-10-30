"""División automática de lotes por tamaño y ante 413."""

import json

import pytest

from coupa_ingest.batching import Limits, send_adaptive, split_by_size, to_json_bytes
from coupa_ingest.coupa_client import CoupaError, PayloadTooLargeError


def _rows(n, width=10):
    return [{"ID": f"{i:06d}", "TXT": "x" * width} for i in range(n)]


def test_split_respects_rows_and_bytes():
    rows = _rows(10)
    assert [len(c) for c in split_by_size(rows, Limits(max_rows=4, max_bytes=10**6))] == [4, 4, 2]
    one = len(to_json_bytes(rows[:1]))
    chunks = list(split_by_size(rows, Limits(max_rows=100, max_bytes=one * 3)))
    assert all(len(to_json_bytes(c)) <= one * 3 for c in chunks)
    assert sum(len(c) for c in chunks) == 10


def test_413_splits_and_lowers_limits():
    sent = []

    def send(chunk, body, nota):
        if len(body) > 300:            # Coupa simulado: rechaza más de 300 bytes
            raise PayloadTooLargeError("413")
        assert json.loads(body) == chunk
        sent.append((len(chunk), nota))

    limits = Limits(max_rows=100, max_bytes=10**6)
    rows = _rows(20)
    send_adaptive(send, rows, limits)
    assert sum(n for n, _ in sent) == 20          # no se pierde ni duplica ninguna fila
    assert limits.splits >= 1 and limits.max_rows < 100
    assert any("413" in nota for _, nota in sent)


def test_single_row_too_big_fails():
    def send(chunk, body, nota):
        raise PayloadTooLargeError("413")

    with pytest.raises(CoupaError, match="Una sola fila"):
        send_adaptive(send, _rows(1), Limits(max_rows=10, max_bytes=10**6))


def test_accents_are_sent_as_utf8():
    body = to_json_bytes([{"N": "Año Señal"}])
    assert "Año".encode() in body
