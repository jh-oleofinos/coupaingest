"""Excel -> CSV por pestaña, sin transformar valores.

Todas las celdas se leen como texto para que lo enviado sea exactamente lo
que hay en el archivo (sin redondeos, fechas reinterpretadas ni ceros perdidos).
El libro se abre una sola vez aunque tenga muchas pestañas grandes.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import openpyxl
import pandas as pd

from coupa_ingest.config import SheetConfig

log = logging.getLogger(__name__)


class ValidationError(RuntimeError):
    pass


@dataclass
class SheetResult:
    sheet: str
    table: str
    rows: int
    csv_path: Path


def resolve_sheets(
    sheet_names: list[str],
    configured: list[SheetConfig],
    all_sheets: bool,
    exclude: list[str],
) -> list[SheetConfig]:
    """Decide qué pestañas se procesan.

    all_sheets=True: todas las del libro (menos `exclude`), en el orden del libro;
    las que estén en `configured` toman de ahí su tabla destino y llaves.
    all_sheets=False: solo las de `configured`.
    """
    by_name = {s.sheet: s for s in configured}
    missing = [n for n in by_name if n not in sheet_names]
    if missing:
        raise ValidationError(f"Pestañas configuradas que no existen en el archivo: {missing}")
    if not all_sheets:
        return list(configured)
    return [by_name.get(n, SheetConfig(sheet=n, table=n)) for n in sheet_names if n not in exclude]


def read_sheet(book: pd.ExcelFile, sheet: str) -> pd.DataFrame:
    df = book.parse(sheet_name=sheet, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    # Quita filas totalmente vacías (comunes al final de una hoja)
    df = df[~(df == "").all(axis=1)].reset_index(drop=True)
    return df


def validate(df: pd.DataFrame, cfg: SheetConfig) -> None:
    unnamed = [c for c in df.columns if c.startswith("Unnamed:")]
    if unnamed:
        raise ValidationError(f"[{cfg.sheet}] columnas sin encabezado: {unnamed}")
    dup_cols = [c for c in df.columns if re.search(r"\.\d+$", c) and c.rsplit(".", 1)[0] in df.columns]
    if dup_cols:
        raise ValidationError(f"[{cfg.sheet}] encabezados repetidos: {dup_cols}")
    missing = [k for k in cfg.key if k not in df.columns]
    if missing:
        raise ValidationError(f"[{cfg.sheet}] faltan columnas llave: {missing}")
    if cfg.key:
        empty = df[cfg.key].eq("").any(axis=1).sum()
        if empty:
            raise ValidationError(f"[{cfg.sheet}] {empty} filas con llave vacía")
        dup = df.duplicated(subset=cfg.key).sum()
        if dup:
            raise ValidationError(f"[{cfg.sheet}] {dup} filas con llave duplicada")


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "hoja"


def to_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")


def hidden_sheets(xlsx: bytes) -> list[str]:
    wb = openpyxl.load_workbook(io.BytesIO(xlsx), read_only=True)
    try:
        return [ws.title for ws in wb.worksheets if ws.sheet_state != "visible"]
    finally:
        wb.close()


def excel_to_csvs(
    xlsx: bytes,
    sheets: list[SheetConfig],
    out_dir: Path,
    all_sheets: bool = False,
    exclude: list[str] | None = None,
    include_hidden: bool = False,
    allow_empty: bool = False,
) -> list[SheetResult]:
    """Valida TODAS las pestañas antes de escribir; si una falla no se envía nada."""
    book = pd.ExcelFile(io.BytesIO(xlsx), engine="openpyxl")
    exclude = list(exclude or [])
    if all_sheets and not include_hidden:
        hidden = hidden_sheets(xlsx)
        if hidden:
            log.info("Pestañas ocultas que no se procesan: %s", hidden)
            exclude += hidden
    selected = resolve_sheets(book.sheet_names, sheets, all_sheets, exclude)
    if not selected:
        raise ValidationError("No hay pestañas que procesar")
    log.info("Pestañas a procesar (%d): %s", len(selected), [s.sheet for s in selected])

    frames: list[tuple[SheetConfig, pd.DataFrame]] = []
    errors: list[str] = []
    for cfg in selected:
        try:
            df = read_sheet(book, cfg.sheet)
            if df.empty and not allow_empty:
                raise ValidationError(f"[{cfg.sheet}] la pestaña no tiene filas")
            validate(df, cfg)
            frames.append((cfg, df))
        except ValidationError as exc:
            errors.append(str(exc))
    if errors:
        raise ValidationError("; ".join(errors))

    results = []
    for cfg, df in frames:
        path = out_dir / f"{safe_filename(cfg.table)}.csv"
        to_csv(df, path)
        log.info("[%s] %d filas, %d columnas -> %s", cfg.sheet, len(df), df.shape[1], path.name)
        results.append(SheetResult(cfg.sheet, cfg.table, len(df), path))
    return results


def iter_record_batches(csv_path: Path, batch_rows: int):
    """Parte un CSV en lotes de `batch_rows` filas como lista de {columna: valor}.

    Todo va como texto, tal como está en el archivo; una celda vacía es "".
    """
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = pd.read_csv(fh, dtype=str, keep_default_na=False, chunksize=batch_rows)
        for chunk in reader:
            yield chunk.to_dict(orient="records")
