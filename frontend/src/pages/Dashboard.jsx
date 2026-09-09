import { useState } from 'react';
import { Link } from 'react-router-dom';

import DataTable from '../components/DataTable.jsx';
import LineChart from '../components/LineChart.jsx';
import RiskBadge from '../components/RiskBadge.jsx';
import StatCard from '../components/StatCard.jsx';
import { ErrorState, Loading } from '../components/States.jsx';
import { useApi } from '../hooks/useApi.js';
import { getDemandTrend, getModel, getOverview, trainModel } from '../services/api.js';

export default function Dashboard() {
  const overview = useApi(() => getOverview(5));
  const model = useApi(getModel);
  const trend = useApi(() => getDemandTrend(30, 7));
  const [training, setTraining] = useState(false);
  const [trainError, setTrainError] = useState(null);

  const onTrain = async () => {
    setTraining(true);
    setTrainError(null);
    try {
      await trainModel();
      overview.reload();
      model.reload();
      trend.reload();
    } catch (error) {
      setTrainError(error);
    } finally {
      setTraining(false);
    }
  };

  const info = model.data;
  const wape = info?.metrics?.[info?.model_name]?.wape;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <p className="muted">
            {info?.trained
              ? `Forecasts from ${info.model_name}${wape ? ` · ${(wape * 100).toFixed(1)}% WAPE on held-out data` : ''}`
              : 'No model trained yet.'}
          </p>
        </div>
        <button type="button" className="btn btn--primary" onClick={onTrain} disabled={training}>
          {training ? 'Training…' : 'Retrain model'}
        </button>
      </div>

      {trainError && <ErrorState error={trainError} />}

      {overview.loading && <Loading />}
      {overview.error && <ErrorState error={overview.error} onRetry={overview.reload} />}

      {overview.data && (
        <>
          <section className="stats">
            <StatCard label="Total products" value={overview.data.total_products} />
            <StatCard
              label="Critical"
              value={overview.data.critical_products}
              tone={overview.data.critical_products > 0 ? 'critical' : 'neutral'}
              hint="Under 2 days of cover"
            />
            <StatCard
              label="High risk"
              value={overview.data.high_risk_products}
              tone={overview.data.high_risk_products > 0 ? 'high' : 'neutral'}
              hint="Runs out before delivery"
            />
            <StatCard label="Overstocked" value={overview.data.overstocked_products} hint="Over 30 days of cover" />
            <StatCard
              label="Predicted 7-day demand"
              value={Math.round(overview.data.expected_7_day_units).toLocaleString()}
              hint="units across all SKUs"
            />
          </section>

          <section className="panel">
            <div className="panel__head">
              <h2>Total demand: last 30 days and next 7</h2>
              <span className="muted">all SKUs combined</span>
            </div>
            {trend.loading && <Loading />}
            {trend.data && <LineChart series={trendSeries(trend.data)} />}
          </section>

          <section className="panel">
            <div className="panel__head">
              <h2>Reorder recommendations</h2>
              <Link to="/inventory" className="link">
                View all
              </Link>
            </div>
            <DataTable
              rowKey={(row) => row.product_id}
              rows={overview.data.top_reorders}
              empty="Nothing needs reordering."
              columns={[
                { key: 'name', label: 'Product' },
                { key: 'risk', label: 'Risk', render: (row) => <RiskBadge level={row.risk} /> },
                { key: 'current_stock', label: 'Stock', align: 'right' },
                {
                  key: 'stock_cover_days',
                  label: 'Cover',
                  align: 'right',
                  render: (row) => (row.stock_cover_days === null ? '—' : `${row.stock_cover_days}d`),
                },
                {
                  key: 'recommended_reorder_quantity',
                  label: 'Reorder',
                  align: 'right',
                  render: (row) => <strong>{row.recommended_reorder_quantity}</strong>,
                },
              ]}
            />
          </section>

          <section className="panel">
            <div className="panel__head">
              <h2>Recent demand anomalies</h2>
              <span className="muted">{overview.data.anomaly_count} detected</span>
            </div>
            {overview.data.anomalies.length === 0 ? (
              <p className="muted">No unusual demand changes.</p>
            ) : (
              <ul className="anomalies">
                {overview.data.anomalies.map((anomaly) => (
                  <li key={anomaly.product_id} className={`anomaly anomaly--${anomaly.direction.toLowerCase()}`}>
                    <span className="anomaly__arrow">{anomaly.direction === 'SPIKE' ? '▲' : '▼'}</span>
                    <span>{anomaly.message}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </>
  );
}

/** Observed then predicted catalogue demand, joined at the handover point. */
function trendSeries(trend) {
  const shortDate = (iso) => iso.slice(5);
  const lastActual = trend.history[trend.history.length - 1];

  return [
    {
      name: 'Actual demand',
      colour: '#1f6feb',
      points: trend.history.map((point) => ({ label: shortDate(point.date), value: point.quantity })),
    },
    {
      name: 'Predicted demand',
      colour: '#b45309',
      dashed: true,
      offset: Math.max(0, trend.history.length - 1),
      points: [
        ...(lastActual ? [{ label: shortDate(lastActual.date), value: lastActual.quantity }] : []),
        ...trend.forecast.map((point) => ({ label: shortDate(point.date), value: point.predicted_demand })),
      ],
    },
  ];
}
