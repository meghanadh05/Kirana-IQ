-- Kirana-IQ SaaS core: users, stores, multi-tenancy, and the retail/POS domain.
--
-- The 0001 schema was single-tenant: a flat `products` table and a flat `sales`
-- table holding one row per product per day. This migration turns that into a
-- multi-tenant product while preserving the existing demand history, which the
-- forecasting model is trained on.
--
-- Legacy rows are adopted by a "Demo Store" owned by a system user whose
-- password hash is deliberately unusable ('!'), so no credential is committed
-- and the account cannot be logged into until a seed script sets one.

-- ---------------------------------------------------------------------------
-- Identity
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         TEXT        NOT NULL UNIQUE,
    password_hash TEXT        NOT NULL,
    full_name     TEXT        NOT NULL,
    phone         TEXT,
    is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stores (
    id                    SERIAL PRIMARY KEY,
    name                  TEXT        NOT NULL,
    owner_name            TEXT,
    phone                 TEXT,
    email                 TEXT,
    address               TEXT,
    city                  TEXT,
    state                 TEXT,
    pin_code              TEXT,
    gst_number            TEXT,
    currency              TEXT        NOT NULL DEFAULT 'INR',
    business_type         TEXT        NOT NULL DEFAULT 'KIRANA',
    is_demo               BOOLEAN     NOT NULL DEFAULT FALSE,
    onboarding_step       INTEGER     NOT NULL DEFAULT 1,
    onboarding_completed  BOOLEAN     NOT NULL DEFAULT FALSE,
    created_by            INTEGER     REFERENCES users (id) ON DELETE SET NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Membership is the single source of truth for tenant access. Every request
-- that names a store is checked against this table before any data is read.
CREATE TABLE IF NOT EXISTS store_members (
    id         SERIAL PRIMARY KEY,
    store_id   INTEGER     NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    user_id    INTEGER     NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role       TEXT        NOT NULL DEFAULT 'CASHIER'
                           CHECK (role IN ('OWNER', 'MANAGER', 'CASHIER')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (store_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_store_members_user ON store_members (user_id);

-- Per-store policy. Global env vars remain the defaults these are seeded from.
CREATE TABLE IF NOT EXISTS store_settings (
    store_id                  INTEGER PRIMARY KEY REFERENCES stores (id) ON DELETE CASCADE,
    low_stock_threshold       INTEGER        NOT NULL DEFAULT 10 CHECK (low_stock_threshold >= 0),
    default_tax_rate          NUMERIC(5, 2)  NOT NULL DEFAULT 0 CHECK (default_tax_rate >= 0),
    default_lead_time_days    INTEGER        NOT NULL DEFAULT 3 CHECK (default_lead_time_days >= 0),
    invoice_prefix            TEXT           NOT NULL DEFAULT 'INV',
    purchase_order_prefix     TEXT           NOT NULL DEFAULT 'PO',
    financial_year_start_month INTEGER       NOT NULL DEFAULT 4
                                             CHECK (financial_year_start_month BETWEEN 1 AND 12),
    timezone                  TEXT           NOT NULL DEFAULT 'Asia/Kolkata',
    critical_cover_days       NUMERIC(6, 2)  NOT NULL DEFAULT 2.0,
    medium_cover_buffer_days  NUMERIC(6, 2)  NOT NULL DEFAULT 3.0,
    overstock_cover_days      NUMERIC(6, 2)  NOT NULL DEFAULT 30.0,
    safety_days               INTEGER        NOT NULL DEFAULT 3,
    service_level_z           NUMERIC(5, 3)  NOT NULL DEFAULT 1.28,
    updated_at                TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Catalogue support tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS categories (
    id          SERIAL PRIMARY KEY,
    store_id    INTEGER     NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (store_id, name)
);

CREATE TABLE IF NOT EXISTS suppliers (
    id                     SERIAL PRIMARY KEY,
    store_id               INTEGER     NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    name                   TEXT        NOT NULL,
    contact_person         TEXT,
    phone                  TEXT,
    email                  TEXT,
    address                TEXT,
    gst_number             TEXT,
    default_lead_time_days INTEGER     NOT NULL DEFAULT 3 CHECK (default_lead_time_days >= 0),
    notes                  TEXT,
    is_active              BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_suppliers_store ON suppliers (store_id);

CREATE TABLE IF NOT EXISTS customers (
    id            SERIAL PRIMARY KEY,
    store_id      INTEGER        NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    name          TEXT           NOT NULL,
    phone         TEXT,
    email         TEXT,
    notes         TEXT,
    created_at    TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customers_store ON customers (store_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_store_phone
    ON customers (store_id, phone) WHERE phone IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Products: extend the single-tenant table in place
-- ---------------------------------------------------------------------------

ALTER TABLE products ADD COLUMN IF NOT EXISTS store_id       INTEGER REFERENCES stores (id) ON DELETE CASCADE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS barcode        TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS description    TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS brand          TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS unit           TEXT NOT NULL DEFAULT 'piece';
ALTER TABLE products ADD COLUMN IF NOT EXISTS cost_price     NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (cost_price >= 0);
ALTER TABLE products ADD COLUMN IF NOT EXISTS tax_rate       NUMERIC(5, 2)  NOT NULL DEFAULT 0 CHECK (tax_rate >= 0);
ALTER TABLE products ADD COLUMN IF NOT EXISTS supplier_id    INTEGER REFERENCES suppliers (id) ON DELETE SET NULL;
ALTER TABLE products ADD COLUMN IF NOT EXISTS is_active      BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE products ADD COLUMN IF NOT EXISTS updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- `unit_price` becomes `selling_price` now that a cost price exists alongside
-- it. The product repository still exposes a `unit_price` alias, because the
-- feature pipeline reads that key and its column list is part of the trained
-- model bundle.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'products' AND column_name = 'unit_price') THEN
        ALTER TABLE products RENAME COLUMN unit_price TO selling_price;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Sales: flat daily rows become invoice headers plus line items
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'sales' AND column_name = 'product_id') THEN
        ALTER TABLE sales RENAME TO legacy_sales;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS sales (
    id              SERIAL PRIMARY KEY,
    store_id        INTEGER        NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    invoice_number  TEXT           NOT NULL,
    customer_id     INTEGER        REFERENCES customers (id) ON DELETE SET NULL,
    customer_name   TEXT,
    customer_phone  TEXT,
    subtotal        NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    discount        NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (discount >= 0),
    tax             NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (tax >= 0),
    total           NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (total >= 0),
    cost_total      NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (cost_total >= 0),
    payment_method  TEXT           NOT NULL DEFAULT 'CASH'
                                   CHECK (payment_method IN ('CASH', 'UPI', 'CARD', 'MIXED', 'OTHER')),
    amount_received NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (amount_received >= 0),
    change_due      NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (change_due >= 0),
    status          TEXT           NOT NULL DEFAULT 'COMPLETED'
                                   CHECK (status IN ('COMPLETED', 'CANCELLED', 'RETURNED')),
    notes           TEXT,
    sale_date       DATE           NOT NULL,
    created_by      INTEGER        REFERENCES users (id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (store_id, invoice_number)
);

CREATE INDEX IF NOT EXISTS idx_sales_store_date ON sales (store_id, sale_date DESC);
CREATE INDEX IF NOT EXISTS idx_sales_store_created ON sales (store_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales (customer_id);

CREATE TABLE IF NOT EXISTS sale_items (
    id           SERIAL PRIMARY KEY,
    sale_id      INTEGER        NOT NULL REFERENCES sales (id) ON DELETE CASCADE,
    store_id     INTEGER        NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    product_id   INTEGER        NOT NULL REFERENCES products (id) ON DELETE RESTRICT,
    product_name TEXT           NOT NULL,
    sku          TEXT           NOT NULL,
    quantity     INTEGER        NOT NULL CHECK (quantity > 0),
    unit_price   NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    cost_price   NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (cost_price >= 0),
    discount     NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (discount >= 0),
    tax_rate     NUMERIC(5, 2)  NOT NULL DEFAULT 0 CHECK (tax_rate >= 0),
    tax_amount   NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    line_total   NUMERIC(12, 2) NOT NULL CHECK (line_total >= 0),
    sale_date    DATE           NOT NULL
);

-- The forecasting pipeline aggregates daily demand straight off this index.
CREATE INDEX IF NOT EXISTS idx_sale_items_product_date ON sale_items (product_id, sale_date);
CREATE INDEX IF NOT EXISTS idx_sale_items_store_date ON sale_items (store_id, sale_date);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items (sale_id);

CREATE TABLE IF NOT EXISTS payments (
    id         SERIAL PRIMARY KEY,
    sale_id    INTEGER        NOT NULL REFERENCES sales (id) ON DELETE CASCADE,
    store_id   INTEGER        NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    method     TEXT           NOT NULL CHECK (method IN ('CASH', 'UPI', 'CARD', 'OTHER')),
    amount     NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
    reference  TEXT,
    created_at TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payments_sale ON payments (sale_id);

-- ---------------------------------------------------------------------------
-- Inventory ledger
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS inventory_transactions (
    id              SERIAL PRIMARY KEY,
    store_id        INTEGER     NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    product_id      INTEGER     NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    type            TEXT        NOT NULL CHECK (type IN (
                        'SALE', 'PURCHASE', 'RETURN', 'DAMAGE',
                        'MANUAL_ADJUSTMENT', 'OPENING_STOCK')),
    quantity_change INTEGER     NOT NULL,
    quantity_before INTEGER     NOT NULL,
    quantity_after  INTEGER     NOT NULL,
    reference_type  TEXT,
    reference_id    INTEGER,
    notes           TEXT,
    created_by      INTEGER     REFERENCES users (id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inv_tx_store_created ON inventory_transactions (store_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inv_tx_product ON inventory_transactions (product_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Purchasing
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS purchase_orders (
    id                SERIAL PRIMARY KEY,
    store_id          INTEGER        NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    po_number         TEXT           NOT NULL,
    supplier_id       INTEGER        REFERENCES suppliers (id) ON DELETE SET NULL,
    status            TEXT           NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
                          'DRAFT', 'ORDERED', 'PARTIALLY_RECEIVED', 'RECEIVED', 'CANCELLED')),
    subtotal          NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    tax               NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (tax >= 0),
    total             NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (total >= 0),
    expected_delivery DATE,
    notes             TEXT,
    created_by        INTEGER        REFERENCES users (id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    received_at       TIMESTAMPTZ,
    UNIQUE (store_id, po_number)
);

CREATE INDEX IF NOT EXISTS idx_po_store_created ON purchase_orders (store_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_po_supplier ON purchase_orders (supplier_id);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id                SERIAL PRIMARY KEY,
    purchase_order_id INTEGER        NOT NULL REFERENCES purchase_orders (id) ON DELETE CASCADE,
    store_id          INTEGER        NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    product_id        INTEGER        NOT NULL REFERENCES products (id) ON DELETE RESTRICT,
    quantity          INTEGER        NOT NULL CHECK (quantity > 0),
    received_quantity INTEGER        NOT NULL DEFAULT 0 CHECK (received_quantity >= 0),
    cost_price        NUMERIC(10, 2) NOT NULL CHECK (cost_price >= 0),
    tax_rate          NUMERIC(5, 2)  NOT NULL DEFAULT 0 CHECK (tax_rate >= 0),
    line_total        NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (line_total >= 0)
);

CREATE INDEX IF NOT EXISTS idx_po_items_order ON purchase_order_items (purchase_order_id);
CREATE INDEX IF NOT EXISTS idx_po_items_product ON purchase_order_items (product_id);

-- ---------------------------------------------------------------------------
-- Business management
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS expenses (
    id             SERIAL PRIMARY KEY,
    store_id       INTEGER        NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    category       TEXT           NOT NULL,
    description    TEXT,
    amount         NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
    expense_date   DATE           NOT NULL,
    payment_method TEXT           NOT NULL DEFAULT 'CASH',
    notes          TEXT,
    created_by     INTEGER        REFERENCES users (id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_expenses_store_date ON expenses (store_id, expense_date DESC);

CREATE TABLE IF NOT EXISTS notifications (
    id         SERIAL PRIMARY KEY,
    store_id   INTEGER     NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    type       TEXT        NOT NULL CHECK (type IN ('CRITICAL', 'PURCHASE', 'ANOMALY', 'SYSTEM', 'STOCK')),
    severity   TEXT        NOT NULL DEFAULT 'INFO' CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
    title      TEXT        NOT NULL,
    message    TEXT        NOT NULL,
    link       TEXT,
    dedupe_key TEXT,
    is_read    BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_store ON notifications (store_id, created_at DESC);
-- Regenerating alerts must not pile up duplicates of the same open issue.
CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_dedupe
    ON notifications (store_id, dedupe_key) WHERE dedupe_key IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Forecasting provenance
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS forecast_runs (
    id          SERIAL PRIMARY KEY,
    store_id    INTEGER     NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    status      TEXT        NOT NULL DEFAULT 'COMPLETED'
                            CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED')),
    model_name  TEXT,
    rows_used   INTEGER,
    products    INTEGER,
    metrics     JSONB,
    error       TEXT,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    created_by  INTEGER     REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_forecast_runs_store ON forecast_runs (store_id, started_at DESC);

CREATE TABLE IF NOT EXISTS forecast_predictions (
    id                SERIAL PRIMARY KEY,
    forecast_run_id   INTEGER     NOT NULL REFERENCES forecast_runs (id) ON DELETE CASCADE,
    store_id          INTEGER     NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    product_id        INTEGER     NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    target_date       DATE        NOT NULL,
    predicted_demand  INTEGER     NOT NULL CHECK (predicted_demand >= 0),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (forecast_run_id, product_id, target_date)
);

CREATE INDEX IF NOT EXISTS idx_forecast_predictions_product
    ON forecast_predictions (product_id, target_date);

-- ---------------------------------------------------------------------------
-- Adopt single-tenant data into a demo tenant
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    demo_user_id  INTEGER;
    demo_store_id INTEGER;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM products WHERE store_id IS NULL) THEN
        RETURN;
    END IF;

    -- '!' is not a valid bcrypt hash, so this account cannot be logged into.
    -- scripts/seed_demo.py sets a real password when a demo login is wanted.
    INSERT INTO users (email, password_hash, full_name)
    VALUES ('demo@kirana-iq.local', '!', 'Demo Owner')
    ON CONFLICT (email) DO NOTHING;
    SELECT id INTO demo_user_id FROM users WHERE email = 'demo@kirana-iq.local';

    SELECT id INTO demo_store_id FROM stores WHERE is_demo = TRUE ORDER BY id LIMIT 1;
    IF demo_store_id IS NULL THEN
        INSERT INTO stores (name, owner_name, city, state, business_type, is_demo,
                            onboarding_step, onboarding_completed, created_by)
        VALUES ('Demo Store', 'Demo Owner', 'Hyderabad', 'Telangana', 'KIRANA', TRUE,
                4, TRUE, demo_user_id)
        RETURNING id INTO demo_store_id;
    END IF;

    INSERT INTO store_members (store_id, user_id, role)
    VALUES (demo_store_id, demo_user_id, 'OWNER')
    ON CONFLICT (store_id, user_id) DO NOTHING;

    INSERT INTO store_settings (store_id) VALUES (demo_store_id)
    ON CONFLICT (store_id) DO NOTHING;

    UPDATE products SET store_id = demo_store_id WHERE store_id IS NULL;

    INSERT INTO categories (store_id, name)
    SELECT DISTINCT demo_store_id, category FROM products WHERE store_id = demo_store_id
    ON CONFLICT (store_id, name) DO NOTHING;

    -- The single-tenant dataset had no cost prices, so margin analytics would
    -- read as 100%. Seed a plausible cost for the demo tenant only; this store
    -- is flagged is_demo precisely so its numbers are never mistaken for real.
    UPDATE products
       SET cost_price = ROUND(selling_price * 0.72, 2)
     WHERE store_id = demo_store_id AND cost_price = 0;

    -- Opening stock, so every unit currently on hand is explainable from the ledger.
    INSERT INTO inventory_transactions (store_id, product_id, type, quantity_change,
                                        quantity_before, quantity_after, reference_type, notes)
    SELECT demo_store_id, id, 'OPENING_STOCK', current_stock, 0, current_stock,
           'MIGRATION', 'Opening stock recorded when the store was created'
    FROM products
    WHERE store_id = demo_store_id
      AND NOT EXISTS (
          SELECT 1 FROM inventory_transactions t
          WHERE t.product_id = products.id AND t.type = 'OPENING_STOCK');

    -- Flat daily sales rows become one invoice each, preserving the demand
    -- history the forecasting model is trained on.
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_name = 'legacy_sales') THEN
        WITH inserted AS (
            INSERT INTO sales (store_id, invoice_number, subtotal, tax, total, cost_total,
                               payment_method, amount_received, status, sale_date, created_by)
            SELECT demo_store_id,
                   'LEG-' || ls.id,
                   ls.quantity * ls.unit_price,
                   0,
                   ls.quantity * ls.unit_price,
                   ls.quantity * p.cost_price,
                   'CASH',
                   ls.quantity * ls.unit_price,
                   'COMPLETED',
                   ls.sale_date,
                   demo_user_id
            FROM legacy_sales ls
            JOIN products p ON p.id = ls.product_id
            WHERE ls.quantity > 0
            RETURNING id, invoice_number, sale_date
        )
        INSERT INTO sale_items (sale_id, store_id, product_id, product_name, sku, quantity,
                                unit_price, cost_price, line_total, sale_date)
        SELECT inserted.id, demo_store_id, p.id, p.name, p.sku, ls.quantity,
               ls.unit_price, p.cost_price, ls.quantity * ls.unit_price, ls.sale_date
        FROM inserted
        JOIN legacy_sales ls ON inserted.invoice_number = 'LEG-' || ls.id
        JOIN products p ON p.id = ls.product_id;

        DROP TABLE legacy_sales;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Tenant constraints (applied after backfill)
-- ---------------------------------------------------------------------------

ALTER TABLE products ALTER COLUMN store_id SET NOT NULL;

-- SKUs and barcodes are unique per store, not globally: two shops can stock the
-- same product under the same code.
ALTER TABLE products DROP CONSTRAINT IF EXISTS products_sku_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_store_sku ON products (store_id, sku);
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_store_barcode
    ON products (store_id, barcode) WHERE barcode IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_products_store_active ON products (store_id, is_active);
CREATE INDEX IF NOT EXISTS idx_products_store_category ON products (store_id, category);
CREATE INDEX IF NOT EXISTS idx_products_supplier ON products (supplier_id);
DROP INDEX IF EXISTS idx_products_category;
