"""Carga y validación de la configuración (sin secretos)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl


class SharePointConfig(BaseModel):
    tenant_id: str
    client_id: str
    hostname: str
    site_path: str
    file_path: str


class CoupaConfig(BaseModel):
    base_url: HttpUrl
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
    sharepoint: SharePointConfig
    coupa: CoupaConfig
    # true: se procesan todas las pestañas del libro (menos exclude_sheets);
    # [[sheets]] solo sobreescribe tabla destino y llaves de algunas.
    all_sheets: bool = True
    exclude_sheets: list[str] = Field(default_factory=list)
    sheets: list[SheetConfig] = Field(default_factory=list)


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
