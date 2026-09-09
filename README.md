# Kirana-IQ

AI-powered demand forecasting and inventory intelligence for small retail and kirana stores.

Kirana-IQ analyses historical sales data, forecasts SKU-level demand, and converts those predictions into practical inventory decisions such as stockout risk, reorder quantities, overstock alerts, and demand anomalies.

**Status: Complete** — 181 backend tests and 20 frontend tests passing.

## Overview

Small retail stores often manage inventory using intuition. This can lead to:

- Fast-moving products going out of stock
- Excess inventory tying up working capital
- Poor visibility into future demand
- Missed seasonal and festival demand spikes

Kirana-IQ helps answer:

- What will likely sell in the next 7, 14, or 30 days?
- Which products may run out before the supplier delivers?
- How much should be reordered?
- Which products are overstocked?
- Which products are showing unusual demand?

## Features

- SKU-level demand forecasting
- 7, 14, and 30-day forecasts
- Stockout risk classification
- Reorder quantity recommendations
- Safety-stock calculation
- Overstock detection
- Demand anomaly detection
- Festival-aware forecasting
- Product and category analytics
- Interactive React dashboard
- Automated model evaluation
- Docker-based development setup
- GitHub Actions CI

## Tech Stack

| Layer | Technology |
| ----- | ---------- |
| Frontend | React 18, Vite |
| Backend | FastAPI, Uvicorn |
| Database | PostgreSQL 16, psycopg 3 |
| ML / Data | Python, Pandas, NumPy, scikit-learn |
| Testing | Pytest, Vitest, Testing Library |
| DevOps | Docker, Docker Compose, GitHub Actions |

## Architecture

```
Historical Sales
      ↓
Data Cleaning
      ↓
Feature Engineering
      ↓
Demand Forecasting Model
      ↓
7 / 14 / 30 Day Forecast
      ↓
Inventory Intelligence
      ↓
Stockout Risk
Reorder Quantity
Overstock Alerts
      ↓
React Dashboard
```

The backend follows a simple layered architecture:

```
routes → services → ml / models → PostgreSQL
```

- [`routes`](backend/app/routes) handle HTTP validation
- [`services`](backend/app/services) contain business logic
- [`ml`](backend/app/ml) handles forecasting and feature engineering
- [`models`](backend/app/models) contain SQL/database access

## Dataset

Kirana-IQ includes a reproducible synthetic retail dataset generator.

Default dataset:

| Property | Value |
| -------- | ----- |
| Products | 30 SKUs |
| Categories | 7 |
| Period | 365 days |
| Sales rows | 10,902 |
| Total units | 227,468 |

Categories include:

Dairy, Snacks, Beverages, Rice & Grains, Personal Care, Household, and Bakery.

Generate the dataset with:

```bash
python scripts/generate_data.py
python scripts/load_data.py --truncate
```

The generator models:

- Weekly demand patterns
- Seasonal trends
- Product trends
- Festival demand
- Payday effects
- Random demand variation

## Festival-Aware Forecasting

The project includes an Indian festival calendar containing events such as:

- Diwali
- Holi
- Sankranti
- Ugadi
- Eid
- Christmas
- Janmashtami
- Independence Day
- Raksha Bandhan

Different festivals can affect different product categories with different impact scores.

Example:

```csv
date,event_name,affected_category,impact_score
2025-10-20,Diwali,Household,0.60
2026-03-04,Holi,Snacks,0.55
```

## Feature Engineering

The model uses 26 features, including:

- Day of week
- Month
- Weekend flag
- Lag 1 / 7 / 14 / 30
- Rolling averages
- Rolling standard deviation
- Short-term and long-term growth
- Product price
- Product category
- Festival signals
- Upcoming festival impact
- Promotion signals

All lag and rolling features are shifted before calculation to prevent target leakage.

```python
past = frame["quantity"].shift(1)
frame["rolling_mean_7"] = past.rolling(7).mean()
frame["rolling_std_7"] = past.rolling(7).std()
```

## Machine Learning

Kirana-IQ trains one global model across all SKUs.

Two candidate models are evaluated:

- `RandomForestRegressor`
- `HistGradientBoostingRegressor`

Training uses a chronological:

```
70% Training
15% Validation
15% Test
```

The validation set selects the best model. The test set remains untouched until final evaluation.

### Test Results

| Model | MAE | RMSE | WAPE |
| ----- | --- | ---- | ---- |
| 7-Day Moving Average | 5.062 | 7.526 | 24.27% |
| HistGradientBoosting | 4.474 | 6.533 | **21.45%** |

The selected model achieves approximately 11.6% lower WAPE than the baseline.

### Recursive Forecast Backtest

| Horizon | Baseline WAPE | Model WAPE | Improvement |
| ------- | ------------- | ---------- | ----------- |
| 7 days | 24.62% | 20.54% | 16.6% |
| 14 days | 24.03% | 20.19% | 16.0% |
| 30 days | 23.63% | 19.82% | 16.1% |

## Inventory Intelligence

Forecasts are converted into actionable inventory recommendations.

### Stock Cover

```
stock_cover_days =
current_stock / average_daily_forecast
```

### Stockout Risk

| Risk | Condition |
| ---- | --------- |
| `CRITICAL` | ≤ 2 days of stock |
| `HIGH` | Stock runs out before supplier lead time |
| `MEDIUM` | Cover is within 3 days beyond lead time |
| `LOW` | Healthy stock level |

### Reorder Quantity

```
replenishment_window =
lead_time_days + safety_days

target_stock =
forecast_demand + safety_stock

reorder_quantity =
max(0, target_stock - current_stock)
```

Safety stock uses demand variability:

```
safety_stock =
z × daily_std × sqrt(replenishment_window)
```

## Example Recommendation

```json
{
  "sku": "PCR-002",
  "name": "Dove Soap 100g",
  "current_stock": 7,
  "expected_7_day_demand": 71,
  "stock_cover_days": 0.7,
  "lead_time_days": 6,
  "risk": "CRITICAL",
  "recommended_reorder_quantity": 95
}
```

Example explanation:

> Only 0.7 days of stock remain while the supplier takes 6 days. Reorder 95 units now.

## Anomaly Detection

Kirana-IQ detects unusual changes in demand by comparing recent sales with historical behaviour.

An anomaly must satisfy both:

- Relative change ≥ 25%
- Absolute z-score ≥ 2.0

This helps avoid noisy alerts for products with naturally unstable demand.

## Dashboard

The React application contains five pages:

| Page | Purpose |
| ---- | ------- |
| Dashboard | Inventory overview, demand trend, anomalies, urgent reorders |
| Products | Search and filter the product catalogue |
| Forecast | View SKU forecasts for 7/14/30 days |
| Inventory | Stockout risk and reorder recommendations |
| Analytics | Category trends, top sellers, slow movers and anomalies |

### Dashboard

![Dashboard](docs/screenshots/dashboard.png)

### Forecast

![Forecast](docs/screenshots/forecast.png)

### Inventory

![Inventory](docs/screenshots/inventory.png)

### Analytics

![Analytics](docs/screenshots/analytics.png)

### Products

![Products](docs/screenshots/products.png)

## API

Important endpoints:

| Method | Endpoint | Purpose |
| ------ | -------- | ------- |
| `GET` | `/health` | Service and database health |
| `GET` | `/products` | List products |
| `POST` | `/products` | Create product |
| `GET` | `/sales/{product_id}` | Product sales history |
| `POST` | `/sales` | Record sale |
| `GET` | `/forecast/{id}?days=7` | Demand forecast |
| `GET` | `/inventory/recommendations` | Reorder recommendations |
| `GET` | `/inventory/summary` | Inventory overview |
| `GET` | `/analytics/overview` | Dashboard analytics |
| `GET` | `/analytics/anomalies` | Demand anomalies |
| `GET` | `/analytics/top-products` | Top-selling products |
| `GET` | `/analytics/slow-moving` | Slow-moving products |
| `GET` | `/analytics/category-trends` | Category performance |
| `POST` | `/train` | Retrain forecasting model |
| `GET` | `/model` | Current model information |

Interactive API documentation is available at:

```
http://localhost:8000/docs
```

## Running the Project

### Quick Start

```bash
./start.sh          # build, seed, train and serve
./stop.sh           # stop everything, keep the data
```

`start.sh` is idempotent: it seeds only when the database is empty and trains only when no model exists. Run `./start.sh --help` for all options.

### Docker

```bash
git clone <repository-url>
cd Kirana-IQ
cp .env.example .env
docker compose up --build
```

Generate and load sample data:

```bash
python scripts/generate_data.py
python scripts/load_data.py --truncate
```

Train the model:

```bash
cd backend
python -m app.ml.train_model
```

Run evaluation:

```bash
python -m app.ml.evaluate
```

Open:

| Service | URL |
| ------- | --- |
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

## Local Development

### Database

```bash
docker compose up -d db
```

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Testing

### Backend

```bash
cd backend
pytest -v
```

**181 backend tests**

Coverage includes:

- APIs
- Feature engineering
- Leakage prevention
- Dataset generation
- Forecasting
- Model evaluation
- Inventory calculations
- Anomaly detection
- Analytics

### Frontend

```bash
cd frontend
npm test
```

**20 frontend tests**

## CI/CD

GitHub Actions runs on pushes and pull requests to `main`.

The pipeline:

```
Start PostgreSQL
      ↓
Install dependencies
      ↓
Generate dataset
      ↓
Load PostgreSQL
      ↓
Train ML model
      ↓
Run backend tests
      ↓
Run frontend tests
      ↓
Build frontend
```

CI fails if required tests are skipped.

## Project Structure

```
Kirana-IQ/
├── backend/
│   ├── app/
│   │   ├── routes/
│   │   ├── services/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── ml/
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── services/
│   └── package.json
│
├── data/
├── models/
├── scripts/
├── docs/screenshots/
├── .github/workflows/ci.yml
├── docker-compose.yml
├── docker-compose.prod.yml
└── README.md
```

## Current Results

On the default generated catalogue:

- 30 SKUs
- 6 critical stock risks
- 2 high risks
- 3 medium risks
- 19 low risks
- 6 overstocked products
- 1,248 units recommended for reorder
- 21.45% test WAPE
- ~16% improvement over the recursive moving-average baseline

## Limitations

- Dataset is currently synthetic
- Forecasts are point estimates without confidence intervals
- Forecast cache is process-local
- Model retraining is synchronous
- Future promotions are not currently known
- Multi-store authentication is not implemented

## Future Improvements

- Real POS/store data integration
- Multi-store support
- Authentication and user accounts
- Supplier management
- Automatic purchase-order generation
- Prediction intervals
- External festival/calendar API
- Supplier lead-time learning
- Store-level and category-level forecasting
- Cloud deployment

## License

See [LICENSE](LICENSE).
