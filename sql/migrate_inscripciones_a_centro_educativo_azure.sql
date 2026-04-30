/*
  Migración Azure SQL: elimina Inscripciones, crea CentroEducativo y enlaza Certificados.

  Ejecute en la base correcta (p. ej. CertificadosDB), con permisos DDL.
  Revise el bloque de UPDATE de backfill antes de confirmar en producción.
*/
SET NOCOUNT ON;

/* 1) Tabla CentroEducativo */
IF OBJECT_ID(N'dbo.CentroEducativo', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.CentroEducativo (
        IdCentroEducativo INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Logo VARBINARY(MAX) NULL,
        Nombre NVARCHAR(200) NOT NULL,
        Estado NVARCHAR(20) NOT NULL CONSTRAINT DF_CentroEducativo_Estado DEFAULT (N'Activo'),
        CONSTRAINT CK_CentroEducativo_Estado CHECK (Estado IN (N'Activo', N'Inactivo')),
        CONSTRAINT UX_CentroEducativo_Nombre UNIQUE (Nombre)
    );
END;
GO

/* 2) Centro por defecto (solo si no hay filas) */
IF NOT EXISTS (SELECT 1 FROM dbo.CentroEducativo)
BEGIN
    INSERT INTO dbo.CentroEducativo (Logo, Nombre, Estado)
    VALUES (NULL, N'Institución predeterminada', N'Activo');
END;
GO

/* 3) Columna IdCentroEducativo en Certificados (referencia al centro, no al revés) */
IF COL_LENGTH(N'dbo.Certificados', N'IdCentroEducativo') IS NULL
BEGIN
    ALTER TABLE dbo.Certificados ADD IdCentroEducativo INT NULL;
END;
GO

/* 4) Rellenar certificados sin centro (asigna el primer IdCentroEducativo existente) */
DECLARE @IdDef INT;
SELECT @IdDef = MIN(IdCentroEducativo) FROM dbo.CentroEducativo;

UPDATE c
SET c.IdCentroEducativo = @IdDef
FROM dbo.Certificados AS c
WHERE c.IdCentroEducativo IS NULL
  AND @IdDef IS NOT NULL;
GO

/* 5) FK: Certificados.IdCentroEducativo -> CentroEducativo.IdCentroEducativo */
IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = N'FK_Certificados_CentroEducativo'
      AND parent_object_id = OBJECT_ID(N'dbo.Certificados')
)
BEGIN
    ALTER TABLE dbo.Certificados
    ADD CONSTRAINT FK_Certificados_CentroEducativo
    FOREIGN KEY (IdCentroEducativo) REFERENCES dbo.CentroEducativo (IdCentroEducativo);
END;
GO

/* 6) Índice por centro */
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_Certificados_IdCentroEducativo'
      AND object_id = OBJECT_ID(N'dbo.Certificados')
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_Certificados_IdCentroEducativo
    ON dbo.Certificados (IdCentroEducativo);
END;
GO

/* 7) Quitar FKs hacia/desde Inscripciones y eliminar la tabla */
DECLARE @sql NVARCHAR(MAX) = N'';

/* FKs definidas en Inscripciones (tabla padre = Inscripciones) */
SELECT @sql = @sql + N'ALTER TABLE dbo.Inscripciones DROP CONSTRAINT ' + QUOTENAME(fk.name) + N';' + CHAR(13)
FROM sys.foreign_keys AS fk
WHERE fk.parent_object_id = OBJECT_ID(N'dbo.Inscripciones');

IF @sql <> N''
    EXEC sp_executesql @sql;

SET @sql = N'';

/* Otras tablas que referencien Inscripciones */
SELECT @sql = @sql
    + N'ALTER TABLE ' + QUOTENAME(OBJECT_SCHEMA_NAME(fk.parent_object_id)) + N'.' + QUOTENAME(OBJECT_NAME(fk.parent_object_id))
    + N' DROP CONSTRAINT ' + QUOTENAME(fk.name) + N';' + CHAR(13)
FROM sys.foreign_keys AS fk
WHERE fk.referenced_object_id = OBJECT_ID(N'dbo.Inscripciones');

IF @sql <> N''
    EXEC sp_executesql @sql;

IF OBJECT_ID(N'dbo.Inscripciones', N'U') IS NOT NULL
    DROP TABLE dbo.Inscripciones;
GO
