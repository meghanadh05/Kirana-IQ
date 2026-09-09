import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import ProductForm from './ProductForm.jsx';
import PageHeader from '../../components/layout/PageHeader.jsx';
import LineChart from '../../components/charts/LineChart.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Table from '../../components/ui/Table.jsx';
import { ConfirmDialog } from '../../components/ui/Modal.jsx';
import { RiskBadge, StockBadge } from '../../components/ui/Badge.jsx';
import { AsyncSection, EmptyState, ErrorState, Loading } from '../../components/ui/States.jsx';
import { useCan } from '../../context/AuthContext.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { currency, date, dateTime, number, titleCase } from '../../lib/format.js';

export default function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const canManage = useCan('MANAGER');

  const product = useApi(() => api.getProduct(id), [id]);
  const movements = useApi(() => api.listMovements({ product_id: id, limit: 15 }), [id]);
  const forecast = useApi(() => api.getForecast(id, 14, 45), [id]);
  const advice = useApi(() => api.getProductRecommendation(id), [id]);

  const [editing, setEditing] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);

  if (product.loading) return <div className="page"><Loading /></div>;
  if (product.error) {
    return (
      <div className="page">
        <ErrorState error={product.error} onRetry={product.reload} />
      </div>
    );
  }

  const data = product.data;
  const stockStatus =
    data.current_stock <= 0 ? 'OUT_OF_STOCK' : data.current_stock <= data.reorder_level ? 'LOW' : 'OK';

  async function archive() {
    setArchiving(true);
    try {
      await api.archiveProduct(data.id);
      toast.success(`${data.name} archived`);
      setConfirmArchive(false);
      product.reload();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setArchiving(false);
    }
  }

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
        breadcrumb={[{ label: 'Products', to: '/app/products' }, { label: data.name }]}
        title={data.name}
        subtitle={`${data.sku}${data.barcode ? ` · ${data.barcode}` : ''} · ${data.category}${data.brand ? ` · ${data.brand}` : ''}`}
        actions={
          canManage ? (
            <>
              {data.is_active ? (
                <Button variant="dangerGhost" onClick={() => setConfirmArchive(true)}>
                  Archive
                </Button>
              ) : null}
              <Button variant="primary" icon="edit" onClick={() => setEditing(true)}>
                Edit
              </Button>
            </>
          ) : null
        }
      />

      {!data.is_active ? (
        <div className="alert alert--warn" style={{ marginBottom: 'var(--s4)' }}>
          This product is archived. It cannot be sold, and it is hidden from the catalogue by
          default. Its sales history is kept.
        </div>
      ) : null}

      <div className="grid grid--kpi" style={{ marginBottom: 'var(--s5)' }}>
        <div className="stat">
          <span className="stat__label">In stock</span>
          <span className="stat__value stat__value--sm">
            {number(data.current_stock)} <span className="u-xs u-subtle">{data.unit}</span>
          </span>
          <span className="stat__meta">
            <StockBadge status={stockStatus} />
          </span>
        </div>
        <div className="stat">
          <span className="stat__label">Selling price</span>
          <span className="stat__value stat__value--sm">{currency(data.selling_price)}</span>
          <span className="stat__meta">cost {currency(data.cost_price)}</span>
        </div>
        <div className="stat">
          <span className="stat__label">Stock value</span>
          <span className="stat__value stat__value--sm">
            {currency(data.current_stock * Number(data.cost_price), { compact: true })}
          </span>
          <span className="stat__meta">at cost</span>
        </div>
        <div className="stat">
          <span className="stat__label">Lead time</span>
          <span className="stat__value stat__value--sm">{data.lead_time_days}d</span>
          <span className="stat__meta">reorder at {number(data.reorder_level)}</span>
        </div>
      </div>

      <div className="grid grid--sidebar">
        <div className="u-col u-gap4">
          <Card
            title="Demand and forecast"
            subtitle="Units sold per day, then the model's prediction."
          >
            <AsyncSection
              loading={forecast.loading}
              error={forecast.error}
              onRetry={forecast.reload}
              isEmpty={!forecast.data}
              empty={
                <EmptyState
                  inline
                  icon="forecast"
                  title="Not enough history yet"
                  message="Forecasting needs at least 31 days of sales for this product. Keep selling and it will appear here."
                />
              }
            >
              <>
                <LineChart
                  series={chartSeries}
                  height={220}
                  formatLabel={(label) => date(label, { year: undefined })}
                />
                <div className="u-row u-gap4 u-mt4 u-xs u-muted">
                  <span className="u-row">
                    <span style={{ width: 14, height: 2, background: 'var(--accent-500)' }} /> Sold
                  </span>
                  <span className="u-row">
                    <span
                      style={{
                        width: 14, height: 2,
                        background: 'repeating-linear-gradient(90deg, var(--warn-500) 0 4px, transparent 4px 7px)',
                      }}
                    />
                    Forecast · {forecast.data?.total_predicted_demand} units over{' '}
                    {forecast.data?.forecast_days} days
                  </span>
                </div>
              </>
            </AsyncSection>
          </Card>

          <Card
            title="Stock movements"
            subtitle="Every change to this product's stock, newest first."
            flush
            actions={
              <Link to={`/app/inventory/movements?product=${data.id}`} className="u-small">
                View all
              </Link>
            }
          >
            <AsyncSection
              loading={movements.loading}
              error={movements.error}
              onRetry={movements.reload}
              isEmpty={(movements.data?.items || []).length === 0}
              empty={
                <EmptyState
                  inline
                  icon="inventory"
                  title="No movements recorded"
                  message="Sales, deliveries and adjustments will appear here."
                />
              }
            >
              <Table
                columns={[
                  {
                    key: 'type',
                    header: 'Type',
                    render: (row) => (
                      <div>
                        <div className="u-small u-strong">{titleCase(row.type)}</div>
                        {row.notes ? <div className="table__secondary">{row.notes}</div> : null}
                      </div>
                    ),
                  },
                  {
                    key: 'change',
                    header: 'Change',
                    align: 'right',
                    render: (row) => (
                      <span
                        className="u-num u-strong"
                        style={{
                          color: row.quantity_change > 0 ? 'var(--success-600)' : 'var(--danger-600)',
                        }}
                      >
                        {row.quantity_change > 0 ? '+' : ''}
                        {number(row.quantity_change)}
                      </span>
                    ),
                  },
                  {
                    key: 'after',
                    header: 'Balance',
                    align: 'right',
                    render: (row) => <span className="u-num">{number(row.quantity_after)}</span>,
                  },
                  {
                    key: 'when',
                    header: 'When',
                    align: 'right',
                    render: (row) => <span className="u-xs u-muted">{dateTime(row.created_at)}</span>,
                  },
                ]}
                rows={movements.data?.items || []}
              />
            </AsyncSection>
          </Card>
        </div>

        <div className="u-col u-gap4">
          <Card title="Reorder advice">
            <AsyncSection
              loading={advice.loading}
              error={advice.error}
              onRetry={advice.reload}
              isEmpty={!advice.data}
              empty={
                <p className="u-small u-muted">
                  Reorder advice appears once this product has enough sales history to forecast.
                </p>
              }
            >
              {advice.data ? (
                <div className="u-col u-gap4">
                  <div className="u-row-between">
                    <RiskBadge risk={advice.data.risk} />
                    {advice.data.stock_cover_days !== null ? (
                      <span className="u-xs u-muted">
                        {advice.data.stock_cover_days.toFixed(1)} days of cover
                      </span>
                    ) : null}
                  </div>

                  <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
                    <Metric
                      label="Expected demand"
                      value={`${number(Math.round(advice.data.expected_7_day_demand))} / 7d`}
                    />
                    <Metric
                      label="Suggested order"
                      value={number(advice.data.recommended_reorder_quantity)}
                    />
                  </div>

                  <p className="u-small u-muted">{advice.data.reason}</p>

                  {advice.data.recommended_reorder_quantity > 0 && canManage ? (
                    <Button
                      variant="primary"
                      icon="purchases"
                      block
                      onClick={() =>
                        navigate(`/app/purchases/new?product=${data.id}&quantity=${advice.data.recommended_reorder_quantity}`)
                      }
                    >
                      Create purchase order
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </AsyncSection>
          </Card>

          <Card title="Details">
            <dl className="u-col" style={{ gap: 'var(--s3)' }}>
              <Detail label="Unit" value={data.unit} />
              <Detail label="Tax rate" value={`${data.tax_rate}%`} />
              <Detail
                label="Margin"
                value={
                  Number(data.selling_price) && Number(data.cost_price)
                    ? `${(((data.selling_price - data.cost_price) / data.selling_price) * 100).toFixed(0)}%`
                    : '—'
                }
              />
              <Detail label="Added" value={date(data.created_at)} />
              {data.description ? <Detail label="Notes" value={data.description} /> : null}
            </dl>
          </Card>
        </div>
      </div>

      <ProductForm
        open={editing}
        product={data}
        onClose={() => setEditing(false)}
        onSaved={() => {
          setEditing(false);
          product.reload();
        }}
      />

      <ConfirmDialog
        open={confirmArchive}
        onClose={() => setConfirmArchive(false)}
        onConfirm={archive}
        loading={archiving}
        destructive
        title={`Archive ${data.name}?`}
        confirmLabel="Archive"
        message="It will no longer appear in the catalogue or be sellable at the till. Its sales history is kept, and you can restore it by editing the product."
      />
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div>
      <div className="u-xs u-muted">{label}</div>
      <div className="u-strong" style={{ fontSize: 'var(--text-lg)' }}>
        {value}
      </div>
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div className="u-row-between">
      <dt className="u-xs u-muted">{label}</dt>
      <dd className="u-small" style={{ margin: 0, textAlign: 'right' }}>
        {value}
      </dd>
    </div>
  );
}
