from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import BitacoraAcceso, Usuario, ahora_utc
from app.schemas import EntraEntrada, LoginEntrada, PerfilSalida, RolSalida
from app.security import passwords
from app.security.deps import (
    UsuarioContexto,
    contexto_de,
    llamada_de_servicio,
    usuario_actual,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Un solo mensaje para todo fallo de login: no revela si el correo existe,
# si la cuenta está inactiva o si está bloqueada.
CREDENCIALES_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas."
)
NO_AUTORIZADO = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN, detail="Usuario no autorizado."
)


def perfil(ctx: UsuarioContexto) -> PerfilSalida:
    return PerfilSalida(
        id=ctx.id,
        correo=ctx.correo,
        nombre=ctx.nombre,
        roles=[RolSalida(codigo=c, nombre=n) for c, n in ctx.roles],
        permisos=sorted(ctx.permisos),
        version_sesion=ctx.version_sesion,
    )


def _registrar(
    db: Session,
    evento: str,
    proveedor: str | None,
    usuario: Usuario | None,
    correo: str | None = None,
    detalle: str | None = None,
) -> None:
    db.add(
        BitacoraAcceso(
            usuario_id=usuario.id if usuario else None,
            correo_intentado=None if usuario or not correo else correo[:254],
            evento=evento,
            proveedor=proveedor,
            detalle=detalle,
        )
    )


def _sumar_intento_fallido(
    db: Session, usuario: Usuario, ahora: datetime, settings: Settings
) -> bool:
    """Incremento ATÓMICO en la base (no leer-sumar-escribir en Python): con peticiones en
    paralelo, el UPDATE bloquea la fila y cada intento cuenta. Devuelve True si se bloqueó."""
    db.execute(
        update(Usuario)
        .where(Usuario.id == usuario.id)
        .values(intentos_fallidos=Usuario.intentos_fallidos + 1)
        .execution_options(synchronize_session=False)
    )
    intentos = db.scalar(select(Usuario.intentos_fallidos).where(Usuario.id == usuario.id)) or 0
    if intentos < settings.LOGIN_MAX_INTENTOS:
        return False
    db.execute(
        update(Usuario)
        .where(Usuario.id == usuario.id)
        .values(
            bloqueado_hasta=ahora + timedelta(minutes=settings.LOGIN_BLOQUEO_MINUTOS),
            intentos_fallidos=0,
        )
        .execution_options(synchronize_session=False)
    )
    return True


@router.post("/login", response_model=PerfilSalida)
def login(
    entrada: LoginEntrada,
    _: object = Depends(llamada_de_servicio),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PerfilSalida:
    correo = entrada.correo.lower()
    usuario = db.scalar(select(Usuario).where(Usuario.correo == correo))
    ahora = ahora_utc()

    if usuario and usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
        passwords.verificar(None, entrada.contrasena)  # mismo tiempo de respuesta
        _registrar(db, "login_bloqueado", "credenciales", usuario)
        db.commit()
        raise CREDENCIALES_INVALIDAS

    correcta = passwords.verificar(usuario.hash_contrasena if usuario else None, entrada.contrasena)

    if not usuario or not correcta or not usuario.activo:
        if usuario and not correcta and _sumar_intento_fallido(db, usuario, ahora, settings):
            _registrar(db, "login_bloqueado", "credenciales", usuario, detalle="por intentos")
        detalle = "inactivo" if usuario and correcta else None
        _registrar(db, "login_fallido", "credenciales", usuario, correo, detalle)
        db.commit()
        raise CREDENCIALES_INVALIDAS

    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.ultimo_acceso = ahora
    if usuario.hash_contrasena and passwords.requiere_rehash(usuario.hash_contrasena):
        usuario.hash_contrasena = passwords.generar_hash(entrada.contrasena)
    _registrar(db, "login_ok", "credenciales", usuario)
    db.commit()
    return perfil(contexto_de(usuario))


@router.post("/entra", response_model=PerfilSalida)
def login_entra(
    entrada: EntraEntrada,
    _: object = Depends(llamada_de_servicio),
    db: Session = Depends(get_db),
) -> PerfilSalida:
    """Entra ID ya autenticó a la persona (y la web verificó que es de nuestro tenant);
    aquí solo se decide si está autorizada en el portal.

    El vínculo es por `oid` (inmutable). El correo solo se usa la primera vez, para
    vincular a un usuario dado de alta en el portal que todavía no tiene `oid`.
    """
    oid = entrada.oid.lower()
    correo = entrada.correo.lower()
    usuario = db.scalar(select(Usuario).where(Usuario.entra_oid == oid))
    if usuario is None:
        candidato = db.scalar(select(Usuario).where(Usuario.correo == correo))
        if candidato is not None and candidato.entra_oid is None:
            candidato.entra_oid = oid
            usuario = candidato
    if usuario is None or not usuario.activo:
        _registrar(db, "login_rechazado", "entra", usuario, correo, "no registrado o inactivo")
        db.commit()
        raise NO_AUTORIZADO
    usuario.ultimo_acceso = ahora_utc()
    _registrar(db, "login_ok", "entra", usuario)
    db.commit()
    return perfil(contexto_de(usuario))


@router.get("/perfil", response_model=PerfilSalida)
def obtener_perfil(usuario: UsuarioContexto = Depends(usuario_actual)) -> PerfilSalida:
    """La web lo consulta en cada página: refleja al instante cambios de rol, bajas y cierres."""
    return perfil(usuario)


@router.post("/cerrar-sesion", status_code=status.HTTP_204_NO_CONTENT)
def cerrar_sesion(
    ctx: UsuarioContexto = Depends(usuario_actual), db: Session = Depends(get_db)
) -> None:
    """Invalida TODAS las sesiones del usuario (cualquier cookie copiada deja de servir)."""
    db.execute(
        update(Usuario)
        .where(Usuario.id == ctx.id)
        .values(version_sesion=Usuario.version_sesion + 1)
        .execution_options(synchronize_session=False)
    )
    db.add(BitacoraAcceso(usuario_id=ctx.id, evento="logout"))
    db.commit()
