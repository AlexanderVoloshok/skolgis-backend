


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