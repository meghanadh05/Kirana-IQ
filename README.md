# Kirana-IQ

AI-powered inventory forecasting system for small retail/kirana stores. Kirana-IQ
analyses historical sales data, forecasts SKU-level demand, and turns those
forecasts into concrete inventory decisions: stockout risk, reorder quantities,
and overstock alerts.

> **Status: Phase 2 complete.** The scaffold, synthetic dataset generator,
> PostgreSQL loader, and the product/sales CRUD API are working end to end and
> covered by 36 passing tests. Forecasting, inventory intelligence and the full
> dashboard are not implemented yet — see [Roadmap](#roadmap). Nothing in this
> README describes a feature that does not currently run.

---

## Problem Statement

A kirana store owner orders stock from intuition. That produces two costly
failures at once: fast-moving SKUs run out before the supplier's next delivery,
while slow-moving SKUs tie up working capital on the shelf. The owner cannot
answer, with numbers:

- What will likely sell over the next 7 days?
- Which products will run out before replenishment arrives?
- Which products are overstocked?
- How much should I reorder, and when?
- Which products are behaving unusually?

Kirana-IQ answers these from the store's own sales history.

## Core Pipeline

```
Historical Sales Data
        |
   Data Cleaning
        |
Feature Engineering
        |
 Machine Learning Model
        |
  Demand Forecast
        |
 Inventory Analysis
        |
  Stockout Risk
        |
Reorder Recommendation
        |
  React Dashboard
```

## Tech Stack

| Layer     | Technology                          |
| --------- | ----------------------------------- |
| Frontend  | React 18, Vite                      |
| Backend   | FastAPI, Uvicorn                    |
| Database  | PostgreSQL 16 (via psycopg 3, no ORM) |
| ML / Data | Python, scikit-learn, Pandas, NumPy |
| Tooling   | Docker, Docker Compose, GitHub Actions |

The database layer is deliberately a thin SQL wrapper around a psycopg
connection pool rather than an ORM, so every query in the project is readable
SQL.

## Data Model

**products** — `id`, `sku`, `name`, `category`, `unit_price`, `current_stock`,
`reorder_level`, `lead_time_days`

**sales** — `id`, `product_id` → `products.id`, `quantity`, `sale_date`,
`unit_price`

One product has many sales. The schema lives in
[backend/app/schema.sql](backend/app/schema.sql) and is applied idempotently at
application startup.

## Dataset

The repository ships a reproducible generator rather than a checked-in dump, so
the dataset can be regenerated or resized at will.

```bash
python scripts/generate_data.py            # defaults: --seed 42 --days 365
python scripts/load_data.py --truncate     # load the CSVs into PostgreSQL
```

Running with the defaults produces:

| Property   | Value                                |
| ---------- | ------------------------------------ |
| Products   | 30 SKUs                              |
| Categories | 7 (Dairy, Snacks, Beverages, Rice & Grains, Personal Care, Household, Bakery) |
| Period     | 2025-09-09 → 2026-09-08 (365 days)   |
| Sales rows | 10,902 (one row per product per day with sales) |
| Total units| 227,468                              |

Demand for a product on a day is a Poisson draw whose mean is built from
interpretable multiplicative components:

```
lambda = base_demand
         x day_of_week_factor    weekend uplift, category dependent
         x seasonal_factor       annual sine wave, peaks in the category's month
         x trend_factor          linear growth or decline across the window
         x event_factor          festival spikes from data/events.csv
         x payday_factor         month-start salary effect
```

Because each component is explicit, the series contains structure a model can
actually learn. Measured on the default seed:

| Signal                    | Evidence in the generated data                |
| ------------------------- | --------------------------------------------- |
| Weekend effect            | Sat/Sun average 725 units vs. weekday 583 (1.24x) |
| Festival spike            | Snacks around Diwali: 224 → 408 daily units (+82%) |
| Seasonality               | Beverages: 122 units/day in January vs. 186 in May |
| Inventory mix             | 8 SKUs under 3 days of cover, 16 healthy, 6 over 30 days |

`--seed` makes runs byte-identical; a different seed produces a different store.

### Event Signals

[data/events.csv](data/events.csv) holds 45 rows covering Indian festivals in the
generated window — Navratri, Dussehra, Diwali, Chhath Puja, Christmas, New Year,
Sankranti, Republic Day, Maha Shivaratri, Holi, Ugadi, Eid al-Fitr, Ram Navami,
Tamil New Year, Eid al-Adha, Independence Day, Raksha Bandhan and Janmashtami.

```csv
date,event_name,affected_category,impact_score
2025-10-20,Diwali,Household,0.60
2026-03-04,Holi,Snacks,0.55
```

One event can have several rows, one per affected category, so Diwali can lift
Household by 60% and Rice & Grains by 40%. `affected_category` may be `ALL`.
Uplift ramps over the three days *before* the event (shoppers stock up in
advance) and decays the day after.

Festival dates are approximate — several are lunar and shift year to year. The
file is a plain CSV read at generation time, so a real calendar API can replace
it later without touching the generator.

## API Endpoints

Implemented today:

| Method | Path                        | Description                                       |
| ------ | --------------------------- | ------------------------------------------------- |
| GET    | `/`                         | Service name, version, link to docs               |
| GET    | `/health`                   | Liveness probe; reports PostgreSQL connectivity   |
| GET    | `/docs`                     | Interactive OpenAPI documentation                 |
| GET    | `/products`                 | List products; `category`, `search`, `limit`, `offset` |
| GET    | `/products/categories`      | Distinct categories, for the dashboard filter     |
| GET    | `/products/{id}`            | One product; 404 when absent                      |
| POST   | `/products`                 | Create a product; 409 on duplicate SKU            |
| GET    | `/sales/{product_id}`       | Sales history; `start_date`, `end_date`, `limit`  |
| GET    | `/sales/{product_id}/summary` | Record count, total units, first/last sale date |
| POST   | `/sales`                    | Record a sale; 404 when the product is unknown    |

Example `/health` response:

```json
{
  "status": "ok",
  "app": "Kirana-IQ",
  "version": "0.1.0",
  "environment": "development",
  "database": "connected"
}
```

`status` is `degraded` and `database` is `unavailable` when PostgreSQL cannot be
reached; the API stays up so the failure is visible rather than fatal.

Example — `GET /sales/1?start_date=2026-09-01`:

```json
[
  { "id": 1, "product_id": 1, "quantity": 55, "sale_date": "2026-09-01", "unit_price": "33.00" },
  { "id": 2, "product_id": 1, "quantity": 66, "sale_date": "2026-09-02", "unit_price": "33.00" }
]
```

Validation is enforced at the edge by Pydantic: negative prices, negative
quantities, malformed dates and inverted date ranges return `422`; unknown ids
return `404`; duplicate SKUs return `409`.

Planned in later phases: `/train`, `/forecast/{id}`,
`/inventory/recommendations`, `/analytics/overview`.

## Installation

### Option A — Docker (recommended)

```bash
git clone <repository-url>
cd Kirana-IQ
cp .env.example .env
docker compose up --build
```

Then seed the database (in a second terminal):

```bash
python scripts/generate_data.py
python scripts/load_data.py --truncate
```

Services:

- Frontend — http://localhost:5173
- Backend — http://localhost:8000 (docs at http://localhost:8000/docs)
- PostgreSQL — `localhost:5432`

### Option B — Local development

PostgreSQL must be reachable. The quickest way is to run just the database
container:

```bash
docker compose up -d db
```

Backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

### Environment Variables

Copy `.env.example` to `.env` at the repository root. All backend settings are
read from the environment via `pydantic-settings`.

| Variable            | Default                 | Purpose                              |
| ------------------- | ----------------------- | ------------------------------------ |
| `ENVIRONMENT`       | `development`           | Reported by `/health`                |
| `POSTGRES_HOST`     | `localhost`             | Database host (`db` inside Docker)   |
| `POSTGRES_PORT`     | `5432`                  | Database port                        |
| `POSTGRES_DB`       | `kirana_iq`             | Database name                        |
| `POSTGRES_USER`     | `kirana`                | Database user                        |
| `POSTGRES_PASSWORD` | `kirana`                | Database password                    |
| `CORS_ORIGINS`      | `http://localhost:5173` | Comma-separated allowed origins      |
| `VITE_API_BASE_URL` | `http://localhost:8000` | API base URL baked into the frontend |

## Testing

```bash
cd backend
pytest -v
```

36 tests, all passing. They need a reachable PostgreSQL (`docker compose up -d db`)
and clean up any rows they create.

| File                       | Covers                                                     |
| -------------------------- | ---------------------------------------------------------- |
| `test_health.py`           | `/health` shape, `/` root                                  |
| `test_products.py`         | Creation, retrieval, filtering, search, pagination, 404/409/422 |
| `test_sales.py`            | Sale creation, chronological history, date filtering, summary aggregation, validation |
| `test_data_generation.py`  | Reproducibility, unique SKUs, positive integer quantities, weekend uplift, festival uplift, stock-cover mix |

The generator tests are the interesting ones: they assert that the synthetic
data actually contains the weekly and festival structure the forecasting model
will be asked to learn.

## Continuous Integration

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on every push and pull
request to `main`:

- **backend** — spins up a PostgreSQL service container, installs
  `backend/requirements.txt`, runs `pytest`
- **frontend** — `npm install`, `npm run build`

## Project Structure

```
Kirana-IQ/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, CORS, lifespan, /health
│   │   ├── config.py          # Env-driven settings
│   │   ├── database.py        # psycopg connection pool + SQL helpers
│   │   ├── schema.sql         # products / sales DDL
│   │   ├── routes/            # products.py, sales.py (forecast/inventory next)
│   │   ├── models/            # product.py, sale.py — SQL access functions
│   │   ├── schemas/           # product.py, sale.py — Pydantic models
│   │   ├── services/          # (phase 3+) forecast, inventory, analytics
│   │   └── ml/                # (phase 3+) features, training, prediction
│   ├── tests/
│   ├── Dockerfile
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/api.js    # API client
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── Dockerfile
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── data/
│   ├── events.csv             # festival calendar (committed)
│   ├── products.csv           # generated, git-ignored
│   └── sales.csv              # generated, git-ignored
├── models/                    # (phase 3) saved scikit-learn models
├── scripts/
│   ├── generate_data.py       # reproducible synthetic dataset
│   └── load_data.py           # CSV -> PostgreSQL via COPY
├── .github/workflows/ci.yml
├── docker-compose.yml
├── .env.example
└── README.md
```

## Roadmap

| Phase | Scope                                                              |
| ----- | ------------------------------------------------------------------ |
| 1 ✅  | Scaffold: FastAPI, React, PostgreSQL, env config, `/health`, Docker, CI |
| 2 ✅  | Synthetic dataset generator, events dataset, product & sales CRUD endpoints |
| 3     | Feature engineering, moving-average baseline, scikit-learn model, evaluation |
| 4     | Forecast API, inventory intelligence, stockout risk, reorder recommendations |
| 5     | Anomaly detection, analytics endpoints                             |
| 6     | Full React dashboard: Dashboard, Products, Forecast, Inventory, Analytics |

Model evaluation results (MAE / RMSE / WAPE, baseline vs. ML) will be published
here once phase 3 has actually been trained and measured. No metrics are quoted
before they are produced.

## Future Improvements

- Real event/festival signals from an external calendar API
- Per-category and store-wide aggregate forecasting
- Supplier lead-time learning from actual delivery history
- Authentication and multi-store support

## License

See [LICENSE](LICENSE).
