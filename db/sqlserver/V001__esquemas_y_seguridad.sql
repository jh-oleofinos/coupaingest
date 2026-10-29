/*
  V001 - Esquemas y tablas de seguridad del Portal Oleofinos.
  Ejecutar sobre la base del proyecto (ej. commodities):
    sqlcmd -S OLF05ZGTWB01\SQLEXPRESS -E -d commodities -i V001__esquemas_y_seguridad.sql
  Debe coincidir con api/app/models.py.
*/
IF SCHEMA_ID('app') IS NULL EXEC('CREATE SCHEMA app');
IF SCHEMA_ID('dat') IS NULL EXEC('CREATE SCHEMA dat');
IF SCHEMA_ID('ctl') IS NULL EXEC('CREATE SCHEMA ctl');
GO

IF OBJECT_ID('ctl.version_esquema') IS NULL
CREATE TABLE ctl.version_esquema (
    version      varchar(20)  NOT NULL CONSTRAINT pk_version_esquema PRIMARY KEY,
    descripcion  varchar(200) NOT NULL,
    aplicado_en  datetime2(0) NOT NULL CONSTRAINT df_version_esquema_fecha DEFAULT SYSUTCDATETIME(),
    aplicado_por sysname      NOT NULL CONSTRAINT df_version_esquema_usuario DEFAULT SUSER_SNAME()
);
GO

SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF EXISTS (SELECT 1 FROM ctl.version_esquema WHERE version = 'V001')
BEGIN
    PRINT 'V001 ya aplicado.';
    COMMIT;
    RETURN;
END;

CREATE TABLE app.permiso (
    id          int IDENTITY(1,1) NOT NULL CONSTRAINT pk_permiso PRIMARY KEY,
    codigo      varchar(100) NOT NULL CONSTRAINT uq_permiso_codigo UNIQUE,
    descripcion nvarchar(200) NOT NULL
);

CREATE TABLE app.rol (
    id          int IDENTITY(1,1) NOT NULL CONSTRAINT pk_rol PRIMARY KEY,
    codigo      varchar(50)  NOT NULL CONSTRAINT uq_rol_codigo UNIQUE,
    nombre      nvarchar(100) NOT NULL,
    descripcion nvarchar(200) NOT NULL CONSTRAINT df_rol_descripcion DEFAULT N''
);

CREATE TABLE app.rol_permiso (
    rol_id     int NOT NULL CONSTRAINT fk_rol_permiso_rol REFERENCES app.rol(id),
    permiso_id int NOT NULL CONSTRAINT fk_rol_permiso_permiso REFERENCES app.permiso(id),
    CONSTRAINT pk_rol_permiso PRIMARY KEY (rol_id, permiso_id)
);

CREATE TABLE app.usuario (
    id                int IDENTITY(1,1) NOT NULL CONSTRAINT pk_usuario PRIMARY KEY,
    correo            varchar(254)  NOT NULL CONSTRAINT uq_usuario_correo UNIQUE,
    nombre            nvarchar(200) NOT NULL,
    hash_contrasena   varchar(255)  NULL,          -- NULL = solo entra con Entra ID
    activo            bit           NOT NULL CONSTRAINT df_usuario_activo DEFAULT 1,
    intentos_fallidos int           NOT NULL CONSTRAINT df_usuario_intentos DEFAULT 0,
    bloqueado_hasta   datetime2(6)  NULL,
    ultimo_acceso     datetime2(6)  NULL,
    entra_oid         varchar(36)   NULL,          -- id inmutable en Entra ID (se vincula en el 1er login)
    version_sesion    int           NOT NULL CONSTRAINT df_usuario_version_sesion DEFAULT 0,
    creado_en         datetime2(6)  NOT NULL CONSTRAINT df_usuario_creado DEFAULT SYSUTCDATETIME(),
    actualizado_en    datetime2(6)  NOT NULL CONSTRAINT df_usuario_actualizado DEFAULT SYSUTCDATETIME(),
    -- Comparación binaria: con la intercalación por defecto (CI) LOWER() no detectaría mayúsculas.
    CONSTRAINT ck_usuario_correo_minusculas CHECK (correo COLLATE Latin1_General_100_BIN2 = LOWER(correo) COLLATE Latin1_General_100_BIN2)
);
CREATE UNIQUE INDEX ux_usuario_entra_oid ON app.usuario (entra_oid) WHERE entra_oid IS NOT NULL;

CREATE TABLE app.usuario_rol (
    usuario_id int NOT NULL CONSTRAINT fk_usuario_rol_usuario REFERENCES app.usuario(id),
    rol_id     int NOT NULL CONSTRAINT fk_usuario_rol_rol REFERENCES app.rol(id),
    CONSTRAINT pk_usuario_rol PRIMARY KEY (usuario_id, rol_id)
);

CREATE TABLE app.bitacora_acceso (
    id               bigint IDENTITY(1,1) NOT NULL CONSTRAINT pk_bitacora_acceso PRIMARY KEY,
    fecha            datetime2(6) NOT NULL CONSTRAINT df_bitacora_fecha DEFAULT SYSUTCDATETIME(),
    usuario_id       int NULL CONSTRAINT fk_bitacora_usuario REFERENCES app.usuario(id),
    correo_intentado nvarchar(254) NULL,
    evento           varchar(30)  NOT NULL,
    proveedor        varchar(20)  NULL,
    detalle          nvarchar(200) NULL
);
CREATE INDEX ix_bitacora_fecha ON app.bitacora_acceso (fecha);

INSERT INTO ctl.version_esquema (version, descripcion) VALUES ('V001', 'Esquemas y seguridad');
COMMIT;
