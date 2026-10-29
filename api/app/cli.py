"""Administración por consola.

    python -m app.cli sembrar-roles
    python -m app.cli crear-usuario --correo ana@oleofinos.com.mx --nombre "Ana Pérez" --rol lector
    python -m app.cli asignar-rol --correo ... --rol administrador
    python -m app.cli quitar-rol --correo ... --rol lector
    python -m app.cli desactivar --correo ...      |  activar
    python -m app.cli desbloquear --correo ...
    python -m app.cli cambiar-contrasena --correo ...
    python -m app.cli crear-tablas                 (solo desarrollo con SQLite)
    python -m app.cli datos-ejemplo                (solo desarrollo; datos inventados)

Las contraseñas se piden en consola (getpass); nunca van como argumento.
"""

import argparse
import getpass
import random
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db
from app.config import get_settings
from app.models import Commodity, Corrida, Permiso, Precio, Rol, Usuario
from app.security import passwords
from app.security.catalogo import PERMISOS, ROLES


def _sesion() -> Session:
    settings = get_settings()
    engine = db.iniciar(settings.DATABASE_URL.get_secret_value())  # type: ignore[union-attr]
    return Session(engine, expire_on_commit=False)


def _usuario(s: Session, correo: str) -> Usuario:
    u = s.scalar(select(Usuario).where(Usuario.correo == correo.lower()))
    if u is None:
        sys.exit(f"No existe el usuario {correo}.")
    return u


def _rol(s: Session, codigo: str) -> Rol:
    r = s.scalar(select(Rol).where(Rol.codigo == codigo))
    if r is None:
        sys.exit(f"No existe el rol {codigo}. Corre primero sembrar-roles.")
    return r


def _pedir_contrasena(correo: str) -> str:
    while True:
        c1 = getpass.getpass("Contraseña: ")
        errores = passwords.validar_politica(c1, correo)
        if errores:
            print("\n".join(errores))
            continue
        if c1 != getpass.getpass("Repite la contraseña: "):
            print("No coinciden.")
            continue
        return c1


def sembrar_roles(s: Session) -> None:
    permisos = {p.codigo: p for p in s.scalars(select(Permiso)).all()}
    for codigo, desc in PERMISOS.items():
        if codigo not in permisos:
            permisos[codigo] = Permiso(codigo=codigo, descripcion=desc)
            s.add(permisos[codigo])
        else:
            permisos[codigo].descripcion = desc
    for codigo, datos in ROLES.items():
        rol = s.scalar(select(Rol).where(Rol.codigo == codigo))
        if rol is None:
            rol = Rol(codigo=codigo, nombre=datos["nombre"], descripcion=datos["descripcion"])
            s.add(rol)
        rol.nombre, rol.descripcion = datos["nombre"], datos["descripcion"]
        rol.permisos = [permisos[p] for p in datos["permisos"]]
    s.commit()
    print(f"Roles: {', '.join(ROLES)}. Permisos: {', '.join(PERMISOS)}.")


def crear_usuario(s: Session, correo: str, nombre: str, rol: str, sin_contrasena: bool) -> None:
    correo = correo.lower()
    if s.scalar(select(Usuario).where(Usuario.correo == correo)):
        sys.exit("Ese correo ya existe.")
    u = Usuario(correo=correo, nombre=nombre.strip(), roles=[_rol(s, rol)])
    if not sin_contrasena:
        u.hash_contrasena = passwords.generar_hash(_pedir_contrasena(correo))
    s.add(u)
    s.commit()
    print(f"Usuario {correo} creado con rol {rol}.")


def datos_ejemplo(s: Session) -> None:
    """Series INVENTADAS para desarrollar la interfaz. No representan precios reales."""
    if not get_settings().es_dev:
        sys.exit("datos-ejemplo solo se permite en desarrollo.")
    catalogo = [
        ("aceite_soya", "Aceite de soya (ejemplo)", "USD/t", 1050),
        ("aceite_palma", "Aceite de palma (ejemplo)", "USD/t", 930),
        ("pasta_soya", "Pasta de soya (ejemplo)", "USD/t", 340),
        ("maiz", "Maíz (ejemplo)", "USD/t", 210),
    ]
    rng = random.Random(42)  # noqa: S311 - datos de ejemplo, no criptografía
    hoy = date.today()
    inicio = hoy - timedelta(days=730)
    corrida = Corrida(
        proceso="commodities",
        inicio=datetime.combine(hoy, time(13, 40)),
        fin=datetime.combine(hoy, time(13, 45)),
        estado="exitosa",
        filas=0,
        mensaje="Datos de ejemplo",
    )
    s.add(corrida)
    s.flush()
    filas = 0
    for orden, (codigo, nombre, unidad, base) in enumerate(catalogo):
        c = s.scalar(select(Commodity).where(Commodity.codigo == codigo))
        if c is None:
            c = Commodity(codigo=codigo, nombre=nombre, unidad=unidad, orden=orden)
            s.add(c)
            s.flush()
        valor = float(base)
        d = inicio
        while d <= hoy:
            if d.weekday() < 5:
                valor = max(valor * (1 + rng.gauss(0.0002, 0.012)), base * 0.4)
                s.add(
                    Precio(
                        commodity_id=c.id,
                        fecha=d,
                        valor=Decimal(f"{valor:.2f}"),
                        corrida_id=corrida.id,
                    )
                )
                filas += 1
            d += timedelta(days=1)
    corrida.filas = filas
    s.commit()
    print(f"{filas} precios de ejemplo cargados.")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("crear-tablas")
    sub.add_parser("sembrar-roles")
    sub.add_parser("datos-ejemplo")
    c = sub.add_parser("crear-usuario")
    c.add_argument("--correo", required=True)
    c.add_argument("--nombre", required=True)
    c.add_argument("--rol", required=True, choices=list(ROLES))
    c.add_argument("--sin-contrasena", action="store_true", help="Solo entrará con Entra ID")
    for nombre in ("asignar-rol", "quitar-rol"):
        x = sub.add_parser(nombre)
        x.add_argument("--correo", required=True)
        x.add_argument("--rol", required=True, choices=list(ROLES))
    for nombre in ("activar", "desactivar", "desbloquear", "cambiar-contrasena"):
        sub.add_parser(nombre).add_argument("--correo", required=True)
    a = p.parse_args(argv)

    s = _sesion()
    if a.cmd == "crear-tablas":
        if not str(s.get_bind().url).startswith("sqlite"):
            sys.exit("En SQL Server las tablas se crean con los scripts de db/sqlserver.")
        db.Base.metadata.create_all(s.get_bind())
        print("Tablas creadas.")
    elif a.cmd == "sembrar-roles":
        sembrar_roles(s)
    elif a.cmd == "datos-ejemplo":
        datos_ejemplo(s)
    elif a.cmd == "crear-usuario":
        crear_usuario(s, a.correo, a.nombre, a.rol, a.sin_contrasena)
    else:
        u = _usuario(s, a.correo)
        if a.cmd == "asignar-rol":
            r = _rol(s, a.rol)
            if r not in u.roles:
                u.roles.append(r)
        elif a.cmd == "quitar-rol":
            u.roles = [r for r in u.roles if r.codigo != a.rol]
            u.version_sesion += 1
        elif a.cmd == "activar":
            u.activo = True
        elif a.cmd == "desactivar":
            u.activo = False
            u.version_sesion += 1
        elif a.cmd == "desbloquear":
            u.bloqueado_hasta, u.intentos_fallidos = None, 0
        elif a.cmd == "cambiar-contrasena":
            u.hash_contrasena = passwords.generar_hash(_pedir_contrasena(u.correo))
            u.bloqueado_hasta, u.intentos_fallidos = None, 0
            u.version_sesion += 1
        s.commit()
        print("Listo.")


if __name__ == "__main__":
    main()
