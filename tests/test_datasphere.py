"""Lectura de Datasphere contra una conexión simulada (sin datos reales)."""

import csv
import datetime as dt
from decimal import Decimal

import pytest

from coupa_ingest.config import DatasphereConfig, Settings
from coupa_ingest.datasphere import (
    DatasphereClient,
    DatasphereError,
    extract_views,
    quote_ident,
    to_text,
)

VIEWS = {
    "vw_A": (["ID", "MONTO", "FECHA", "NOTA"], [
        ("0001", Decimal("1.50"), dt.date(2026, 5, 4), None),
        ("0002", Decimal("1E+2"), dt.date(2026, 5, 5), "Año, \"comillas\""),
        ("0003", Decimal("-0.001"), dt.date(2026, 5, 6), "línea1\nlínea2"),
    ]),
    "vw_B": (["X"], [("x",)]),
}


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.description = None
        self._rows = []

    def execute(self, sql, params=None):
        self.conn.sql.append(sql)
        if "SYS.VIEWS" in sql:
            self._rows = [(v,) for v in VIEWS]
            return
        view = sql.rsplit(".", 1)[-1].strip('"')
        cols, rows = VIEWS[view]
        if sql.startswith("SELECT COUNT(*)"):
            self._rows = [(len(rows) + self.conn.count_delta,)]
        else:
            self.description = [(c,) for c in cols]
            self._rows = list(rows)

    def fetchone(self):
        return self._rows[0]

    def fetchall(self):
        return self._rows

    def fetchmany(self, n):
        out, self._rows = self._rows[:n], self._rows[n:]
        return out

    def close(self):
        pass


class FakeConn:
    def __init__(self, count_delta=0):
        self.sql = []
        self.count_delta = count_delta
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.closed = True


def _cfg(**kw):
    return DatasphereConfig(host="h", user="OLEOFINOS#COUPA", views=list(VIEWS), fetch_rows=2, **kw)


def test_to_text_keeps_exact_values():
    assert to_text(None) == ""
    assert to_text(Decimal("1E+2")) == "100"
    assert to_text(Decimal("1.50")) == "1.50"
    assert to_text(dt.datetime(2026, 5, 4, 7, 30)) == "2026-05-04 07:30:00"
    assert to_text(True) == "true"
    assert quote_ident('a"b') == '"a""b"'


def test_extract_writes_csv_and_checks_count(tmp_path):
    conn = FakeConn()
    with DatasphereClient(_cfg(), "pw", connect=lambda **kw: conn) as dsc:
        res = extract_views(dsc, ["vw_A", "vw_B"], tmp_path)
    assert conn.closed
    assert [(r.table, r.rows) for r in res] == [("vw_A", 3), ("vw_B", 1)]
    assert 'SELECT * FROM "OLEOFINOS"."vw_A"' in conn.sql
    with (tmp_path / "vw_A.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["ID", "MONTO", "FECHA", "NOTA"]
    assert rows[1] == ["0001", "1.50", "2026-05-04", ""]
    assert rows[2][3] == 'Año, "comillas"' and rows[3][3] == "línea1\nlínea2"


def test_csv_roundtrip_to_records(tmp_path):
    from coupa_ingest.transform import iter_record_batches

    with DatasphereClient(_cfg(), "pw", connect=lambda **kw: FakeConn()) as dsc:
        res = extract_views(dsc, ["vw_A"], tmp_path)
    records = [r for b in iter_record_batches(res[0].csv_path, 2) for r in b]
    assert records[2] == {"ID": "0003", "MONTO": "-0.001", "FECHA": "2026-05-06", "NOTA": "línea1\nlínea2"}


def test_count_mismatch_stops(tmp_path):
    client = DatasphereClient(_cfg(), "pw", connect=lambda **kw: FakeConn(count_delta=1))
    with client as dsc, pytest.raises(DatasphereError, match="COUNT"):
        dsc.extract("vw_A", tmp_path / "a.csv")


def test_check_reports_missing_views():
    with DatasphereClient(_cfg(), "pw", connect=lambda **kw: FakeConn()) as dsc:
        assert dsc.check(["vw_A", "vw_B"]) == {"vw_A": 3, "vw_B": 1}
        with pytest.raises(DatasphereError, match="vw_Z"):
            dsc.check(["vw_A", "vw_Z"])


def test_connection_error_has_hint():
    def boom(**kw):
        raise RuntimeError("(10, 'authentication failed')")

    with pytest.raises(DatasphereError, match="DATASPHERE_PASSWORD"),             DatasphereClient(_cfg(), "pw", connect=boom):
        pass


def test_pipeline_from_datasphere(tmp_path, monkeypatch):
    from test_pipeline import FakeClient

    import coupa_ingest.pipeline as pl

    conn = FakeConn()
    real = pl.datasphere.DatasphereClient
    monkeypatch.setattr(pl.datasphere, "DatasphereClient",
                        lambda cfg, pw: real(cfg, pw, connect=lambda **kw: conn))
    monkeypatch.setattr(pl, "CoupaClient", FakeClient)
    monkeypatch.setattr(pl.secrets, "get_secret", lambda name, amb: "x")
    s = Settings(
        data_dir=tmp_path / "data", log_dir=tmp_path / "logs",
        datasphere={"host": "h", "user": "u", "views": list(VIEWS)},
        coupa={"base_url": "https://coupa.invalid", "model_id": "M1"},
    )
    m = pl.run(s, "ds1")
    assert m.status == "ok", m.error
    assert m.rows_file == m.rows_sent == 4 and m.cuadra
    assert m.source["tipo"] == "datasphere"
    m2 = pl.run(s, "ds2", dry_run=True, only_sheets=["vw_B"])
    assert m2.status == "ok" and [x.sheet for x in m2.sheets] == ["vw_B"]
