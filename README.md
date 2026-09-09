# Kirana-IQ

Intelligent POS, inventory and demand forecasting for small retail stores.

Kirana-IQ is a complete retail platform: bill customers at the counter, track every unit of stock, buy from suppliers, and let a demand model trained on your own sales tell you what to reorder and when.

**Status:** 371 backend tests and 83 frontend tests passing.

## The idea

Most small stores manage inventory by intuition, which produces the same three problems everywhere: fast movers run out, slow movers tie up cash, and nobody can say what next week will sell.

Forecasting alone does not fix that. A prediction is only useful where it changes a decision, so in Kirana-IQ the model is wired into the places decisions actually get made:

```
Sell at the counter  →  sales history builds itself
        ↓
Demand model trains on that history
        ↓
Stockout risk and reorder quantities
        ↓
Purchase order, grouped by supplier
        ↓
Receive delivery, stock rises, ledger records why
```

There is no separate data-entry step. The model learns from the invoices you were going to create anyway.

## What it does

**Selling**
- Barcode or keyboard-driven POS with a persistent scan field
- Cash, UPI, card and split payments, with change calculation
- Printable 80mm thermal receipts
- Held sales, discounts, optional customer capture
- Sales history with filtering, and cancellation that returns stock

**Stock**
- A full inventory ledger: every unit is explained by a movement
- Adjustments for damage, expiry, loss, counts and opening stock
- Live valuation at cost and at retail
- Low-stock and out-of-stock tracking against per-product reorder levels

**Buying**
- Suppliers with lead times, product assignments and purchase history
- Purchase orders with an enforced lifecycle and partial receiving
- Reorder recommendations grouped by supplier, one click from becoming an order

**Intelligence**
- SKU-level demand forecasting at 7, 14 and 30 days
- Stockout risk classification and safety-stock-sized reorder quantities
- Demand anomaly detection
- Sales, product, inventory, category and profit analytics
- Nine CSV reports

**Running the business**
- Multi-tenant: users, stores, and roles (owner, manager, cashier)
- Store onboarding wizard, per-store policy, team management
- Customers, expenses and estimated operating profit
- In-app alerts, global ⌘K search

## Tech stack

| Layer | Technology |
| ----- | ---------- |
| Frontend | React 18, Vite, React Router |
| Backend | FastAPI, Uvicorn |
| Database | PostgreSQL 16, psycopg 3 (hand-written SQL, no ORM) |
| Auth | bcrypt, JWT |
| ML / Data | Python, Pandas, NumPy, scikit-learn |
| Testing | Pytest, Vitest, Testing Library |
| DevOps | Docker, Docker Compose, GitHub Actions |

## Architecture

```
routes  →  services  →  models (SQL)  →  PostgreSQL
                ↓
               ml
```

- [`routes`](backend/app/routes) validate requests and nothing else — no SQL, no business rules
- [`services`](backend/app/services) hold the business logic and own transactions
- [`models`](backend/app/models) are the repository layer: plain functions over psycopg
- [`ml`](backend/app/ml) is feature engineering, training and prediction, independent of HTTP

### Multi-tenancy

Every business record belongs to a `store_id`, and every repository read takes one — there is no unscoped variant, because a query without a tenant filter is a data leak waiting for its first bug.

Access is resolved once, in [`app/deps.py`](backend/app/deps.py), by reading the caller's membership from the database. A store id in a header is a *claim*, never a grant. Roles are enforced the same way: hiding a button is presentation, the dependency is the enforcement.

### Transactions

POS checkout writes an invoice, its line items, its payments, and one stock movement plus one ledger row per line. All of it happens on one connection inside one transaction. Products are locked in id order so concurrent carts cannot deadlock, and any failure rolls back the whole sale. Receiving a delivery works the same way in reverse.

`products.current_stock` is a cache of the ledger, never updated without an `inventory_transactions` row on the same connection — so the stock figure is always explainable, not merely asserted.

## Dataset

Kirana-IQ ships a reproducible synthetic retail dataset generator, used as a **demo store** so the product can be explored with real-looking history from the first minute.

| Property | Value |
| -------- | ----- |
| Products | 30 SKUs across 7 categories |
| Period | 365 days |
| Invoices | 365 |
| Sale lines | 10,902 |
| Total units | 227,468 |

The generator models weekly patterns, seasonality, per-product trend, festival demand, payday effects and Poisson noise. It also emits cost prices, barcodes, brands and per-category tax rates.

```bash
python scripts/generate_data.py
python scripts/seed_demo.py --reset --train
```

Seeded stores are flagged `is_demo` and the demo account lives on a `demo.` subdomain, so synthetic data is never mistaken for a real shop's.

## Festival-aware forecasting

The project includes an Indian festival calendar — Diwali, Holi, Sankranti, Ugadi, Eid, Christmas, Janmashtami, Independence Day, Raksha Bandhan — where different festivals affect different categories with different impact scores.

```csv
date,event_name,affected_category,impact_score
2025-10-20,Diwali,Household,0.60
2026-03-04,Holi,Snacks,0.55
```

Events are known months ahead, so using tomorrow's Diwali flag to predict tomorrow's demand is not leakage — it is exactly what a shop owner does when ordering.

## Feature engineering

26 features: calendar (day of week, month, weekend), lags (1/7/14/30), rolling mean and standard deviation, short- and long-term growth, price, category, festival signals and promotion flags.

Every lag and rolling statistic is computed on a shifted series, so a feature for date D can only use information available before the end of D-1:

```python
past = frame["quantity"].shift(1)
frame["rolling_mean_7"] = past.rolling(7).mean()
frame["rolling_std_7"] = past.rolling(7).std()
```

Days with no sales are reindexed onto a complete calendar and filled with zero — a day with no sales is a real zero, and dropping it would teach the model that demand never falls to nothing.

## Machine learning

Each store trains its own model on its own sales, written to `models/store_<id>/`. A store falls back to a shared starter model until it has trained one, so forecasting works from day 31 rather than never.

Two candidates are evaluated:

- `RandomForestRegressor`
- `HistGradientBoostingRegressor`

Splits are chronological — 70% train, 15% validation, 15% test. The validation window selects the model; the test window stays untouched until the winner is fixed.

### Test results

| Model | MAE | RMSE | WAPE |
| ----- | --- | ---- | ---- |
| 7-Day Moving Average | 5.062 | 7.526 | 24.27% |
| HistGradientBoosting | 4.474 | 6.533 | **21.45%** |

Approximately 11.6% lower WAPE than the baseline.

### Recursive forecast backtest

Longer horizons are produced recursively — predict tomorrow, append it as if observed, rebuild the lags, predict again. Error compounds with the horizon, and `evaluate_horizon` measures exactly how much:

| Horizon | Baseline WAPE | Model WAPE | Improvement |
| ------- | ------------- | ---------- | ----------- |
| 7 days | 24.62% | 20.54% | 16.6% |
| 14 days | 24.03% | 20.19% | 16.0% |
| 30 days | 23.63% | 19.82% | 16.1% |

## Inventory intelligence

### Stock cover

```
stock_cover_days = current_stock / average_daily_forecast
```

### Stockout risk

Deliberately lead-time relative: two days of cover is fine with a daily supplier and dangerous with a weekly one.

| Risk | Condition |
| ---- | --------- |
| `CRITICAL` | ≤ 2 days of stock |
| `HIGH` | Stock runs out before the supplier lead time |
| `MEDIUM` | Cover is within 3 days beyond the lead time |
| `LOW` | Healthy stock level |

### Reorder quantity

```
replenishment_window = lead_time_days + safety_days
target_stock         = forecast_demand + safety_stock
reorder_quantity     = max(0, target_stock - current_stock)

safety_stock = z × daily_std × sqrt(replenishment_window)
```

The square root is the point: forecast error accumulates with the square root of time, so a 9-day window needs three times the buffer of a 1-day window, not nine times.

Every threshold above is per store, configurable in Settings. Environment variables are only the defaults a new store starts from.

### Example recommendation

```json
{
  "sku": "PCR-002",
  "name": "Dove Soap 100g",
  "current_stock": 7,
  "expected_7_day_demand": 71,
  "stock_cover_days": 0.7,
  "lead_time_days": 6,
  "risk": "CRITICAL",
  "recommended_reorder_quantity": 95,
  "reason": "Only 0.7 days of stock left and the supplier takes 6 days. This product will very likely run out before replenishment arrives — reorder 95 units now."
}
```

The reasoning travels with the number, because a quantity nobody can explain is a quantity nobody trusts. In the UI, that recommendation carries a **Create purchase order** button that pre-fills the supplier, quantity and expected cost.

## Anomaly detection

Recent demand is compared against each product's own earlier baseline. An anomaly must clear both gates:

- Relative change ≥ 25%
- Absolute z-score ≥ 2.0

Percentage alone fires constantly on low-volume products; z-score alone flags trivial moves on steady ones.

## Profit reporting

Metrics are labelled for what they actually are:

```
net revenue    = revenue − tax collected
gross profit   = net revenue − cost of goods sold
estimated operating profit = gross profit − recorded expenses
```

Tax collected is not the shop's money, so it never counts as revenue. And the last line is explicitly an *estimate*: it only subtracts costs somebody typed into the expenses screen, which is not the same as an accounting result. A margin on zero revenue is reported as undefined, not as 0%.

## Application

| Area | Pages |
| ---- | ----- |
| Overview | Command centre: what needs attention today, and the actions that follow |
| Sell | POS, sales history, sale detail with printable receipt |
| Catalogue | Products, product detail, categories, CSV import/export |
| Inventory | Stock position, movement ledger, adjustments |
| Buying | Suppliers, supplier detail, purchase orders, order builder |
| Intelligence | Forecasting, analytics, alerts |
| Business | Customers, expenses, reports |
| Settings | Store profile, policy, tax and invoicing, team, account |

Plus a public landing page, sign-up, sign-in, password reset and a four-step store onboarding wizard.

## API

Roughly 70 endpoints. The main ones:

| Method | Endpoint | Purpose |
| ------ | -------- | ------- |
| `POST` | `/auth/register` · `/auth/login` | Create an account, sign in |
| `GET` | `/auth/me` | Current user and their stores |
| `POST` | `/stores` | Create a store (creator becomes owner) |
| `GET`/`PATCH` | `/stores/current/settings` | Per-store policy |
| `GET`/`POST` | `/products` | Catalogue |
| `GET` | `/products/barcode/{code}` | POS scan lookup |
| `POST` | `/products/import` | CSV import |
| `POST` | `/pos/checkout` | Complete a sale (atomic) |
| `GET` | `/sales` · `/sales/{id}` | Invoice history and detail |
| `GET` | `/inventory` · `/inventory/movements` | Stock position and ledger |
| `POST` | `/inventory/adjustments` | Correct stock, with a reason |
| `GET` | `/inventory/recommendations` | Reorder advice |
| `GET` | `/purchase-orders/suggestions` | Recommendations grouped by supplier |
| `POST` | `/purchase-orders/from-recommendations` | Turn advice into a draft order |
| `POST` | `/purchase-orders/{id}/receive` | Book in a delivery |
| `GET` | `/forecast/{id}?days=7` | Demand forecast |
| `POST` | `/train` | Retrain this store's model |
| `GET` | `/dashboard` · `/briefing` | Overview data |
| `GET` | `/analytics/{sales,products,inventory,categories,profit}` | Business analytics |
| `GET` | `/reports/{report}` | CSV download |

Requests carry `Authorization: Bearer <token>` and `X-Store-Id: <id>`. Interactive documentation is at http://localhost:8000/docs.

## Running the project

### Quick start

```bash
./start.sh          # build, seed, train and serve
./stop.sh           # stop everything, keep the data
```

`start.sh` is idempotent: it seeds only when the demo store is empty and trains only when no model exists. Run `./start.sh --help` for all options.

Sign in to the demo store with **demo@demo.kirana-iq.com** / **demo12345**, or create your own account.

### Docker

```bash
cp .env.example .env
docker compose up --build
```

Then seed and train:

```bash
python scripts/generate_data.py
python scripts/seed_demo.py --reset --train
```

| Service | URL |
| ------- | --- |
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

### Local development

```bash
docker compose up -d db                       # database only

python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000

cd frontend && npm install && npm run dev
```

### Database migrations

The schema lives in [`backend/app/migrations`](backend/app/migrations) as numbered SQL files, applied in filename order at startup and recorded in `schema_migrations`. Each runs in its own transaction and is applied at most once. To change the schema, add a new file — never edit one that has shipped.

## Testing

### Backend

```bash
cd backend && pytest -v
```

**371 tests.** Coverage includes authentication and password hashing, tenant isolation, role authorisation, product CRUD and validation, CSV import, POS checkout, stock deduction, transaction rollback, the inventory ledger, purchase order receiving, customers, expenses, store settings, feature engineering and leakage prevention, forecasting mechanics, model training, inventory maths and anomaly detection.

The tenancy tests assert on HTTP responses rather than on internal helpers, because the guarantee being tested is about the API surface. The suite cleans up after itself, so it is safe to run against a database you are also developing on.

### Frontend

```bash
cd frontend && npm test
```

**83 tests.** Covering sign-in, POS cart behaviour and stock limits, barcode scanning, the checkout modal, product creation and validation, inventory filtering and adjustments, the purchase order builder, plus a smoke test that mounts all 21 pages.

## CI/CD

GitHub Actions runs on pushes and pull requests to `main`:

```
Start PostgreSQL → install deps → generate dataset → seed demo store
→ train model → backend tests → frontend tests → build frontend
```

CI fails if any test is skipped: the suite skips gracefully when the demo store or model is missing, which is right for a fresh clone and wrong in CI, where a skip means the environment is broken.

## Security

- Passwords hashed with bcrypt; over-length passwords are rejected rather than silently truncated
- JWT sessions; the user record is re-read per request, so a deactivated account stops working before its token expires
- Tenant isolation enforced at the dependency layer, before any query runs
- Role authorisation enforced server-side, not by hiding UI
- All SQL parameterised; sort columns whitelisted
- Explicit CORS allowlist, never `*` with credentials
- Startup refuses to serve a non-development environment with the default JWT secret
- Unhandled errors are logged in full and returned as a generic message — a stack trace in a client response leaks table names, paths and library versions

## Project structure

```
Kirana-IQ/
├── backend/
│   ├── app/
│   │   ├── migrations/        numbered SQL migrations
│   │   ├── routes/            HTTP validation only
│   │   ├── services/          business logic and transactions
│   │   ├── models/            SQL repository layer
│   │   ├── schemas/           Pydantic request/response models
│   │   ├── ml/                features, training, prediction
│   │   ├── deps.py            auth, tenancy and role dependencies
│   │   └── errors.py          domain errors → HTTP status codes
│   └── tests/
│
├── frontend/
│   └── src/
│       ├── components/{ui,layout,charts}
│       ├── pages/{auth,onboarding,pos,sales,catalog,inventory,purchasing,intelligence,business}
│       ├── context/           auth and toasts
│       ├── hooks/             useApi, useDebounce, useHotkey
│       ├── services/api.js    the only place that knows about HTTP
│       └── styles/            design tokens and component styles
│
├── data/  models/  scripts/
├── .github/workflows/ci.yml
├── docker-compose.yml  docker-compose.prod.yml
└── README.md
```

## Current results

On the demo dataset:

- 30 SKUs, 365 days, 227,468 units sold
- 6 critical stock risks, 2 high, 3 medium, 19 low
- 6 overstocked products
- 1,248 units recommended for reorder
- 21.45% test WAPE, ~16% better than the recursive moving-average baseline

## Limitations

Worth being straight about:

- The bundled dataset is synthetic. The pipeline is real; the shop is not.
- Forecasts are point estimates with no confidence intervals.
- Model retraining is synchronous. The service is structured so a background worker could replace it, but today it runs on the request thread.
- The forecast cache is process-local, so it does not survive a restart or span replicas.
- Password reset records the request but does not send email — there is no mail provider wired up.
- Future promotions are not known to the model.
- Returns are recorded as a whole-sale cancellation; partial line-level returns are not implemented.

## License

MIT — see [LICENSE](LICENSE).
