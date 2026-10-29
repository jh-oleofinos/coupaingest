import json

from coupa_ingest.config import Settings
from coupa_ingest.pipeline import run


def _settings(tmp_path, sheets) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        log_dir=tmp_path / "logs",
        sharepoint={"file_url": "https://x.sharepoint.com/f.xlsx"},
        coupa={"base_url": "https://coupa.invalid", "model_id": "M1"},
        sheets=sheets,
    )


def test_dry_run_with_local_file(sample_xlsx, sheets, tmp_path):
    src = tmp_path / "in.xlsx"
    src.write_bytes(sample_xlsx)
    m = run(_settings(tmp_path, sheets), "test_run", dry_run=True, local_file=src)
    assert m.status == "ok", m.error
    run_dir = tmp_path / "data" / "runs" / "test_run"
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert [s["rows_file"] for s in manifest["sheets"]] == [3, 2]
    assert (run_dir / "source.xlsx").exists()
    assert (run_dir / "csv" / "products.csv").exists()


class FakeClient:
    """Simula Coupa: cada lote termina y el resumen reporta lo que se envió."""

    def __init__(self, *a, **k):
        self.sent = 0
        self.closed = False

    def open_session(self):
        return "S1"

    def put_batch(self, sid, table, records, n):
        from coupa_ingest.coupa_client import BatchResult

        assert all(isinstance(v, str) for r in records for v in r.values())
        self.sent += len(records)
        return BatchResult(table=table, n=n, rows=len(records), http_status=202,
                           location=f"/v4/operation/record/{table}-{n}", operation_id=f"{table}-{n}")

    def wait_batch(self, batch):
        batch.status, batch.polls = "terminado", 1
        return batch

    def close_session(self, sid):
        self.closed = True

    def summary(self, sid):
        return {"successCount": self.sent, "errorCount": 0}

    def status_pages(self, sid):
        return [[]]

    def error_pages(self, sid):
        return [[]]


def test_send_flow_with_fake_coupa(sample_xlsx, sheets, tmp_path, monkeypatch):
    import coupa_ingest.pipeline as pl

    monkeypatch.setattr(pl, "CoupaClient", FakeClient)
    monkeypatch.setattr(pl.secrets, "get_secret", lambda name, amb: "x")
    src = tmp_path / "in.xlsx"
    src.write_bytes(sample_xlsx)
    m = run(_settings(tmp_path, sheets), "r2", local_file=src)
    assert m.status == "ok", m.error
    assert m.cuadra and m.rows_sent == 5
    log = (tmp_path / "data" / "registro_lotes.csv").read_text(encoding="utf-8").splitlines()
    assert len(log) == 3 and log[0].startswith("run_id,session_id,table")
    runs = (tmp_path / "data" / "registro_corridas.csv").read_text(encoding="utf-8").splitlines()
    assert len(runs) == 2 and ",ok," in runs[1]
    assert m.rejected_rows == 0


def test_send_fails_when_coupa_reports_errors(sample_xlsx, sheets, tmp_path, monkeypatch):
    import coupa_ingest.pipeline as pl

    class WithErrors(FakeClient):
        def summary(self, sid):
            return {"successCount": self.sent - 1, "errorCount": 1}

        def error_pages(self, sid):
            return [[{"table": "suppliers", "row": 2, "message": "columna X no existe"}]]

    monkeypatch.setattr(pl, "CoupaClient", WithErrors)
    monkeypatch.setattr(pl.secrets, "get_secret", lambda name, amb: "x")
    src = tmp_path / "in.xlsx"
    src.write_bytes(sample_xlsx)
    m = run(_settings(tmp_path, sheets), "r3", local_file=src)
    assert m.status == "failed" and "No cuadra" in m.error
    assert m.rejected_rows == 1
    rej = (tmp_path / "data" / "runs" / "r3" / "rechazados.csv").read_text(encoding="utf-8-sig")
    assert rej.splitlines()[0] == "table,row,message"
