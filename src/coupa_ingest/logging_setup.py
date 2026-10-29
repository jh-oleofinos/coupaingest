"""Logs por corrida: consola + archivo logs/<run_id>.log, cada línea con run_id."""

from __future__ import annotations

import logging
from pathlib import Path


class _RunIdFilter(logging.Filter):
    def __init__(self, run_id: str) -> None:
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = self.run_id
        return True


def setup_logging(log_dir: Path, run_id: str, level: int = logging.INFO) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{run_id}.log"
    fmt = logging.Formatter("%(asctime)s %(levelname)s run_id=%(run_id)s %(name)s - %(message)s")

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    for handler in (logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")):
        handler.setFormatter(fmt)
        handler.addFilter(_RunIdFilter(run_id))
        root.addHandler(handler)
    # Evita que urllib3/msal llenen el log con detalles de HTTP
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("msal").setLevel(logging.WARNING)
    return log_file
