import json

from coupa_ingest.config import Settings
from coupa_ingest.pipeline import run


def _settings(tmp_path, sheets) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        log_dir=tmp_path / "logs",
        sharepoint={"tenant_id": "t", "client_id": "c", "hostname": "h", "site_path": "/s", "file_path": "/f.xlsx"},
        coupa={"base_url": "https://coupa.invalid"},
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


def test_send_flow_with_fake_coupa(sample_xlsx, sheets, tmp_path, monkeypatch):
    import coupa_ingest.pipeline as pl

    class FakeClient:
        def __init__(self, *a, **k):
            self.n = 0

        def open_session(self, run_id):
            return "S1"

        def put_batch(self, sid, table, payload, rows):
            from coupa_ingest.coupa_client import BatchResult

            self.n += 1
            return BatchResult(batch_id=f"B{self.n}", rows_sent=rows)

        def wait_batch(self, sid, batch):
            batch.status = "completed"
            return batch

        def close_session(self, sid):
            pass

        def summary(self, sid):
            return {"tables": {"suppliers": {"accepted": 3}, "products": {"accepted": 2}}}

        def errors(self, sid):
            return []

    monkeypatch.setattr(pl, "CoupaClient", FakeClient)
    monkeypatch.setattr(pl.secrets, "get_secret", lambda name, amb: "x")
    src = tmp_path / "in.xlsx"
    src.write_bytes(sample_xlsx)
    m = run(_settings(tmp_path, sheets), "r2", local_file=src)
    assert m.status == "ok", m.error
    assert all(s.cuadra for s in m.sheets)
