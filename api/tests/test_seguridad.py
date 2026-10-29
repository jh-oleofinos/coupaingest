from tests.conftest import CONTRASENA, cabecera, id_de

LOGIN = "/auth/login"


def _login(client, correo, contrasena=CONTRASENA, **kw):
    return client.post(
        LOGIN,
        json={"correo": correo, "contrasena": contrasena},
        headers=cabecera(tipo="servicio", sub="web", **kw),
    )


# ---------------------------------------------------------------- login


def test_login_correcto_devuelve_perfil_con_rol_y_permisos(client):
    r = _login(client, "Admin@Oleofinos.com.mx")  # el correo no distingue mayúsculas
    assert r.status_code == 200
    perfil = r.json()
    assert perfil["nombre"] == "Admin Prueba"
    assert perfil["roles"] == [{"codigo": "administrador", "nombre": "Administrador"}]
    assert set(perfil["permisos"]) == {"commodities.ver", "usuarios.administrar"}
    assert "hash_contrasena" not in perfil


def test_login_falla_siempre_con_el_mismo_mensaje(client):
    respuestas = [
        _login(client, "lector@oleofinos.com.mx", "incorrecta-123456"),
        _login(client, "noexiste@oleofinos.com.mx"),
        _login(client, "inactivo@oleofinos.com.mx"),
        _login(client, "entra@oleofinos.com.mx", "cualquier-cosa-1234"),  # sin contraseña
    ]
    assert {r.status_code for r in respuestas} == {401}
    assert {r.json()["detail"] for r in respuestas} == {"Credenciales inválidas."}


def test_bloqueo_tras_intentos_fallidos(client):
    for _ in range(3):
        assert _login(client, "lector@oleofinos.com.mx", "incorrecta-123456").status_code == 401
    # Bloqueada: ni la contraseña correcta entra.
    assert _login(client, "lector@oleofinos.com.mx").status_code == 401


def test_login_exige_token_de_servicio(client):
    cuerpo = {"correo": "admin@oleofinos.com.mx", "contrasena": CONTRASENA}
    assert client.post(LOGIN, json=cuerpo).status_code == 401
    r = client.post(LOGIN, json=cuerpo, headers=cabecera(tipo="usuario", sub="1"))
    assert r.status_code == 401


# ---------------------------------------------------------------- tokens


def test_tokens_invalidos_se_rechazan(client):
    uid = id_de(client, "admin@oleofinos.com.mx")
    casos = [
        cabecera(sub=uid, _secreto="y" * 48),  # firma con otro secreto
        cabecera(sub=uid, aud="otra-api"),
        cabecera(sub=uid, iss="otro-emisor"),
        cabecera(sub=uid, vida=-60),  # vencido
        cabecera(sub=uid, vida=3600),  # vida demasiado larga
        cabecera(sub=uid, typ="admin"),
        {"Authorization": "Bearer basura"},
        {},
    ]
    for h in casos:
        assert client.get("/auth/perfil", headers=h).status_code == 401, h


def test_token_con_algoritmo_none_se_rechaza(client):
    import jwt

    t = jwt.encode({"sub": "1", "typ": "usuario"}, key=None, algorithm="none")
    assert client.get("/auth/perfil", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_usuario_inactivo_pierde_acceso_aunque_tenga_token(client):
    uid = id_de(client, "inactivo@oleofinos.com.mx")
    assert client.get("/commodities/resumen", headers=cabecera(sub=uid)).status_code == 401


# ---------------------------------------------------------------- permisos


def test_lector_ve_commodities_pero_no_administra_usuarios(client):
    h = cabecera(sub=id_de(client, "lector@oleofinos.com.mx"))
    assert client.get("/commodities/resumen", headers=h).status_code == 200
    assert client.get("/usuarios", headers=h).status_code == 403


def test_administrador_lista_usuarios_sin_exponer_hashes(client):
    r = client.get("/usuarios", headers=cabecera(sub=id_de(client, "admin@oleofinos.com.mx")))
    assert r.status_code == 200
    assert all("hash_contrasena" not in u for u in r.json())


# ---------------------------------------------------------------- entra


def test_entra_solo_autoriza_usuarios_registrados_y_activos(client):
    h = cabecera(tipo="servicio", sub="web")
    assert (
        client.post(
            "/auth/entra", json={"correo": "entra@oleofinos.com.mx", "oid": OID_A}, headers=h
        ).status_code
        == 200
    )
    for correo in ("inactivo@oleofinos.com.mx", "desconocido@oleofinos.com.mx"):
        assert (
            client.post("/auth/entra", json={"correo": correo, "oid": OID_B}, headers=h).status_code
            == 403
        )


def test_host_no_permitido(client):
    r = client.get("/salud", headers={"Host": "oleoweb.ejemplo.com"})
    assert r.status_code == 400


# ---------------------------------------------------------------- revisión de seguridad


def test_cerrar_sesion_invalida_tokens_anteriores(client):
    uid = id_de(client, "lector@oleofinos.com.mx")
    assert client.get("/auth/perfil", headers=cabecera(sub=uid, vs=0)).status_code == 200
    assert client.post("/auth/cerrar-sesion", headers=cabecera(sub=uid, vs=0)).status_code == 204
    # La sesión vieja (vs=0) ya no sirve; la nueva versión llega en el próximo login.
    assert client.get("/commodities/resumen", headers=cabecera(sub=uid, vs=0)).status_code == 401
    assert _login(client, "lector@oleofinos.com.mx").json()["version_sesion"] == 1


def test_token_de_usuario_sin_version_se_rechaza(client):
    import time

    import jwt

    from tests.conftest import SECRETO

    ahora = int(time.time())
    t = jwt.encode(
        {
            "iss": "oleoweb-web",
            "aud": "oleoweb-api",
            "iat": ahora,
            "exp": ahora + 60,
            "sub": id_de(client, "lector@oleofinos.com.mx"),
            "typ": "usuario",
        },
        SECRETO,
        algorithm="HS256",
    )
    assert client.get("/auth/perfil", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_intentos_se_cuentan_en_la_base(client):
    from sqlalchemy.orm import Session

    from app import db
    from app.models import Usuario

    _login(client, "admin@oleofinos.com.mx", "incorrecta-123456")
    _login(client, "admin@oleofinos.com.mx", "incorrecta-123456")
    with Session(db.get_engine()) as s:
        u = s.query(Usuario).filter_by(correo="admin@oleofinos.com.mx").one()
        assert u.intentos_fallidos == 2 and u.bloqueado_hasta is None
    _login(client, "admin@oleofinos.com.mx", "incorrecta-123456")
    with Session(db.get_engine()) as s:
        u = s.query(Usuario).filter_by(correo="admin@oleofinos.com.mx").one()
        assert u.intentos_fallidos == 0 and u.bloqueado_hasta is not None


OID_A = "11111111-1111-1111-1111-111111111111"
OID_B = "22222222-2222-2222-2222-222222222222"


def test_entra_vincula_por_oid_y_no_acepta_otro_oid_con_el_mismo_correo(client):
    h = cabecera(tipo="servicio", sub="web")
    url = "/auth/entra"
    primero = client.post(url, json={"correo": "entra@oleofinos.com.mx", "oid": OID_A}, headers=h)
    assert primero.status_code == 200
    # Otra identidad que dice tener el mismo correo: rechazada.
    otro = client.post(url, json={"correo": "entra@oleofinos.com.mx", "oid": OID_B}, headers=h)
    assert otro.status_code == 403
    # Si el correo cambia en Entra, el oid sigue identificando a la persona.
    cambio = client.post(url, json={"correo": "nuevo@oleofinos.com.mx", "oid": OID_A}, headers=h)
    assert cambio.status_code == 200


def test_precios_de_corridas_fallidas_no_reemplazan_valores(client):
    from datetime import date
    from decimal import Decimal

    from sqlalchemy.orm import Session

    from app import db
    from app.models import Commodity, Corrida, Precio, ahora_utc

    with Session(db.get_engine()) as s:
        c = s.query(Commodity).filter_by(codigo="maiz").one()
        corrida = Corrida(proceso="commodities", estado="fallida")
        s.add(corrida)
        s.flush()
        s.add(
            Precio(
                commodity_id=c.id,
                fecha=date.today(),
                valor=Decimal("999"),
                fecha_carga=ahora_utc(),
                corrida_id=corrida.id,
            )
        )
        s.commit()
    h = cabecera(sub=id_de(client, "lector@oleofinos.com.mx"))
    (maiz,) = client.get("/commodities/resumen", headers=h).json()
    assert Decimal(maiz["ultimo"]["valor"]) == Decimal("205")
