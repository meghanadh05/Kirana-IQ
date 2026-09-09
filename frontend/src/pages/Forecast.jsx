import { useState } from 'react';

import LineChart from '../components/LineChart.jsx';
import StatCard from '../components/StatCard.jsx';
import { ErrorState, Loading } from '../components/States.jsx';
import { useApi } from '../hooks/useApi.js';
import { getForecast, getProducts } from '../services/api.js';

const HORIZONS = [7, 14, 30];
const HISTORY_DAYS = 30;

export default function Forecast() {
  const products = useApi(() => getProducts({ limit: 1000 }));
  const [productId, setProductId] = useState(null);
  const [days, setDays] = useState(7);

  // Default to the first product once the catalogue arrives.
  const selectedId = productId ?? products.data?.[0]?.id ?? null;

  const forecast = useApi(
    () => (selectedId ? getForecast(selectedId, days, HISTORY_DAYS) : Promise.resolve(null)),
    [selectedId, days]
  );

  const data = forecast.data;
  const shortDate = (iso) => iso.slice(5);

  // History and forecast share one x axis. The predicted line starts on the
  // final observed point rather than after it, so the two join up instead of
  // leaving a visual gap at the handover.
  const lastActual = data?.history?.[data.history.length - 1];
  const series = data
    ? [
        {
          name: 'Actual demand',
          colour: '#1f6feb',
          points: data.history.map((point) => ({ label: shortDate(point.date), value: point.quantity })),
        },
        {
          name: 'Predicted demand',
          colour: '#b45309',
          dashed: true,
          offset: Math.max(0, data.history.length - 1),
          points: [
            ...(lastActual ? [{ label: shortDate(lastActual.date), value: lastActual.quantity }] : []),
            ...data.forecast.map((point) => ({ label: shortDate(point.date), value: point.predicted_demand })),
          ],
        },
      ]
    : [];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Forecast</h1>
          <p className="muted">Predicted daily demand for a single SKU</p>
        </div>
        <div className="filters">
          <select
            className="input"
            value={selectedId ?? ''}
            onChange={(event) => setProductId(Number(event.target.value))}
          >
            {(products.data ?? []).map((product) => (
              <option key={product.id} value={product.id}>
                {product.sku} — {product.name}
              </option>
            ))}
          </select>
          <div className="segmented">
            {HORIZONS.map((option) => (
              <button
                key={option}
                type="button"
                className={option === days ? 'segmented__btn segmented__btn--active' : 'segmented__btn'}
                onClick={() => setDays(option)}
              >
                {option}d
              </button>
            ))}
          </div>
        </div>
      </div>

      {(products.loading || forecast.loading) && <Loading />}
      {forecast.error && <ErrorState error={forecast.error} onRetry={forecast.reload} />}

      {data && (
        <>
          <section className="stats">
            <StatCard label="Product" value={data.sku} hint={data.name} />
            <StatCard label={`Next ${days} days`} value={data.total_predicted_demand.toLocaleString()} hint="predicted units" />
            <StatCard
              label="Daily average"
              value={(data.total_predicted_demand / days).toFixed(1)}
              hint="predicted units/day"
            />
          </section>

          <section className="panel">
            <div className="panel__head">
              <h2>Demand: last {HISTORY_DAYS} days and next {days}</h2>
            </div>
            <LineChart series={series} />
          </section>

          <section className="panel">
            <div className="panel__head">
              <h2>Daily forecast</h2>
            </div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th className="right">Predicted units</th>
                  </tr>
                </thead>
                <tbody>
                  {data.forecast.map((point) => (
                    <tr key={point.date}>
                      <td>{point.date}</td>
                      <td className="right">{point.predicted_demand}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </>
  );
}
