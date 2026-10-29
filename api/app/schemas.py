from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Salida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth


class LoginEntrada(BaseModel):
    correo: EmailStr
    contrasena: str = Field(min_length=1, max_length=128)


class EntraEntrada(BaseModel):
    correo: EmailStr
    oid: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")


class RolSalida(Salida):
    codigo: str
    nombre: str


class PerfilSalida(Salida):
    id: int
    correo: str
    nombre: str
    roles: list[RolSalida]
    permisos: list[str]
    version_sesion: int


# ---------------------------------------------------------------- commodities


class PuntoSerie(Salida):
    fecha: date
    valor: Decimal


class ResumenCommodity(Salida):
    codigo: str
    nombre: str
    unidad: str
    ultimo: PuntoSerie | None
    anterior: PuntoSerie | None
    variacion: Decimal | None
    variacion_pct: Decimal | None


class SerieSalida(Salida):
    codigo: str
    nombre: str
    unidad: str
    puntos: list[PuntoSerie]


class CorridaSalida(Salida):
    estado: str
    inicio: datetime
    fin: datetime | None


class EstadoCargaSalida(Salida):
    ultima: CorridaSalida | None
    ultima_exitosa: CorridaSalida | None


# ---------------------------------------------------------------- usuarios


class UsuarioSalida(Salida):
    id: int
    correo: str
    nombre: str
    activo: bool
    roles: list[RolSalida]
    ultimo_acceso: datetime | None
    bloqueado: bool
