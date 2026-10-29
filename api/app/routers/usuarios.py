from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario, ahora_utc
from app.schemas import RolSalida, UsuarioSalida
from app.security.deps import UsuarioContexto, requiere

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("", response_model=list[UsuarioSalida])
def listar(
    _: UsuarioContexto = Depends(requiere("usuarios.administrar")),
    db: Session = Depends(get_db),
) -> list[UsuarioSalida]:
    ahora = ahora_utc()
    return [
        UsuarioSalida(
            id=u.id,
            correo=u.correo,
            nombre=u.nombre,
            activo=u.activo,
            roles=[RolSalida(codigo=r.codigo, nombre=r.nombre) for r in u.roles],
            ultimo_acceso=u.ultimo_acceso,
            bloqueado=bool(u.bloqueado_hasta and u.bloqueado_hasta > ahora),
        )
        for u in db.scalars(select(Usuario).order_by(Usuario.nombre)).all()
    ]
