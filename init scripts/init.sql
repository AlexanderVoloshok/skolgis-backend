CREATE USER skolkovo WITH PASSWORD 'skolkovo';
CREATE DATABASE skolkovo OWNER skolkovo;
\c skolkovo;
CREATE SCHEMA skolkovo_general AUTHORIZATION skolkovo;
CREATE SCHEMA skolkovo_layers AUTHORIZATION skolkovo;
GRANT ALL PRIVILEGES ON DATABASE skolkovo TO skolkovo;
SET search_path TO skolkovo_general;
CREATE EXTENSION IF NOT EXISTS postgis;

SET ROLE skolkovo;



CREATE TABLE IF NOT EXISTS attr_alias
(
    id        serial
        constraint attr_alias_pk
            primary key,
    attr_name varchar(100),
    alias     varchar(100),
    create_at timestamp default now(),
    constraint attr_alias_unique
        unique (attr_name)
);

COMMENT ON COLUMN attr_alias.attr_name is 'название атрибута в таблице';
COMMENT ON COLUMN attr_alias.alias is 'название атрибута в интерфейсе';

CREATE TABLE IF NOT EXISTS file_attachments (
  id           BIGSERIAL PRIMARY KEY,
  layer        TEXT      NOT NULL,
  fid          BIGINT    NOT NULL,
  original_name TEXT     NOT NULL,
  stored_name   TEXT     NOT NULL,   -- уникальное имя на диске
  mime          TEXT,
  size_bytes    BIGINT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- полезный индекс для выборок по объекту
CREATE INDEX IF NOT EXISTS file_attachments_layer_fid_idx
  ON file_attachments (layer, fid);