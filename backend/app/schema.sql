-- Kirana-IQ core schema.
-- Applied at application startup; safe to run repeatedly.

CREATE TABLE IF NOT EXISTS products (
    id             SERIAL PRIMARY KEY,
    sku            TEXT           NOT NULL UNIQUE,
    name           TEXT           NOT NULL,
    category       TEXT           NOT NULL,
    unit_price     NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    current_stock  INTEGER        NOT NULL DEFAULT 0 CHECK (current_stock >= 0),
    reorder_level  INTEGER        NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
    lead_time_days INTEGER        NOT NULL DEFAULT 1 CHECK (lead_time_days >= 0)
);

CREATE TABLE IF NOT EXISTS sales (
    id         SERIAL PRIMARY KEY,
    product_id INTEGER        NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    quantity   INTEGER        NOT NULL CHECK (quantity >= 0),
    sale_date  DATE           NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0)
);

CREATE INDEX IF NOT EXISTS idx_sales_product_date ON sales (product_id, sale_date);
CREATE INDEX IF NOT EXISTS idx_products_category ON products (category);
