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

CREATE VIEW skolkovo_general.field_aliases as 

WITH user_cols as (
            	SELECT aa.attr_name, aa.alias FROM skolkovo_general.attr_alias aa
            )

SELECT columns.column_name as attr_name, 
case 
	when alias = '' or alias is null then columns.column_name
	else alias
end
as alias, 

table_name, 

case 
	when data_type in ('text', 'character varying') then 'text'
	when data_type in ('double precision', 'integer', 'bigint') then 'number'
	else data_type
end
as data_type 

FROM information_schema.columns
left join user_cols on columns.column_name = user_cols.attr_name
WHERE columns.table_name in (
	select table_name FROM skolkovo_general.layers where layers_type_id !=3 
) and columns.column_name not in ('id', 'geom')
order by attr_name;