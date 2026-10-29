"""Catálogo de permisos y roles.

El código siempre revisa PERMISOS, nunca nombres de rol. Para agregar un rol nuevo
basta con declararlo aquí (y en db/sqlserver) con los permisos que le tocan;
no hay que tocar endpoints ni pantallas.
"""

PERMISOS: dict[str, str] = {
    "commodities.ver": "Ver el tablero de commodities",
    "usuarios.administrar": "Dar de alta, baja y asignar roles a usuarios",
}

ROLES: dict[str, dict] = {
    "administrador": {
        "nombre": "Administrador",
        "descripcion": "Acceso completo, incluida la administración de usuarios",
        "permisos": list(PERMISOS),
    },
    "lector": {
        "nombre": "Lector",
        "descripcion": "Consulta el tablero de commodities",
        "permisos": ["commodities.ver"],
    },
}
