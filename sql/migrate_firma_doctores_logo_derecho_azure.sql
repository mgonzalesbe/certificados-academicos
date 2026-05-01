-- Migración manual (Azure SQL / SQL Server) si no ejecuta init_db al arrancar.
-- FirmaDoctores + IdFirmaDoctores en Certificados + LogoDerecho en CentroEducativo.

IF OBJECT_ID(N'dbo.FirmaDoctores', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.FirmaDoctores (
        IdFirmaDoctores INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Firma VARBINARY(MAX) NULL,
        Estado NVARCHAR(20) NOT NULL DEFAULT N'Activo',
        Nombres NVARCHAR(200) NOT NULL,
        Genero NVARCHAR(20) NOT NULL,
        CONSTRAINT CK_FirmaDoctores_Estado CHECK (Estado IN (N'Activo', N'Inactivo')),
        CONSTRAINT CK_FirmaDoctores_Genero CHECK (Genero IN (N'Masculino', N'Femenino'))
    );
END;
GO

IF COL_LENGTH(N'dbo.CentroEducativo', N'LogoDerecho') IS NULL
    ALTER TABLE dbo.CentroEducativo ADD LogoDerecho VARBINARY(MAX) NULL;
GO

IF COL_LENGTH(N'dbo.Certificados', N'IdFirmaDoctores') IS NULL
    ALTER TABLE dbo.Certificados ADD IdFirmaDoctores INT NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_Certificados_IdFirmaDoctores' AND object_id = OBJECT_ID(N'dbo.Certificados')
)
    CREATE NONCLUSTERED INDEX IX_Certificados_IdFirmaDoctores ON dbo.Certificados(IdFirmaDoctores);
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_Certificados_FirmaDoctores')
BEGIN
    ALTER TABLE dbo.Certificados
    ADD CONSTRAINT FK_Certificados_FirmaDoctores
    FOREIGN KEY (IdFirmaDoctores) REFERENCES dbo.FirmaDoctores(IdFirmaDoctores);
END;
GO
