/*
  V002 - Tablas de commodities y control de corridas.
  Debe coincidir con api/app/models.py.
*/
SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF EXISTS (SELECT 1 FROM ctl.version_esquema WHERE version = 'V002')
BEGIN
    PRINT 'V002 ya aplicado.';
    COMMIT;
    RETURN;
END;

CREATE TABLE ctl.corrida (
    id      bigint IDENTITY(1,1) NOT NULL CONSTRAINT pk_corrida PRIMARY KEY,
    proceso varchar(50)   NOT NULL,
    inicio  datetime2(6)  NOT NULL CONSTRAINT df_corrida_inicio DEFAULT SYSUTCDATETIME(),
    fin     datetime2(6)  NULL,
    estado  varchar(20)   NOT NULL CONSTRAINT ck_corrida_estado CHECK (estado IN ('en_curso','exitosa','fallida')),
    filas   int           NULL,
    mensaje nvarchar(500) NULL
);
CREATE INDEX ix_corrida_proceso_inicio ON ctl.corrida (proceso, inicio DESC);

CREATE TABLE dat.commodity (
    id     int IDENTITY(1,1) NOT NULL CONSTRAINT pk_commodity PRIMARY KEY,
    codigo varchar(50)   NOT NULL CONSTRAINT uq_commodity_codigo UNIQUE,
    nombre nvarchar(100) NOT NULL,
    unidad varchar(30)   NOT NULL,
    orden  int           NOT NULL CONSTRAINT df_commodity_orden DEFAULT 0,
    activo bit           NOT NULL CONSTRAINT df_commodity_activo DEFAULT 1
);

-- Historia: solo se agregan filas. Una corrección de la fuente es una versión nueva (fecha_carga).
CREATE TABLE dat.precio (
    id           bigint IDENTITY(1,1) NOT NULL CONSTRAINT pk_precio PRIMARY KEY,
    commodity_id int           NOT NULL CONSTRAINT fk_precio_commodity REFERENCES dat.commodity(id),
    fecha        date          NOT NULL,
    valor        decimal(18,6) NOT NULL,
    fecha_carga  datetime2(6)  NOT NULL CONSTRAINT df_precio_fecha_carga DEFAULT SYSUTCDATETIME(),
    corrida_id   bigint        NULL CONSTRAINT fk_precio_corrida REFERENCES ctl.corrida(id),
    CONSTRAINT uq_precio_version UNIQUE (commodity_id, fecha, fecha_carga)
);
CREATE INDEX ix_precio_commodity_fecha ON dat.precio (commodity_id, fecha, fecha_carga DESC) INCLUDE (valor);

INSERT INTO ctl.version_esquema (version, descripcion) VALUES ('V002', 'Commodities y corridas');
COMMIT;
