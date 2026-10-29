"""Manifiesto por corrida: qué se leyó, qué se envió y la cifra de control.

Se guarda en data/runs/<run_id>/manifest.json. Es la base para pasar después
a la tabla ctl de la plataforma Azure.
"""

from __future__ import annotations

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
    rows_accepted: int | None = None   # lo reporta Coupa en el resumen
    batches: list[dict] = field(default_factory=list)

    @property
    def cuadra(self) -> bool | None:
        if self.rows_accepted is None:
            return None
        return self.rows_file == self.rows_sent == self.rows_accepted


@dataclass
class RunManifest:
    run_id: str
    ambiente: str
    dry_run: bool
    started_at: str = field(default_factory=now_iso)
    finished_at: str | None = None
    status: str = "running"        # running | ok | failed
    error: str | None = None
    source: dict = field(default_factory=dict)
    coupa_session_id: str | None = None
    sheets: list[SheetControl] = field(default_factory=list)

    def save(self, run_dir: Path) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "manifest.json"
        data = asdict(self)
        for s, obj in zip(data["sheets"], self.sheets):
            s["cuadra"] = obj.cuadra
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
