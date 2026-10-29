"""Carga y validación de la configuración (sin secretos)."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

# Ruta por defecto: <repo>/config/settings.toml. Se puede cambiar con la
# variable de entorno COUPA_INGEST_CONFIG o con --config.
ENV_CONFIG = "COUPA_INGEST_CONFIG"
PLACEHOLDER = "PENDIENTE"


def default_config_path() -> Path:
    env = os.environ.get(ENV_CONFIG)
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "config" / "settings.toml"


class SharePointConfig(BaseModel):
    tenant_id: str
    client_id: str
    hostname: str
    site_path: str
    file_path: str
    timeout_s: int = 120


class CoupaConfig(BaseModel):
    base_url: HttpUrl
    model_id: str            # modelo destino en llama.ai; va como fileId al abrir la sesión
    timeout_s: int = 60
    batch_rows: int = Field(5000, gt=0)
    poll_interval_s: int = 10
    poll_max_min: int = 30


class SheetConfig(BaseModel):
    sheet: str
    table: str
    key: list[str] = Field(default_factory=list)


class Settings(BaseModel):
    ambiente: str = "dev"
    data_dir: Path = Path("data")
    log_dir: Path = Path("logs")
    # Días que se conservan data/runs/<run_id>/ y logs/. 0 = no borrar nunca.
    retention_days: int = Field(90, ge=0)
    # Qué hacer si el archivo no cambió desde la última corrida exitosa.
    if_unchanged: Literal["send", "skip", "fail"] = "send"
    sharepoint: SharePointConfig
    coupa: CoupaConfig
    # true: se procesan todas las pestañas del libro (menos exclude_sheets);
    # [[sheets]] solo sobreescribe tabla destino y llaves de algunas.
    all_sheets: bool = True
    include_hidden_sheets: bool = False
    allow_empty_sheets: bool = False
    exclude_sheets: list[str] = Field(default_factory=list)
    sheets: list[SheetConfig] = Field(default_factory=list)

    def placeholders(self) -> list[str]:
        """Campos que aún tienen valores de ejemplo."""
        found = []
        sp = self.sharepoint
        for name in ("tenant_id", "client_id"):
            if set(getattr(sp, name).replace("-", "")) == {"0"}:
                found.append(f"sharepoint.{name}")
        if PLACEHOLDER in sp.file_path:
            found.append("sharepoint.file_path")
        if PLACEHOLDER in str(self.coupa.base_url).upper():
            found.append("coupa.base_url")
        if PLACEHOLDER in self.coupa.model_id.upper():
            found.append("coupa.model_id")
        return found


def load_settings(path: Path) -> Settings:
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    settings = Settings.model_validate(raw)
    # Rutas relativas se resuelven contra la raíz del proyecto (padre de config/)
    root = path.resolve().parent.parent
    if not settings.data_dir.is_absolute():
        settings.data_dir = root / settings.data_dir
    if not settings.log_dir.is_absolute():
        settings.log_dir = root / settings.log_dir
    return settings
