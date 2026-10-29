"""Modelos. Deben coincidir con los scripts de db/sqlserver (fuente de verdad en el servidor).

Fechas y horas se guardan en UTC sin zona; la web las muestra en America/Mexico_City.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# SQLite solo hace autoincremento con INTEGER; SQL Server usa BIGINT IDENTITY.
BigId = BigInteger().with_variant(Integer(), "sqlite")


def ahora_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


# ---------------------------------------------------------------- app: seguridad


class RolPermiso(Base):
    __tablename__ = "rol_permiso"
    __table_args__ = {"schema": "app"}

    rol_id: Mapped[int] = mapped_column(ForeignKey("app.rol.id"), primary_key=True)
    permiso_id: Mapped[int] = mapped_column(ForeignKey("app.permiso.id"), primary_key=True)


class UsuarioRol(Base):
    __tablename__ = "usuario_rol"
    __table_args__ = {"schema": "app"}

    usuario_id: Mapped[int] = mapped_column(ForeignKey("app.usuario.id"), primary_key=True)
    rol_id: Mapped[int] = mapped_column(ForeignKey("app.rol.id"), primary_key=True)


class Permiso(Base):
    __tablename__ = "permiso"
    __table_args__ = {"schema": "app"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(100), unique=True)
    descripcion: Mapped[str] = mapped_column(String(200))


class Rol(Base):
    __tablename__ = "rol"
    __table_args__ = {"schema": "app"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True)
    nombre: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str] = mapped_column(String(200), default="")

    permisos: Mapped[list[Permiso]] = relationship(secondary="app.rol_permiso", lazy="selectin")


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = (
        # Único solo entre los que ya lo tienen (SQL Server admite un solo NULL en UNIQUE).
        Index(
            "ux_usuario_entra_oid",
            "entra_oid",
            unique=True,
            mssql_where=text("entra_oid IS NOT NULL"),
            sqlite_where=text("entra_oid IS NOT NULL"),
        ),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    correo: Mapped[str] = mapped_column(String(254), unique=True)  # siempre en minúsculas
    nombre: Mapped[str] = mapped_column(String(200))
    # Nulo = solo puede entrar con Entra ID.
    hash_contrasena: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Identificador inmutable del usuario en Entra ID; se vincula en su primer inicio de sesión.
    entra_oid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Se incrementa al cerrar sesión, cambiar contraseña o desactivar: invalida todas las sesiones.
    version_sesion: Mapped[int] = mapped_column(Integer, default=0)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora_utc)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, default=ahora_utc, onupdate=ahora_utc
    )

    roles: Mapped[list[Rol]] = relationship(secondary="app.usuario_rol", lazy="selectin")


class BitacoraAcceso(Base):
    __tablename__ = "bitacora_acceso"
    __table_args__ = {"schema": "app"}

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora_utc)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("app.usuario.id"), nullable=True)
    correo_intentado: Mapped[str | None] = mapped_column(String(254), nullable=True)
    # login_ok | login_fallido | login_bloqueado | login_rechazado | acceso_denegado
    evento: Mapped[str] = mapped_column(String(30))
    proveedor: Mapped[str | None] = mapped_column(String(20), nullable=True)  # credenciales | entra
    detalle: Mapped[str | None] = mapped_column(String(200), nullable=True)


# ---------------------------------------------------------------- dat: commodities


class Commodity(Base):
    __tablename__ = "commodity"
    __table_args__ = {"schema": "dat"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True)
    nombre: Mapped[str] = mapped_column(String(100))
    unidad: Mapped[str] = mapped_column(String(30))  # ej. USD/t
    orden: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Precio(Base):
    """Historia de precios. Solo se agregan filas: si la fuente corrige un valor,
    queda una versión nueva con otra fecha_carga y se usa la más reciente."""

    __tablename__ = "precio"
    __table_args__ = (
        UniqueConstraint("commodity_id", "fecha", "fecha_carga", name="uq_precio_version"),
        {"schema": "dat"},
    )

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    commodity_id: Mapped[int] = mapped_column(ForeignKey("dat.commodity.id"))
    fecha: Mapped[date] = mapped_column(Date)
    valor: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    fecha_carga: Mapped[datetime] = mapped_column(DateTime, default=ahora_utc)
    corrida_id: Mapped[int | None] = mapped_column(ForeignKey("ctl.corrida.id"), nullable=True)


# ---------------------------------------------------------------- ctl: control de cargas


class Corrida(Base):
    __tablename__ = "corrida"
    __table_args__ = {"schema": "ctl"}

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    proceso: Mapped[str] = mapped_column(String(50))
    inicio: Mapped[datetime] = mapped_column(DateTime, default=ahora_utc)
    fin: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    estado: Mapped[str] = mapped_column(String(20))  # en_curso | exitosa | fallida
    filas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mensaje: Mapped[str | None] = mapped_column(String(500), nullable=True)
