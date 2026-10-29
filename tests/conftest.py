import io

import pandas as pd
import pytest

from coupa_ingest.config import SheetConfig


@pytest.fixture
def sample_xlsx() -> bytes:
    """Excel sintético (sin datos reales) con dos pestañas."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame(
            {"supplier_id": ["0001", "0002", "0003"], "name": ["A", "B", "C"], "amount": ["1.50", "2", "3.10"]}
        ).to_excel(xw, sheet_name="Proveedores", index=False)
        pd.DataFrame({"product_id": ["P1", "P2"], "uom": ["KG", "L"]}).to_excel(
            xw, sheet_name="Productos", index=False
        )
    return buf.getvalue()


@pytest.fixture
def sheets() -> list[SheetConfig]:
    return [
        SheetConfig(sheet="Proveedores", table="suppliers", key=["supplier_id"]),
        SheetConfig(sheet="Productos", table="products", key=["product_id"]),
    ]
