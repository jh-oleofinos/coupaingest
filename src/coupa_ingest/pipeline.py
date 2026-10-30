"""Orquestación de una corrida: SharePoint -> CSV -> JSON a Coupa."""

from __future__ import annotations

import itertools
import json
import logging
import os
import shutil
import time
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from coupa_ingest import secrets, sharepoint
from coupa_ingest.batching import Limits, send_adaptive
from coupa_ingest.config import Settings, SheetConfig
from coupa_ingest.control import (
    RunManifest,
    SheetControl,
    append_batch_log,
    append_run_log,
    now_iso,
    summary_lines,
    write_rejected,
)
from coupa_ingest.coupa_client import CoupaClient, page_items, summary_totals
from coupa_ingest.transform import excel_to_csvs, iter_record_batches

log = logging.getLogger(__name__)


class AlreadyRunningError(RuntimeError):
    pass


@contextmanager
def run_lock(data_dir: Path):
    """Evita dos corridas a la vez (tarea programada + una manual)."""
    data_dir.mkdir(parents=True, exist_ok=True)
    lock = data_dir / ".lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        age_h = (time.time() - lock.stat().st_mtime) / 3600
        raise AlreadyRunningError(
            f"Ya hay una corrida en curso (candado de hace {age_h:.1f} h: {lock}). "
            "Si no hay ninguna corriendo, borra ese archivo."
        ) from None
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def _state_path(settings: Settings) -> Path:
    return settings.data_dir / "state.json"


def _last_success(settings: Settings) -> dict:
    p = _state_path(settings)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_success(settings: Settings, manifest: RunManifest) -> None:
    state = {"run_id": manifest.run_id, "finished_at": manifest.finished_at, "source": manifest.source}
    _state_path(settings).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def cleanup_old(settings: Settings) -> None:
    """Borra corridas y logs más viejos que retention_days (0 = nunca)."""
    if not settings.retention_days:
        return
    limit = time.time() - settings.retention_days * 86400
    runs = settings.data_dir / "runs"
    for d in runs.iterdir() if runs.exists() else []:
        if d.is_dir() and d.stat().st_mtime < limit:
            shutil.rmtree(d, ignore_errors=True)
    for f in settings.log_dir.glob("*.log") if settings.log_dir.exists() else []:
        if f.stat().st_mtime < limit:
            f.unlink(missing_ok=True)


def run(
    settings: Settings,
    run_id: str,
    dry_run: bool = False,
    local_file: Path | None = None,
    only_sheets: list[str] | None = None,
) -> RunManifest:
    manifest = RunManifest(run_id=run_id, ambiente=settings.ambiente, dry_run=dry_run)
    try:
        with run_lock(settings.data_dir):
            _run(settings, manifest, local_file, only_sheets)
    except AlreadyRunningError as exc:
        manifest.status, manifest.error = "failed", str(exc)
        log.error("%s", exc)
        return manifest  # no se escribe manifiesto: la otra corrida es la dueña
    for line in summary_lines(manifest):
        log.info(line)
    try:
        append_run_log(settings.data_dir / "registro_corridas.csv", manifest)
    except OSError as exc:
        log.warning("No se pudo escribir registro_corridas.csv: %s", exc)
    if manifest.status == "ok" and not dry_run and not manifest.skipped:
        _save_success(settings, manifest)
    try:
        cleanup_old(settings)
    except OSError as exc:
        log.warning("No se pudo limpiar corridas viejas: %s", exc)
    return manifest


def _run(
    settings: Settings,
    manifest: RunManifest,
    local_file: Path | None,
    only_sheets: list[str] | None,
) -> None:
    run_dir = settings.data_dir / "runs" / manifest.run_id
    sheets = settings.sheets
    all_sheets = settings.all_sheets
    if only_sheets:  # --sheet limita la corrida a esas pestañas
        by_name = {s.sheet: s for s in settings.sheets}
        sheets = [by_name.get(n, SheetConfig(sheet=n, table=n)) for n in only_sheets]
        all_sheets = False

    try:
        # 1. Origen: descarga automática de SharePoint (--file solo para pruebas)
        if local_file:
            xlsx, meta = local_file.read_bytes(), {"name": local_file.name, "local": True}
        else:
            xlsx, meta = sharepoint.client_from_settings(settings).download_file()
        manifest.source = meta

        # 1b. ¿El archivo cambió desde la última corrida exitosa?
        last = _last_success(settings).get("source", {})
        if not local_file and last.get("eTag") and last.get("eTag") == meta.get("eTag"):
            msg = f"El archivo no cambió desde la corrida {_last_success(settings).get('run_id')}"
            if settings.if_unchanged == "fail":
                raise RuntimeError(msg)
            if settings.if_unchanged == "skip":
                log.warning("%s; no se envía nada (if_unchanged=skip)", msg)
                manifest.status, manifest.skipped = "ok", True
                return
            log.warning("%s; se envía de todos modos (if_unchanged=send)", msg)

        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "source.xlsx").write_bytes(xlsx)   # copia exacta de lo leído

        # 2. Excel -> CSV (valida todo antes de enviar nada)
        results = excel_to_csvs(
            xlsx,
            sheets,
            run_dir / "csv",
            all_sheets,
            settings.exclude_sheets,
            include_hidden=settings.include_hidden_sheets,
            allow_empty=settings.allow_empty_sheets,
        )
        manifest.sheets = [SheetControl(r.sheet, r.table, rows_file=r.rows) for r in results]
        manifest.save(run_dir)

        if manifest.dry_run:
            log.info("DRY RUN: no se envía nada a Coupa")
            manifest.status = "ok"
            return

        # 3. Envío a Coupa: un lote JSON a la vez, esperando a que termine
        client = CoupaClient(
            settings.coupa, secrets.get_secret(secrets.COUPA_API_KEY, settings.ambiente)
        )
        batch_log = settings.data_dir / "registro_lotes.csv"
        # Límites compartidos por toda la corrida: si Coupa rechaza por tamaño, bajan para todo
        limits = Limits(settings.coupa.batch_rows, int(settings.coupa.max_batch_mb * 1024 * 1024))
        session_id = client.open_session()
        manifest.coupa_session_id = session_id
        manifest.save(run_dir)
        try:
            for res, ctl in zip(results, manifest.sheets, strict=True):
                counter = itertools.count(1)

                def send(chunk, body, nota, res=res, ctl=ctl, counter=counter):
                    batch = client.put_batch(session_id, res.table, len(chunk), body, next(counter), nota)
                    ctl.rows_sent += batch.rows
                    batch = client.wait_batch(batch)
                    entry = asdict(batch)
                    ctl.batches.append(entry)
                    append_batch_log(batch_log, manifest.run_id, session_id, entry)
                    log.info("[%s] lote %d (%s): %d filas, %s bytes, %s en %ss%s",
                             res.sheet, batch.n, batch.operation_id, batch.rows, f"{batch.bytes:,}",
                             batch.status, batch.seconds, f" ({nota})" if nota else "")
                    manifest.save(run_dir)

                # Se lee por bloques de batch_rows para no cargar la pestaña completa en memoria
                for records in iter_record_batches(res.csv_path, settings.coupa.batch_rows):
                    send_adaptive(send, records, limits)
        finally:
            client.close_session(session_id)
        if limits.splits:
            log.warning("Se partieron %d lote(s) por tamaño. Límite final: %d filas / %s bytes; "
                        "conviene ajustar batch_rows / max_batch_mb en settings.toml",
                        limits.splits, limits.max_rows, f"{limits.max_bytes:,}")

        # 4. Resultado de la sesión: resumen, estado y errores, tal como los da Coupa
        summary = client.summary(session_id)
        (run_dir / "coupa_summary.json").write_text(_dump(summary), encoding="utf-8")
        (run_dir / "coupa_status.json").write_text(_dump(client.status_pages(session_id)), encoding="utf-8")
        error_pages = client.error_pages(session_id)
        (run_dir / "coupa_errors.json").write_text(_dump(error_pages), encoding="utf-8")
        manifest.rejected_rows = write_rejected(
            run_dir / "rechazados.csv", [it for p in error_pages for it in page_items(p)]
        )
        manifest.coupa_success, manifest.coupa_errors = summary_totals(summary)
        log.info("Coupa: %s exitosas, %s con error (archivo %d, enviadas %d)",
                 manifest.coupa_success, manifest.coupa_errors, manifest.rows_file, manifest.rows_sent)

        pending = [b for s in manifest.sheets for b in s.batches if b["status"] != "terminado"]
        if pending:
            raise RuntimeError(f"{len(pending)} lote(s) no terminaron a tiempo")
        if manifest.cuadra is None:
            raise RuntimeError("No se reconocieron los totales en coupa_summary.json; revisar el formato")
        if not manifest.cuadra:
            raise RuntimeError(
                f"No cuadra: archivo {manifest.rows_file}, enviadas {manifest.rows_sent}, "
                f"exitosas {manifest.coupa_success}, con error {manifest.coupa_errors}"
            )
        manifest.status = "ok"
    except Exception as exc:
        manifest.status = "failed"
        manifest.error = f"{type(exc).__name__}: {exc}"
        log.exception("La corrida falló")
    finally:
        manifest.finished_at = now_iso()
        if run_dir.exists():
            manifest.save(run_dir)


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)

