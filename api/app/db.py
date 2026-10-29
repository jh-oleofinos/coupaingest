"""Conexión a la base.

- Producción: SQL Server (Express en el Windows Server, después Azure SQL). Los esquemas
  `app`, `dat` y `ctl` se crean con los scripts de `db/sqlserver`.
- Desarrollo y pruebas: SQLite. Como SQLite no tiene esquemas, cada esquema se adjunta
  como un archivo aparte (ATTACH), así los modelos son los mismos en ambos motores.
"""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

ESQUEMAS = ("app", "dat", "ctl")


class Base(DeclarativeBase):
    pass


def _configurar_sqlite(engine: Engine, ruta_principal: str) -> None:
    en_memoria = ruta_principal in ("", ":memory:")

    @event.listens_for(engine, "connect")
    def _al_conectar(conexion_dbapi, _registro) -> None:  # pragma: no cover - trivial
        cursor = conexion_dbapi.cursor()
        for esquema in ESQUEMAS:
            if en_memoria:
                destino = ":memory:"
            else:
                p = Path(ruta_principal)
                destino = str(p.with_name(f"{p.stem}_{esquema}{p.suffix}"))
            cursor.execute(f"ATTACH DATABASE '{destino}' AS {esquema}")  # noqa: S608 - valores fijos
        cursor.execute("PRAGMA foreign_keys=ON")
        if not en_memoria:
            cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def crear_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        ruta = url.split("///", 1)[1] if "///" in url else ""
        if ruta and ruta != ":memory:":
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
            engine = create_engine(url, connect_args={"check_same_thread": False})
        else:
            engine = create_engine(
                "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
            )
        _configurar_sqlite(engine, ruta)
        return engine
    # SQL Server: pool moderado, verifica conexiones antes de usarlas.
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def iniciar(url: str) -> Engine:
    global _engine, _SessionLocal
    _engine = crear_engine(url)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("La base no está inicializada.")
    return _engine


def get_db() -> Iterator[Session]:
    if _SessionLocal is None:
        raise RuntimeError("La base no está inicializada.")
    sesion = _SessionLocal()
    try:
        yield sesion
    finally:
        sesion.close()
