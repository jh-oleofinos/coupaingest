from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Commodity, Corrida, Precio
from app.schemas import (
    CorridaSalida,
    EstadoCargaSalida,
    PuntoSerie,
    ResumenCommodity,
    SerieSalida,
)
from app.security.deps import UsuarioContexto, requiere

router = APIRouter(prefix="/commodities", tags=["commodities"])
PROCESO = "commodities"
RANGO_MAXIMO_DIAS = 366 * 20

ver = requiere("commodities.ver")


def _precios_vigentes():
    """Por cada commodity y fecha, la versión más reciente de una carga EXITOSA.
    Filas de corridas fallidas o en curso nunca reemplazan valores buenos."""
    version = (
        select(
            Precio.commodity_id,
            Precio.fecha,
            func.max(Precio.fecha_carga).label("fecha_carga"),
        )
        .outerjoin(Corrida, Corrida.id == Precio.corrida_id)
        .where(or_(Precio.corrida_id.is_(None), Corrida.estado == "exitosa"))
        .group_by(Precio.commodity_id, Precio.fecha)
        .subquery()
    )
    return select(Precio).join(
        version,
        and_(
            Precio.commodity_id == version.c.commodity_id,
            Precio.fecha == version.c.fecha,
            Precio.fecha_carga == version.c.fecha_carga,
        ),
    )


def _commodity(db: Session, codigo: str) -> Commodity:
    c = db.scalar(select(Commodity).where(Commodity.codigo == codigo, Commodity.activo))
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado.")
    return c


@router.get("/resumen", response_model=list[ResumenCommodity])
def resumen(
    _: UsuarioContexto = Depends(ver), db: Session = Depends(get_db)
) -> list[ResumenCommodity]:
    salida: list[ResumenCommodity] = []
    commodities = db.scalars(
        select(Commodity).where(Commodity.activo).order_by(Commodity.orden, Commodity.nombre)
    ).all()
    for c in commodities:
        ultimos = db.scalars(
            _precios_vigentes()
            .where(Precio.commodity_id == c.id)
            .order_by(Precio.fecha.desc())
            .limit(2)
        ).all()
        ultimo = ultimos[0] if ultimos else None
        anterior = ultimos[1] if len(ultimos) > 1 else None
        variacion = variacion_pct = None
        if ultimo and anterior:
            variacion = ultimo.valor - anterior.valor
            if anterior.valor:
                variacion_pct = (variacion / anterior.valor * 100).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
        salida.append(
            ResumenCommodity(
                codigo=c.codigo,
                nombre=c.nombre,
                unidad=c.unidad,
                ultimo=PuntoSerie(fecha=ultimo.fecha, valor=ultimo.valor) if ultimo else None,
                anterior=PuntoSerie(fecha=anterior.fecha, valor=anterior.valor)
                if anterior
                else None,
                variacion=variacion,
                variacion_pct=variacion_pct,
            )
        )
    return salida


@router.get("/estado-carga", response_model=EstadoCargaSalida)
def estado_carga(
    _: UsuarioContexto = Depends(ver), db: Session = Depends(get_db)
) -> EstadoCargaSalida:
    base = select(Corrida).where(Corrida.proceso == PROCESO).order_by(Corrida.inicio.desc())
    ultima = db.scalar(base.limit(1))
    exitosa = db.scalar(base.where(Corrida.estado == "exitosa").limit(1))
    return EstadoCargaSalida(
        ultima=CorridaSalida.model_validate(ultima) if ultima else None,
        ultima_exitosa=CorridaSalida.model_validate(exitosa) if exitosa else None,
    )


@router.get("/{codigo}/serie", response_model=SerieSalida)
def serie(
    codigo: str,
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    _: UsuarioContexto = Depends(ver),
    db: Session = Depends(get_db),
) -> SerieSalida:
    c = _commodity(db, codigo)
    hasta = hasta or date.today()
    desde = desde or hasta - timedelta(days=365)
    if desde > hasta or (hasta - desde).days > RANGO_MAXIMO_DIAS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Rango inválido."
        )
    filas = db.scalars(
        _precios_vigentes()
        .where(Precio.commodity_id == c.id, Precio.fecha >= desde, Precio.fecha <= hasta)
        .order_by(Precio.fecha)
    ).all()
    return SerieSalida(
        codigo=c.codigo,
        nombre=c.nombre,
        unidad=c.unidad,
        puntos=[PuntoSerie(fecha=p.fecha, valor=p.valor) for p in filas],
    )
