"""Manifiesto por corrida: qué se leyó, qué se envió y la cifra de control.

Se guarda en data/runs/<run_id>/manifest.json. Es la base para pasar después
a la tabla ctl de la plataforma Azure.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class SheetControl:
    sheet: str
    table: str
    rows_file: int = 0
    rows_sent: int = 0
    batches: list[dict] = field(default_factory=list)

    @property
    def cuadra(self) -> bool:
        return self.rows_file == self.rows_sent


@dataclass
class RunManifest:
    run_id: str
    ambiente: str
    dry_run: bool
    started_at: str = field(default_factory=now_iso)
    finished_at: str | None = None
    status: str = "running"        # running | ok | failed
    skipped: bool = False          # true si no se envió porque el archivo no cambió
    error: str | None = None
    source: dict = field(default_factory=dict)
    coupa_session_id: str | None = None
    # Totales que reporta Coupa en el resumen de la sesión (None = no se pudo leer)
    coupa_success: int | None = None
    coupa_errors: int | None = None
    rejected_rows: int | None = None   # registros en el endpoint de errores (rechazados.csv)
    sheets: list[SheetControl] = field(default_factory=list)

    @property
    def rows_file(self) -> int:
        return sum(s.rows_file for s in self.sheets)

    @property
    def rows_sent(self) -> int:
        return sum(s.rows_sent for s in self.sheets)

    @property
    def cuadra(self) -> bool | None:
        """Filas en archivo = enviadas = exitosas en Coupa, y cero errores."""
        if self.coupa_success is None or self.coupa_errors is None:
            return None
        return self.rows_file == self.rows_sent == self.coupa_success and self.coupa_errors == 0

    def save(self, run_dir: Path) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "manifest.json"
        data = asdict(self)
        data.update(rows_file=self.rows_file, rows_sent=self.rows_sent, cuadra=self.cuadra)
        for s, obj in zip(data["sheets"], self.sheets):
            s["cuadra"] = obj.cuadra
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


BATCH_LOG_FIELDS = ("run_id", "session_id", "table", "n", "rows", "http_status", "operation_id",
                    "sent_at", "finished_at", "seconds", "polls", "status")


def append_batch_log(path: Path, run_id: str, session_id: str, batch: dict) -> None:
    """Registro acumulado de lotes (data/registro_lotes.csv); no lo borra la retención."""
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=BATCH_LOG_FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({**batch, "run_id": run_id, "session_id": session_id})


RUN_LOG_FIELDS = ("run_id", "ambiente", "dry_run", "started_at", "finished_at", "status", "skipped",
                  "archivo", "pestanas", "filas_archivo", "filas_enviadas", "exitosas_coupa",
                  "errores_coupa", "rechazados", "cuadra", "coupa_session_id", "error")


def append_run_log(path: Path, m: RunManifest) -> None:
    """Una línea por corrida en data/registro_corridas.csv; no lo borra la retención."""
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "run_id": m.run_id, "ambiente": m.ambiente, "dry_run": m.dry_run,
        "started_at": m.started_at, "finished_at": m.finished_at, "status": m.status,
        "skipped": m.skipped, "archivo": m.source.get("name"), "pestanas": len(m.sheets),
        "filas_archivo": m.rows_file, "filas_enviadas": m.rows_sent,
        "exitosas_coupa": m.coupa_success, "errores_coupa": m.coupa_errors,
        "rechazados": m.rejected_rows, "cuadra": m.cuadra,
        "coupa_session_id": m.coupa_session_id, "error": m.error,
    }
    with path.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=RUN_LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def summary_lines(m: RunManifest) -> list[str]:
    """Resumen legible de la corrida para el log."""
    lines = [
        f"===== RESUMEN {m.run_id} · {m.status.upper()}" + (" (sin envío: archivo sin cambios)" if m.skipped else ""),
        f"Archivo: {m.source.get('name')} · ambiente {m.ambiente}" + (" · DRY RUN" if m.dry_run else ""),
    ]
    for s in m.sheets:
        terminados = sum(1 for b in s.batches if b.get("status") == "terminado")
        lines.append(f"  {s.sheet} -> {s.table}: {s.rows_file} en archivo, {s.rows_sent} enviadas, "
                     f"lotes {terminados}/{len(s.batches)} terminados")
    def v(x):
        return "-" if x is None else x

    lines.append(f"Total: {m.rows_file} en archivo, {m.rows_sent} enviadas, "
                 f"{v(m.coupa_success)} exitosas en Coupa, {v(m.coupa_errors)} con error, "
                 f"{v(m.rejected_rows)} rechazados · cuadra: {v(m.cuadra)}")
    if m.error:
        lines.append(f"Error: {m.error}")
    return lines


def write_rejected(path: Path, items: list) -> int:
    """Rechazados de Coupa a CSV: una fila por error, columnas = campos que traiga Coupa."""
    rows = []
    for it in items:
        if isinstance(it, dict):
            rows.append({k: v if isinstance(v, str | int | float | bool) or v is None
                         else json.dumps(v, ensure_ascii=False) for k, v in it.items()})
        else:
            rows.append({"detalle": json.dumps(it, ensure_ascii=False)})
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields or ["detalle"])
        w.writeheader()
        w.writerows(rows)
    return len(rows)
