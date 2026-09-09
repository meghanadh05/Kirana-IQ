import { useState } from 'react';

import DataTable from '../components/DataTable.jsx';
import RiskBadge from '../components/RiskBadge.jsx';
import StatCard from '../components/StatCard.jsx';
import { ErrorState, Loading } from '../components/States.jsx';
import { useApi } from '../hooks/useApi.js';
import { getInventorySummary, getRecommendations } from '../services/api.js';

const RISKS = ['', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

export default function Inventory() {
  const [risk, setRisk] = useState('');
  const [expanded, setExpanded] = useState(null);

  const summary = useApi(getInventorySummary);
  const rows = useApi(() => getRecommendations({ risk }), [risk]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Inventory</h1>
          <p className="muted">Stockout risk and reorder quantities, most urgent first</p>
        </div>
        <div className="segmented">
          {RISKS.map((level) => (
            <button
              key={level || 'ALL'}
              type="button"
              className={level === risk ? 'segmented__btn segmented__btn--active' : 'segmented__btn'}
              onClick={() => setRisk(level)}
            >
              {level || 'All'}
            </button>
          ))}
        </div>
      </div>

      {summary.data && (
        <section className="stats">
          <StatCard label="Critical" value={summary.data.critical_products} tone="critical" />
          <StatCard label="High" value={summary.data.high_risk_products} tone="high" />
          <StatCard label="Medium" value={summary.data.medium_risk_products} tone="medium" />
          <StatCard label="Low" value={summary.data.low_risk_products} tone="low" />
          <StatCard label="Units to reorder" value={summary.data.total_reorder_units.toLocaleString()} />
        </section>
      )}

      {rows.loading && <Loading />}
      {rows.error && <ErrorState error={rows.error} onRetry={rows.reload} />}

      {rows.data && (
        <section className="panel">
          <div className="panel__head">
            <h2>Recommendations</h2>
            <span className="muted">Select a row for the reasoning</span>
          </div>
          <DataTable
            rowKey={(row) => row.product_id}
            rows={rows.data}
            empty="No products at this risk level."
            columns={[
              { key: 'sku', label: 'SKU' },
              {
                key: 'name',
                label: 'Product',
                render: (row) => (
                  <button
                    type="button"
                    className="linklike"
                    onClick={() => setExpanded(expanded === row.product_id ? null : row.product_id)}
                  >
                    {row.name}
                  </button>
                ),
              },
              { key: 'current_stock', label: 'Stock', align: 'right' },
              { key: 'expected_7_day_demand', label: '7d demand', align: 'right' },
              {
                key: 'stock_cover_days',
                label: 'Cover',
                align: 'right',
                render: (row) => (row.stock_cover_days === null ? '—' : `${row.stock_cover_days}d`),
              },
              { key: 'lead_time_days', label: 'Lead', align: 'right', render: (row) => `${row.lead_time_days}d` },
              { key: 'risk', label: 'Risk', render: (row) => <RiskBadge level={row.risk} /> },
              {
                key: 'recommended_reorder_quantity',
                label: 'Reorder',
                align: 'right',
                render: (row) => <strong>{row.recommended_reorder_quantity}</strong>,
              },
            ]}
          />

          {expanded && (
            <ReasonPanel row={rows.data.find((row) => row.product_id === expanded)} />
          )}
        </section>
      )}
    </>
  );
}

function ReasonPanel({ row }) {
  if (!row) return null;
  return (
    <div className="reason">
      <h3>{row.name}</h3>
      <p>{row.reason}</p>
      <dl className="reason__facts">
        <div>
          <dt>Average daily demand</dt>
          <dd>{row.average_daily_demand}</dd>
        </div>
        <div>
          <dt>Demand variability (σ)</dt>
          <dd>{row.demand_std_dev}</dd>
        </div>
        <div>
          <dt>Safety stock</dt>
          <dd>{row.safety_stock}</dd>
        </div>
        <div>
          <dt>Target stock</dt>
          <dd>{row.target_stock}</dd>
        </div>
        <div>
          <dt>Overstocked</dt>
          <dd>{row.overstock ? 'Yes' : 'No'}</dd>
        </div>
      </dl>
    </div>
  );
}
