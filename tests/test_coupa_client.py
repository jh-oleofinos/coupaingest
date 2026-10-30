"""Cliente de llama.ai contra respuestas simuladas (formato del PDF de Coupa)."""

import json

import pytest

from coupa_ingest.config import CoupaConfig
from coupa_ingest.coupa_client import CoupaClient, CoupaError, summary_totals


class Resp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self.text = body if isinstance(body, str) else json.dumps(body)
        self.content = self.text.encode()

    def json(self):
        return json.loads(self.text)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def request(self, method, url, timeout=None, **kw):
        self.calls.append((method, url, kw))
        return self.responses.pop(0)


def _client(responses):
    cfg = CoupaConfig(base_url="https://api.llama.ai", model_id="M1", poll_interval_s=0)
    c = CoupaClient(cfg, "KEY")
    assert c.s.headers["X-API-Key"] == "KEY"
    c.s = FakeSession(responses)
    return c


def test_session_batch_and_poll():
    c = _client([
        Resp(200, {"id": "S1"}),
        Resp(202, "", {"Location": "/v4/operation/record/OP9"}),
        Resp(200, False),
        Resp(200, True),
        Resp(200, ""),
    ])
    sid = c.open_session()
    assert sid == "S1"
    assert c.s.calls[0][2]["json"] == {"fileId": "M1"}
    batch = c.put_batch(sid, "VW_YVA05", 1, b'[{"A":"1","B":""}]', 1)
    method, url, kw = c.s.calls[1]
    assert method == "PUT" and url.endswith("/v4/import/session/S1/table/VW_YVA05/record")
    assert json.loads(kw["data"]) == [{"A": "1", "B": ""}]
    assert batch.operation_id == "OP9"
    batch = c.wait_batch(batch)
    assert batch.status == "terminado" and batch.polls == 2
    assert c.s.calls[2][1] == "https://api.llama.ai/v4/operation/record/OP9"
    c.close_session(sid)
    assert c.s.calls[4][0] == "PUT" and c.s.calls[4][1].endswith("/S1/close")


def test_put_without_location_fails():
    c = _client([Resp(202, "")])
    with pytest.raises(CoupaError, match="Location"):
        c.put_batch("S1", "T", 1, b"[]", 1)


def test_put_retries_on_429_and_503(monkeypatch):
    monkeypatch.setattr("coupa_ingest.coupa_client.time.sleep", lambda s: None)
    c = _client([Resp(429, ""), Resp(503, ""), Resp(202, "", {"Location": "/x/OP1"})])
    assert c.put_batch("S1", "T", 1, b"[]", 1).operation_id == "OP1"


def test_413_is_payload_too_large():
    from coupa_ingest.coupa_client import PayloadTooLargeError

    c = _client([Resp(413, "too big")])
    with pytest.raises(PayloadTooLargeError):
        c.put_batch("S1", "T", 1, b"[]", 1)


def test_put_does_not_retry_500():
    c = _client([Resp(500, "boom")])
    with pytest.raises(CoupaError, match="500"):
        c.put_batch("S1", "T", 1, b"[]", 1)
    assert len(c.s.calls) == 1


def test_error_pages_until_short_page(monkeypatch):
    monkeypatch.setattr("coupa_ingest.coupa_client.PAGE_SIZE", 2)
    c = _client([Resp(200, [{"e": 1}, {"e": 2}]), Resp(200, [{"e": 3}])])
    assert len(c.error_pages("S1")) == 2
    assert c.s.calls[1][2]["params"] == {"pageSize": 2, "pageIndex": 2}


def test_summary_totals_tolerates_shapes():
    assert summary_totals({"successCount": 10, "errorCount": 0}) == (10, 0)
    assert summary_totals({"summary": {"total_success": "7", "total-errors": "1"}}) == (7, 1)
    assert summary_totals({"algo": 1}) == (None, None)
