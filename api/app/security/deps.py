"""Dependencias de seguridad para los endpoints."""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import BitacoraAcceso, Usuario
from app.security import tokens

NO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado.",
    headers={"WWW-Authenticate": "Bearer"},
)
SIN_PERMISO = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permiso.")


@dataclass(frozen=True)
class UsuarioContexto:
    id: int
    correo: str
    nombre: str
    roles: tuple[tuple[str, str], ...]  # (codigo, nombre)
    permisos: frozenset[str]
    version_sesion: int


def contexto_de(usuario: Usuario) -> UsuarioContexto:
    roles = tuple(sorted((r.codigo, r.nombre) for r in usuario.roles))
    permisos = frozenset(p.codigo for r in usuario.roles for p in r.permisos)
    return UsuarioContexto(
        usuario.id, usuario.correo, usuario.nombre, roles, permisos, usuario.version_sesion
    )


def _claims(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> tokens.Claims:
    if not authorization or not authorization.startswith("Bearer "):
        raise NO_AUTENTICADO
    try:
        return tokens.validar(authorization.removeprefix("Bearer ").strip(), settings)
    except tokens.TokenInvalido:
        raise NO_AUTENTICADO from None


def llamada_de_servicio(claims: tokens.Claims = Depends(_claims)) -> tokens.Claims:
    """Llamadas del servidor web que todavía no tienen usuario (login)."""
    if claims.tipo != "servicio":
        raise NO_AUTENTICADO
    return claims


def usuario_actual(
    claims: tokens.Claims = Depends(_claims), db: Session = Depends(get_db)
) -> UsuarioContexto:
    if claims.tipo != "usuario" or claims.usuario_id is None:
        raise NO_AUTENTICADO
    usuario = db.get(Usuario, claims.usuario_id)
    # Usuario dado de baja: pierde el acceso en la siguiente petición, aunque su sesión siga viva.
    if usuario is None or not usuario.activo or usuario.version_sesion != claims.version_sesion:
        raise NO_AUTENTICADO
    return contexto_de(usuario)


def requiere(permiso: str) -> Callable[..., UsuarioContexto]:
    def _verificar(
        usuario: UsuarioContexto = Depends(usuario_actual), db: Session = Depends(get_db)
    ) -> UsuarioContexto:
        if permiso not in usuario.permisos:
            db.add(
                BitacoraAcceso(
                    usuario_id=usuario.id, evento="acceso_denegado", detalle=permiso[:200]
                )
            )
            db.commit()
            raise SIN_PERMISO
        return usuario

    return _verificar
