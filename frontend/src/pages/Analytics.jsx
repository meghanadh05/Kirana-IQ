import BarChart from '../components/BarChart.jsx';
import DataTable from '../components/DataTable.jsx';
import { ErrorState, Loading } from '../components/States.jsx';
import { useApi } from '../hooks/useApi.js';
import { getAnomalies, getCategoryTrends, getSlowMoving, getTopProducts } from '../services/api.js';

const WINDOW_DAYS = 30;

export default function Analytics() {
  const top = useApi(() => getTopProducts(WINDOW_DAYS, 8));
  const slow = useApi(() => getSlowMoving(WINDOW_DAYS, 8));
  const trends = useApi(() => getCategoryTrends(WINDOW_DAYS));
  const anomalies = useApi(() => getAnomalies());

  const moverColumns = [
    { key: 'sku', label: 'SKU' },
    { key: 'name', label: 'Product' },
    { key: 'total_units', label: 'Units', align: 'right' },
    { key: 'daily_average', label: 'Per day', align: 'right' },
    { key: 'current_stock', label: 'Stock', align: 'right' },
  ];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Analytics</h1>
          <p className="muted">Trailing {WINDOW_DAYS} days</p>
        </div>
      </div>

      <section className="panel">
        <div className="panel__head">
          <h2>Category demand</h2>
          <span className="muted">vs the previous {WINDOW_DAYS} days</span>
        </div>
        {trends.loading && <Loading />}
        {trends.error && <ErrorState error={trends.error} onRetry={trends.reload} />}
        {trends.data && (
          <>
            <BarChart
              rows={trends.data.map((row) => ({ label: row.category, value: row.current_units }))}
              format={(value) => value.toLocaleString()}
            />
            <DataTable
              rowKey={(row) => row.category}
              rows={trends.data}
              columns={[
                { key: 'category', label: 'Category' },
                { key: 'current_units', label: 'Units', align: 'right' },
                { key: 'previous_units', label: 'Previous', align: 'right' },
                {
                  key: 'change_pct',
                  label: 'Change',
                  align: 'right',
                  render: (row) => (
                    <span className={`delta delta--${row.direction.toLowerCase()}`}>
                      {row.change_pct === null ? '—' : `${row.change_pct > 0 ? '+' : ''}${row.change_pct}%`}
                    </span>
                  ),
                },
              ]}
            />
          </>
        )}
      </section>

      <div className="grid-2">
        <section className="panel">
          <div className="panel__head">
            <h2>Top selling</h2>
          </div>
          {top.loading && <Loading />}
          {top.data && <DataTable rowKey={(row) => row.product_id} rows={top.data} columns={moverColumns} />}
        </section>

        <section className="panel">
          <div className="panel__head">
            <h2>Slow moving</h2>
          </div>
          {slow.loading && <Loading />}
          {slow.data && (
            <DataTable
              rowKey={(row) => row.product_id}
              rows={slow.data}
              columns={moverColumns}
              empty="No slow-moving products."
            />
          )}
        </section>
      </div>

      <section className="panel">
        <div className="panel__head">
          <h2>Demand anomalies</h2>
          <span className="muted">Recent 7 days vs the 28 before</span>
        </div>
        {anomalies.loading && <Loading />}
        {anomalies.error && <ErrorState error={anomalies.error} onRetry={anomalies.reload} />}
        {anomalies.data && (
          <DataTable
            rowKey={(row) => row.product_id}
            rows={anomalies.data}
            empty="No unusual demand changes."
            columns={[
              { key: 'name', label: 'Product' },
              { key: 'category', label: 'Category' },
              {
                key: 'direction',
                label: 'Change',
                render: (row) => (
                  <span className={`delta delta--${row.direction === 'SPIKE' ? 'up' : 'down'}`}>
                    {row.direction === 'SPIKE' ? '▲' : '▼'}{' '}
                    {row.change_pct === null ? 'from zero' : `${Math.abs(row.change_pct)}%`}
                  </span>
                ),
              },
              { key: 'baseline_daily_average', label: 'Was', align: 'right' },
              { key: 'recent_daily_average', label: 'Now', align: 'right' },
              { key: 'z_score', label: 'z', align: 'right', render: (row) => row.z_score ?? '—' },
            ]}
          />
        )}
      </section>
    </>
  );
}
