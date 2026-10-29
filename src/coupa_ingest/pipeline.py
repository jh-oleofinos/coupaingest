"""Orquestación de una corrida: SharePoint -> CSV -> Coupa."""

from __future__ import annotations

import logging
from pathlib import Path

from coupa_ingest import secrets
from coupa_ingest.config import Settings, SheetConfig
from coupa_ingest.control import RunManifest, SheetControl, now_iso
from coupa_ingest.coupa_client import CoupaClient
from coupa_ingest.sharepoint import SharePointClient
from coupa_ingest.transform import excel_to_csvs, iter_csv_batches

log = logging.getLogger(__name__)


def run(
    settings: Settings,
    run_id: str,
    dry_run: bool = False,
    local_file: Path | None = None,
    only_sheets: list[str] | None = None,
) -> RunManifest:
    run_dir = settings.data_dir / "runs" / run_id
    manifest = RunManifest(run_id=run_id, ambiente=settings.ambiente, dry_run=dry_run)
    sheets = settings.sheets
    all_sheets = settings.all_sheets
    exclude = list(settings.exclude_sheets)
    if only_sheets:  # --sheet limita la corrida a esas pestañas
        by_name = {s.sheet: s for s in settings.sheets}
        sheets = [by_name.get(n, SheetConfig(sheet=n, table=n)) for n in only_sheets]
        all_sheets = False

    try:
        # 1. Origen: SharePoint (o archivo local para pruebas)
        if local_file:
            xlsx, meta = local_file.read_bytes(), {"name": local_file.name, "local": True}
        else:
            sp = SharePointClient(
                settings.sharepoint,
                secrets.get_secret(secrets.GRAPH_CLIENT_SECRET, settings.ambiente),
            )
            xlsx, meta = sp.download_file()
        manifest.source = meta
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "source.xlsx").write_bytes(xlsx)   # copia exacta de lo leído

        # 2. Excel -> CSV (valida todo antes de enviar nada)
        results = excel_to_csvs(xlsx, sheets, run_dir / "csv", all_sheets, exclude)
        manifest.sheets = [SheetControl(r.sheet, r.table, rows_file=r.rows) for r in results]
        manifest.save(run_dir)

        if dry_run:
            log.info("DRY RUN: no se envía nada a Coupa")
            manifest.status = "ok"
            return manifest

        # 3. Envío a Coupa
        client = CoupaClient(
            settings.coupa, secrets.get_secret(secrets.COUPA_API_KEY, settings.ambiente)
        )
        session_id = client.open_session(run_id)
        manifest.coupa_session_id = session_id
        try:
            for res, ctl in zip(results, manifest.sheets):
                for rows, payload in iter_csv_batches(res.csv_path, settings.coupa.batch_rows):
                    batch = client.put_batch(session_id, res.table, payload, rows)
                    ctl.rows_sent += rows
                    batch = client.wait_batch(session_id, batch)
                    ctl.batches.append(
                        {"batch_id": batch.batch_id, "rows": rows, "status": batch.status}
                    )
                    log.info("[%s] lote %s: %d filas, %s", res.sheet, batch.batch_id, rows, batch.status)
                    manifest.save(run_dir)
        finally:
            client.close_session(session_id)

        # 4. Resumen y errores
        summary = client.summary(session_id)
        errors = client.errors(session_id)
        (run_dir / "coupa_summary.json").write_text(_dump(summary), encoding="utf-8")
        (run_dir / "coupa_errors.json").write_text(_dump(errors), encoding="utf-8")
        _apply_summary(manifest, summary)

        bad = [b for s in manifest.sheets for b in s.batches if b["status"] not in ("completed", "succeeded", "success")]
        descuadre = [s.sheet for s in manifest.sheets if s.cuadra is False]
        if bad or descuadre:
            raise RuntimeError(f"Lotes con problema: {len(bad)}; pestañas que no cuadran: {descuadre}")
        manifest.status = "ok"
    except Exception as exc:
        manifest.status = "failed"
        manifest.error = f"{type(exc).__name__}: {exc}"
        log.exception("La corrida falló")
    finally:
        manifest.finished_at = now_iso()
        manifest.save(run_dir)
    return manifest


def _dump(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, indent=2)


def _apply_summary(manifest: RunManifest, summary: dict) -> None:
    """TODO(Coupa): ajustar al formato real del resumen.

    Se asume {"tables": {"<tabla>": {"accepted": n, "rejected": m}}}.
    """
    tables = (summary or {}).get("tables", {})
    for ctl in manifest.sheets:
        info = tables.get(ctl.table)
        if info and "accepted" in info:
            ctl.rows_accepted = int(info["accepted"])
