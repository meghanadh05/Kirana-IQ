import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import LineChart from '../../components/charts/LineChart.jsx';
import PageHeader from '../../components/layout/PageHeader.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Icon from '../../components/ui/Icon.jsx';
import Table from '../../components/ui/Table.jsx';
import { RiskBadge } from '../../components/ui/Badge.jsx';
import { AsyncSection, EmptyState } from '../../components/ui/States.jsx';
import { useCan } from '../../context/AuthContext.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { currency, date, number, percent, relativeTime } from '../../lib/format.js';

const HORIZONS = [7, 14, 30];

/**
 * Forecasting.
 *
 * The model panel is deliberate: a bare "retrain" button tells a shopkeeper
 * nothing about whether the model is any good. Status, training data size and
 * held-out accuracy are all shown, and the accuracy figure is labelled as
 * coming from a test window the model never saw.
 */
export default function Forecasting() {
  const toast = useToast();
  const canManage = useCan('MANAGER');
  const [searchParams, setSearchParams] = useSearchParams();

  const [productId, setProductId] = useState(searchParams.get('product') || '');
  const [horizon, setHorizon] = useState(7);
  const [training, setTraining] = useState(false);

  const model = useApi(() => api.getModelStatus(), []);
  const products = useApi(() => api.listProducts({ limit: 300, sort: 'name' }), []);
  const recommendations = useApi(() => api.getRecommendations(), []);
  const forecast = useApi(
    () => api.getForecast(productId, horizon, 60),
    [productId, horizon],
    { enabled: Boolean(productId) },
  );

  async function retrain() {
    setTraining(true);
    try {
      const report = await api.trainModel();
      const wape = report.test_scores?.[report.selected_model]?.wape;
      toast.success(
        `Model updated — ${report.selected_model}${wape ? `, test WAPE ${wape.toFixed(2)}%` : ''}`,
      );
      model.reload();
      recommendations.reload();
      if (productId) forecast.reload();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setTraining(false);
    }
  }

  const status = model.data;
  const metrics = status?.metrics?.[status?.model_name];
  const canTrain = (status?.history_days || 0) >= 31;

  const chartSeries = forecast.data
    ? [
        {
          name: 'Sold',
          points: (forecast.data.history || []).map((point) => ({
            label: point.date,
            value: point.quantity,
          })),
        },
        {
          name: 'Forecast',
          dashed: true,
          color: 'var(--warn-500)',
          points: (forecast.data.forecast || []).map((point) => ({
            label: point.date,
            value: point.predicted_demand,
          })),
        },
      ]
    : [];

  return (
    <div className="page">
      <PageHeader
        title="Forecasting"
        subtitle="Predicted demand per product, and what it means for reordering."
      />

      <div className="grid grid--sidebar" style={{ marginBottom: 'var(--s5)' }}>
        <Card
          title="Demand forecast"
          subtitle={
            productId
              ? 'Observed sales, then the model’s prediction'
              : 'Choose a product to see its forecast'
          }
          actions={
            <div className="u-row">
              <select
                className="select"
                style={{ width: 220 }}
                value={productId}
                onChange={(event) => {
                  setProductId(event.target.value);
                  setSearchParams(event.target.value ? { product: event.target.value } : {}, {
                    replace: true,
                  });
                }}
                aria-label="Product"
              >
                <option value="">Choose a product…</option>
                {(products.data?.items || []).map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name}
                  </option>
                ))}
              </select>
              <div className="segment">
                {HORIZONS.map((days) => (
                  <button
                    key={days}
                    type="button"
                    className={`segment__option${horizon === days ? ' segment__option--active' : ''}`}
                    onClick={() => setHorizon(days)}
                  >
                    {days}d
                  </button>
                ))}
              </div>
            </div>
          }
        >
          {!productId ? (
            <EmptyState
              inline
              icon="forecast"
              title="Pick a product"
              message="Its recent sales and predicted demand will be plotted here."
            />
          ) : (
            <AsyncSection
              loading={forecast.loading}
              error={forecast.error}
              onRetry={forecast.reload}
              isEmpty={!forecast.data}
              empty={
                <EmptyState
                  inline
                  icon="forecast"
                  title="Not enough history"
                  message="We need at least 31 days of sales history before forecasting this product."
                />
              }
            >
              <>
                <div className="u-row u-gap4" style={{ marginBottom: 'var(--s4)' }}>
                  <div>
                    <div className="u-xs u-muted">Predicted demand, next {horizon} days</div>
                    <div className="stat__value">
                      {number(forecast.data?.total_predicted_demand)}
                      <span className="u-small u-muted"> units</span>
                    </div>
                  </div>
                </div>
                <LineChart
                  series={chartSeries}
                  height={240}
                  formatLabel={(label) => date(label, { year: undefined })}
                />
              </>
            </AsyncSection>
          )}
        </Card>

        <Card title="Forecast model">
          <AsyncSection loading={model.loading} error={model.error} onRetry={model.reload}>
            {status ? (
              <div className="u-col u-gap4">
                <div className="u-row-between">
                  <span className="u-xs u-muted">Status</span>
                  <span className={`badge badge--${status.trained ? 'success' : 'warn'} badge--dot`}>
                    {status.trained ? 'Ready' : 'Not trained'}
                  </span>
                </div>

                {status.trained ? (
                  <>
                    <Row label="Model" value={status.model_name} />
                    <Row label="Last trained" value={relativeTime(status.trained_at)} />
                    <Row
                      label="Trained on"
                      value={
                        status.store_specific
                          ? 'This store’s sales'
                          : 'The shared starter model'
                      }
                    />
                    {status.training_rows ? (
                      <Row
                        label="Training data"
                        value={`${number(status.training_rows)} rows · ${number(status.training_days)} days`}
                      />
                    ) : null}
                    {metrics ? (
                      <>
                        <Row label="Test WAPE" value={percent(metrics.wape, 2)} />
                        <Row label="Test MAE" value={metrics.mae?.toFixed(2)} />
                      </>
                    ) : null}
                    <p className="u-xs u-subtle">
                      Accuracy is measured on a held-out window of recent sales the model never saw
                      during training.
                    </p>
                  </>
                ) : (
                  <p className="u-small u-muted">
                    No model has been trained for this store yet. Forecasts and reorder advice
                    switch on once one exists.
                  </p>
                )}

                <Row
                  label="Sales history"
                  value={`${number(status.history_days)} days available`}
                />

                {!canTrain ? (
                  <div className="alert alert--info">
                    <Icon name="info" size={15} style={{ flexShrink: 0 }} />
                    <span>
                      Training needs at least 31 days of sales. Keep billing at the counter and this
                      will unlock automatically.
                    </span>
                  </div>
                ) : null}

                {canManage ? (
                  <Button
                    variant="primary"
                    icon="refresh"
                    block
                    loading={training}
                    disabled={!canTrain}
                    onClick={retrain}
                  >
                    {training ? 'Training…' : 'Retrain model'}
                  </Button>
                ) : null}

                {training ? (
                  <p className="u-xs u-muted u-center">
                    Training on your sales history. This takes a few seconds.
                  </p>
                ) : null}
              </div>
            ) : null}
          </AsyncSection>
        </Card>
      </div>

      <Card
        title="Reorder recommendations"
        subtitle="Forecast demand, lead time and demand volatility, turned into a quantity"
        flush
        actions={
          canManage ? (
            <Link to="/app/purchases/new">
              <Button size="sm" icon="purchases">
                Create purchase order
              </Button>
            </Link>
          ) : null
        }
      >
        <AsyncSection
          loading={recommendations.loading}
          error={recommendations.error}
          onRetry={recommendations.reload}
          isEmpty={(recommendations.data || []).length === 0}
          empty={
            <EmptyState
              icon="forecast"
              title="No recommendations yet"
              message="Reorder advice appears once products have enough sales history for the model to forecast them."
            />
          }
        >
          <Table
            columns={[
              {
                key: 'product',
                header: 'Product',
                render: (row) => (
                  <div>
                    <Link to={`/app/products/${row.product_id}`} className="table__primary">
                      {row.name}
                    </Link>
                    <div className="table__secondary u-mono">
                      {row.sku} · {row.category}
                    </div>
                  </div>
                ),
              },
              { key: 'risk', header: 'Risk', render: (row) => <RiskBadge risk={row.risk} /> },
              {
                key: 'stock',
                header: 'Stock',
                align: 'right',
                render: (row) => <span className="u-num">{number(row.current_stock)}</span>,
              },
              {
                key: 'cover',
                header: 'Cover',
                align: 'right',
                render: (row) => (
                  <span className="u-num u-small">
                    {row.stock_cover_days === null ? '—' : `${row.stock_cover_days.toFixed(1)}d`}
                    <span className="u-subtle"> / {row.lead_time_days}d lead</span>
                  </span>
                ),
              },
              {
                key: 'demand',
                header: 'Demand (7d)',
                align: 'right',
                render: (row) => (
                  <span className="u-num">{number(Math.round(row.expected_7_day_demand))}</span>
                ),
              },
              {
                key: 'order',
                header: 'Suggested order',
                align: 'right',
                render: (row) => (
                  <div>
                    <div className="u-num u-strong">
                      {number(row.recommended_reorder_quantity)}
                    </div>
                    {row.estimated_cost > 0 ? (
                      <div className="table__secondary u-num">{currency(row.estimated_cost)}</div>
                    ) : null}
                  </div>
                ),
              },
              {
                key: 'why',
                header: 'Why',
                render: (row) => (
                  <span className="u-xs u-muted" style={{ display: 'block', maxWidth: 340 }}>
                    {row.reason}
                  </span>
                ),
              },
            ]}
            rows={recommendations.data || []}
            rowKey={(row) => row.product_id}
          />
        </AsyncSection>
      </Card>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="u-row-between">
      <span className="u-xs u-muted">{label}</span>
      <span className="u-small u-strong" style={{ textAlign: 'right' }}>
        {value}
      </span>
    </div>
  );
}
