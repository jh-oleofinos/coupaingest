import io

import pandas as pd
import pytest

from coupa_ingest.config import SheetConfig
from coupa_ingest.transform import ValidationError, excel_to_csvs, iter_record_batches


def test_csv_keeps_values_as_text(sample_xlsx, sheets, tmp_path):
    results = excel_to_csvs(sample_xlsx, sheets, tmp_path)
    assert [r.rows for r in results] == [3, 2]
    text = (tmp_path / "suppliers.csv").read_text(encoding="utf-8")
    assert "0001" in text          # ceros a la izquierda se conservan
    assert "1.50" in text          # sin reinterpretar decimales


def test_missing_sheet_fails_before_writing(sample_xlsx, tmp_path):
    cfg = [
        SheetConfig(sheet="Proveedores", table="suppliers", key=["supplier_id"]),
        SheetConfig(sheet="NoExiste", table="x"),
    ]
    with pytest.raises(ValidationError, match="NoExiste"):
        excel_to_csvs(sample_xlsx, cfg, tmp_path)
    assert not list(tmp_path.glob("*.csv"))


def test_duplicate_key_rejected(tmp_path):
    buf = io.BytesIO()
    pd.DataFrame({"id": ["1", "1"]}).to_excel(buf, sheet_name="S", index=False)
    with pytest.raises(ValidationError, match="duplicada"):
        excel_to_csvs(buf.getvalue(), [SheetConfig(sheet="S", table="t", key=["id"])], tmp_path)


def test_all_sheets_with_exclude_and_override(sample_xlsx, tmp_path):
    override = [SheetConfig(sheet="Productos", table="products", key=["product_id"])]
    res = excel_to_csvs(sample_xlsx, override, tmp_path, all_sheets=True, exclude=[])
    assert [(r.sheet, r.table) for r in res] == [("Proveedores", "Proveedores"), ("Productos", "products")]
    res = excel_to_csvs(sample_xlsx, [], tmp_path, all_sheets=True, exclude=["Productos"])
    assert [r.sheet for r in res] == ["Proveedores"]


def test_batches_have_header_and_sum_rows(sample_xlsx, sheets, tmp_path):
    res = excel_to_csvs(sample_xlsx, sheets, tmp_path)[0]
    batches = list(iter_record_batches(res.csv_path, batch_rows=2))
    assert [len(b) for b in batches] == [2, 1]
    assert batches[0][0] == {"supplier_id": "0001", "name": "A", "amount": "1.50"}
