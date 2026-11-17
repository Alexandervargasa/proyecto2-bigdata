-- Esquema de la fuente 1: datos maestros en RDS MariaDB
CREATE DATABASE IF NOT EXISTS clima_maestros
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
SET NAMES utf8mb4;
USE clima_maestros;

DROP TABLE IF EXISTS ciudad;
DROP TABLE IF EXISTS departamento;

CREATE TABLE departamento (
  cod_depto       CHAR(2)      NOT NULL PRIMARY KEY,   -- código DANE
  departamento    VARCHAR(60)  NOT NULL,
  poblacion_2024  INT          NOT NULL,               -- proyección DANE (aprox.)
  area_km2        INT          NOT NULL,
  actualizado_en  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                               ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE ciudad (
  id_ciudad       CHAR(5)       NOT NULL PRIMARY KEY,  -- código DANE municipio
  ciudad          VARCHAR(60)   NOT NULL,
  cod_depto       CHAR(2)       NOT NULL,
  latitud         DECIMAL(8,4)  NOT NULL,
  longitud        DECIMAL(8,4)  NOT NULL,
  altitud_m       INT           NOT NULL,
  region_natural  VARCHAR(20)   NOT NULL,
  es_capital      TINYINT(1)    NOT NULL DEFAULT 1,
  actualizado_en  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_ciudad_depto FOREIGN KEY (cod_depto)
    REFERENCES departamento (cod_depto)
) ENGINE=InnoDB;
