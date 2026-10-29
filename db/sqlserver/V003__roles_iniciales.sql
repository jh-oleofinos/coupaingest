/*
  V003 - Permisos y roles iniciales. Debe coincidir con api/app/security/catalogo.py.
  Para agregar un rol después: script nuevo (V00N) con su INSERT en app.rol y sus permisos.
*/
SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF EXISTS (SELECT 1 FROM ctl.version_esquema WHERE version = 'V003')
BEGIN
    PRINT 'V003 ya aplicado.';
    COMMIT;
    RETURN;
END;

INSERT INTO app.permiso (codigo, descripcion) VALUES
    ('commodities.ver',      N'Ver el tablero de commodities'),
    ('usuarios.administrar', N'Dar de alta, baja y asignar roles a usuarios');

INSERT INTO app.rol (codigo, nombre, descripcion) VALUES
    ('administrador', N'Administrador', N'Acceso completo, incluida la administración de usuarios'),
    ('lector',        N'Lector',        N'Consulta el tablero de commodities');

INSERT INTO app.rol_permiso (rol_id, permiso_id)
SELECT r.id, p.id FROM app.rol r CROSS JOIN app.permiso p WHERE r.codigo = 'administrador';

INSERT INTO app.rol_permiso (rol_id, permiso_id)
SELECT r.id, p.id FROM app.rol r JOIN app.permiso p ON p.codigo = 'commodities.ver'
WHERE r.codigo = 'lector';

INSERT INTO ctl.version_esquema (version, descripcion) VALUES ('V003', 'Roles iniciales');
COMMIT;
