/*
  V004 - Usuarios de base de datos con mínimo privilegio.
  Cuentas de servicio de Windows (sin contraseñas en archivos). Reemplaza DOMINIO\svc_...
  por las cuentas reales antes de ejecutar. Requiere que existan los LOGIN en la instancia:
    CREATE LOGIN [DOMINIO\svc_oleoweb_api] FROM WINDOWS;
    CREATE LOGIN [DOMINIO\svc_oleoweb_job] FROM WINDOWS;

  - API: lee app, dat y ctl. Solo actualiza app.usuario (login, bloqueo, versión de sesión)
    y solo INSERTA en la bitácora: no puede modificar ni borrar el registro de accesos.
  - Job de ingesta: escribe dat y ctl; no toca app.
  - Altas de usuarios y roles (python -m app.cli ...): las corre un administrador con su
    propia cuenta de Windows, no con la cuenta de la API.
*/
SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF EXISTS (SELECT 1 FROM ctl.version_esquema WHERE version = 'V004')
BEGIN
    PRINT 'V004 ya aplicado.';
    COMMIT;
    RETURN;
END;

CREATE ROLE rol_api;
GRANT SELECT ON SCHEMA::app TO rol_api;
GRANT UPDATE ON app.usuario TO rol_api;
GRANT INSERT ON app.bitacora_acceso TO rol_api;
GRANT SELECT ON SCHEMA::dat TO rol_api;
GRANT SELECT ON SCHEMA::ctl TO rol_api;

CREATE ROLE rol_job;
GRANT SELECT, INSERT, UPDATE ON SCHEMA::dat TO rol_job;
GRANT SELECT, INSERT, UPDATE ON SCHEMA::ctl TO rol_job;

CREATE USER [DOMINIO\svc_oleoweb_api] FOR LOGIN [DOMINIO\svc_oleoweb_api];
ALTER ROLE rol_api ADD MEMBER [DOMINIO\svc_oleoweb_api];

CREATE USER [DOMINIO\svc_oleoweb_job] FOR LOGIN [DOMINIO\svc_oleoweb_job];
ALTER ROLE rol_job ADD MEMBER [DOMINIO\svc_oleoweb_job];

INSERT INTO ctl.version_esquema (version, descripcion) VALUES ('V004', 'Usuarios de base');
COMMIT;
