from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app import db
from app.models import Commodity, Precio, ahora_utc
from tests.conftest import cabecera, id_de


def _h(client):
    return cabecera(sub=id_de(client, "lector@oleofinos.com.mx"))


def test_resumen_calcula_variacion(client):
    r = client.get("/commodities/resumen", headers=_h(client))
    assert r.status_code == 200
    (maiz,) = r.json()
    assert Decimal(maiz["ultimo"]["valor"]) == Decimal("205")
    assert Decimal(maiz["variacion"]) == Decimal("5")
    assert Decimal(maiz["variacion_pct"]) == Decimal("2.50")


def test_correccion_de_la_fuente_usa_la_version_mas_reciente(client):
    with Session(db.get_engine()) as s:
        c = s.query(Commodity).filter_by(codigo="maiz").one()
        s.add(
            Precio(
                commodity_id=c.id,
                fecha=date.today(),
                valor=Decimal("210"),
                fecha_carga=ahora_utc() + timedelta(hours=1),
            )
        )
        s.commit()
    serie = client.get("/commodities/maiz/serie", headers=_h(client)).json()
    assert [Decimal(p["valor"]) for p in serie["puntos"]] == [Decimal("200"), Decimal("210")]


def test_serie_valida_rango_y_codigo(client):
    h = _h(client)
    assert client.get("/commodities/noexiste/serie", headers=h).status_code == 404
    r = client.get("/commodities/maiz/serie?desde=2026-02-01&hasta=2026-01-01", headers=h)
    assert r.status_code == 422


def test_estado_carga_sin_corridas(client):
    r = client.get("/commodities/estado-carga", headers=_h(client))
    assert r.json() == {"ultima": None, "ultima_exitosa": None}
