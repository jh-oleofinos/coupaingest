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
