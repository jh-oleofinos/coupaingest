import time
from datetime import date, timedelta
from decimal import Decimal

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import db
from app.cli import sembrar_roles
from app.config import Settings
from app.main import create_app
from app.models import Commodity, Precio, Rol, Usuario
from app.security import passwords

SECRETO = "x" * 48
CONTRASENA = "Contraseña-de-prueba-123"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        ENTORNO="dev",
        DATABASE_URL="sqlite:///:memory:",
        API_TOKEN_SECRET=SECRETO,
        LOGIN_MAX_INTENTOS=3,
        LOGIN_BLOQUEO_MINUTOS=15,
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    app = create_app(settings)
    db.Base.metadata.create_all(db.get_engine())
    with Session(db.get_engine()) as s:
        sembrar_roles(s)
        roles = {r.codigo: r for r in s.query(Rol).all()}
        h = passwords.generar_hash(CONTRASENA)
        s.add_all(
            [
                Usuario(
                    correo="admin@oleofinos.com.mx",
                    nombre="Admin Prueba",
                    hash_contrasena=h,
                    roles=[roles["administrador"]],
                ),
                Usuario(
                    correo="lector@oleofinos.com.mx",
                    nombre="Lector Prueba",
                    hash_contrasena=h,
                    roles=[roles["lector"]],
                ),
                Usuario(
                    correo="inactivo@oleofinos.com.mx",
                    nombre="Inactivo",
                    hash_contrasena=h,
                    activo=False,
                    roles=[roles["lector"]],
                ),
                Usuario(
                    correo="entra@oleofinos.com.mx",
                    nombre="Solo Entra",
                    hash_contrasena=None,
                    roles=[roles["lector"]],
                ),
            ]
        )
        c = Commodity(codigo="maiz", nombre="Maíz", unidad="USD/t")
        s.add(c)
        s.flush()
        hoy = date.today()
        s.add_all(
            [
                Precio(commodity_id=c.id, fecha=hoy - timedelta(days=1), valor=Decimal("200")),
                Precio(commodity_id=c.id, fecha=hoy, valor=Decimal("205")),
            ]
        )
        s.commit()
    return TestClient(app)


def token(tipo: str = "usuario", sub: str = "1", vida: int = 60, vs: int = 0, **cambios) -> str:
    ahora = int(time.time())
    datos = {
        "iss": "oleoweb-web",
        "aud": "oleoweb-api",
        "iat": ahora,
        "exp": ahora + vida,
        "sub": sub,
        "typ": tipo,
    }
    if tipo == "usuario":
        datos["vs"] = vs
    datos.update(cambios)
    secreto = datos.pop("_secreto", SECRETO)
    return jwt.encode(datos, secreto, algorithm="HS256")


def cabecera(**kw) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(**kw)}"}


def id_de(client: TestClient, correo: str) -> str:
    with Session(db.get_engine()) as s:
        return str(s.query(Usuario).filter_by(correo=correo).one().id)
