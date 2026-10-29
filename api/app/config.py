"""Configuración de la API.

Orden de lectura de cada valor:
1. Variable de entorno (o archivo .env en desarrollo).
2. Para secretos: Administrador de credenciales de Windows vía `keyring`
   (servicio "oleoweb"), con la cuenta de servicio que corre la API.

Nunca se escriben secretos en código ni en archivos versionados.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICIO_KEYRING = "oleoweb"
SECRETOS = ("DATABASE_URL", "API_TOKEN_SECRET")


def _leer_keyring(nombre: str) -> str | None:
    try:
        import keyring

        return keyring.get_password(SERVICIO_KEYRING, nombre)
    except Exception:  # noqa: BLE001 - sin backend de keyring disponible
        return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENTORNO: Literal["dev", "prd"] = "dev"

    # Ej. SQL Server: mssql+pyodbc://@OLF05ZGTWB01\\SQLEXPRESS/commodities?driver=ODBC+Driver+18+for+SQL+Server&Trusted_Connection=yes&Encrypt=yes
    # Ej. desarrollo: sqlite:///./dev/oleoweb.db
    DATABASE_URL: SecretStr | None = None

    # Secreto compartido con el servidor de Next.js para firmar los tokens de servicio (HS256).
    API_TOKEN_SECRET: SecretStr | None = None
    API_TOKEN_ISSUER: str = "oleoweb-web"  # noqa: S105 - no es secreto
    API_TOKEN_AUDIENCE: str = "oleoweb-api"  # noqa: S105 - no es secreto
    API_TOKEN_MAX_SEGUNDOS: int = 120

    LOGIN_MAX_INTENTOS: int = Field(default=5, ge=3, le=20)
    LOGIN_BLOQUEO_MINUTOS: int = Field(default=15, ge=1, le=1440)

    @model_validator(mode="before")
    @classmethod
    def _secretos_desde_keyring(cls, datos: dict) -> dict:
        for nombre in SECRETOS:
            if not datos.get(nombre):
                valor = _leer_keyring(nombre)
                if valor:
                    datos[nombre] = valor
        return datos

    @model_validator(mode="after")
    def _validar(self) -> "Settings":
        if self.DATABASE_URL is None:
            raise ValueError(
                "Falta DATABASE_URL (variable de entorno o Administrador de credenciales)."
            )
        secreto = self.API_TOKEN_SECRET.get_secret_value() if self.API_TOKEN_SECRET else ""
        if len(secreto) < 32:
            raise ValueError("API_TOKEN_SECRET debe existir y tener al menos 32 caracteres.")
        if self.ENTORNO == "prd" and self.DATABASE_URL.get_secret_value().startswith("sqlite"):
            raise ValueError("En prd la base debe ser SQL Server, no SQLite.")
        return self

    @property
    def es_dev(self) -> bool:
        return self.ENTORNO == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
