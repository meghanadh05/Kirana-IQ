import { Link, useNavigate } from 'react-router-dom';

import LineChart from '../components/charts/LineChart.jsx';
import PageHeader from '../components/layout/PageHeader.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Icon from '../components/ui/Icon.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import Table from '../components/ui/Table.jsx';
import { RiskBadge } from '../components/ui/Badge.jsx';
import { AsyncSection, CardSkeleton, EmptyState, ErrorState } from '../components/ui/States.jsx';
import { useAuth, useCan } from '../context/AuthContext.jsx';
import { useApi } from '../hooks/useApi.js';
import * as api from '../services/api.js';
import { currency, date, number, percent, time } from '../lib/format.js';

/**
 * The command centre.
 *
 * Answers one question first — what needs my attention today — and only then
 * shows the numbers. Every line is traceable to a real figure: a stock level, a
 * forecast, an open order. Nothing here is labelled "AI"; it is labelled with
 * what it actually is.
 */
export default function Overview() {
  const { user, store } = useAuth();
  const canManage = useCan('MANAGER');
  const navigate = useNavigate();

  const dashboard = useApi(() => api.getDashboard(), []);
  const briefing = useApi(() => api.getBriefing(), []);

  if (dashboard.error) {
    return (
      <div className="page">
        <ErrorState error={dashboard.error} onRetry={dashboard.reload} />
      </div>
    );
  }

  const data = dashboard.data;
  const brief = briefing.data;

  const revenueDelta =
    data && data.yesterday_revenue > 0
      ? ((data.today.revenue - data.yesterday_revenue) / data.yesterday_revenue) * 100
      : null;

  return (
    <div className="page">
      <PageHeader
        title={
          brief
            ? `${brief.greeting}, ${(user?.full_name || '').split(' ')[0]}`
            : `Welcome back`
        }
        subtitle={
          brief
            ? brief.attention_count > 0
              ? `${store?.name} needs your attention in ${brief.attention_count} area${brief.attention_count === 1 ? '' : 's'} today.`
              : `${store?.name} is running smoothly today.`
            : store?.name
        }
        actions={
          <>
            <Link to="/app/pos">
              <Button variant="primary" icon="pos">
                Open POS
              </Button>
            </Link>
          </>
        }
      />

      {/* --- What needs attention ------------------------------------- */}
      <AsyncSection
        loading={briefing.loading}
        error={briefing.error}
        onRetry={briefing.reload}
        skeleton={<CardSkeleton height={130} />}
      >
        {brief ? (
          <div className="grid grid--sidebar" style={{ marginBottom: 'var(--s5)' }}>
            <Card title="Today at a glance">
              <ul className="u-col" style={{ gap: 'var(--s3)' }}>
                {brief.headlines.map((headline, index) => (
                  <li key={index} className="u-row">
                    <HeadlineIcon kind={headline.icon} />
                    <span className="u-small u-grow">{headline.text}</span>
                    {headline.link ? (
                      <Link
                        to={headline.link.replace(/^\//, '/app/')}
                        className="u-xs u-nowrap"
                      >
                        View
                      </Link>
                    ) : null}
                  </li>
                ))}
              </ul>
            </Card>

            <Card
              title="Recommended actions"
              subtitle={brief.actions.length ? 'Ordered by urgency' : undefined}
            >
              {brief.actions.length === 0 ? (
                <p className="u-small u-muted">
                  Nothing needs doing right now. Stock levels and demand are both within range.
                </p>
              ) : (
                <ol className="u-col" style={{ gap: 'var(--s4)' }}>
                  {brief.actions.map((action, index) => (
                    <li key={index}>
                      <div className="u-row-between">
                        <span className="u-small u-strong">
                          {index + 1}. {action.title}
                        </span>
                      </div>
                      <p className="u-xs u-muted" style={{ marginTop: 2 }}>
                        {action.detail}
                      </p>
                      {canManage ? (
                        <Button
                          size="sm"
                          className="u-mt4"
                          onClick={() => navigate(action.link.replace(/^\//, '/app/'))}
                        >
                          {action.kind === 'REORDER'
                            ? 'Create purchase order'
                            : action.kind === 'TRAIN'
                              ? 'Train the model'
                              : 'Investigate'}
                        </Button>
                      ) : null}
                    </li>
                  ))}
                </ol>
              )}
            </Card>
          </div>
        ) : null}
      </AsyncSection>

      {/* --- KPIs ------------------------------------------------------ */}
      <AsyncSection
        loading={dashboard.loading}
        error={dashboard.error}
        onRetry={dashboard.reload}
        skeleton={
          <div className="grid grid--kpi">
            {Array.from({ length: 6 }).map((_, index) => (
              <CardSkeleton key={index} height={92} />
            ))}
          </div>
        }
      >
        {data ? (
          <>
            <div className="grid grid--kpi">
              <StatCard
                label="Today's revenue"
                value={currency(data.today.revenue, { compact: true })}
                delta={revenueDelta}
                deltaLabel="vs yesterday"
                meta={revenueDelta === null ? 'No sales yesterday to compare' : undefined}
                icon="money"
              />
              <StatCard
                label="Today's orders"
                value={number(data.today.orders)}
                meta={
                  data.today.orders
                    ? `${number(data.today.units)} units · avg ${currency(data.today.average_order_value)}`
                    : 'No sales yet today'
                }
                icon="sales"
              />
              <StatCard
                label="Gross profit (7d)"
                value={currency(data.week.gross_profit, { compact: true })}
                meta={
                  data.week.gross_margin_pct !== null
                    ? `${percent(data.week.gross_margin_pct)} margin`
                    : 'No sales this week'
                }
                icon="trending"
              />
              <StatCard
                label="Low stock"
                value={number(data.inventory.low_stock)}
                tone={data.inventory.low_stock > 0 ? 'warn' : undefined}
                meta="at or below reorder level"
                icon="package"
              />
              <StatCard
                label="Critical risk"
                value={data.risk ? number(data.risk.critical_products) : '—'}
                tone={data.risk?.critical_products > 0 ? 'alert' : undefined}
                meta={data.forecast_available ? 'may run out before delivery' : 'needs a trained model'}
                icon="warning"
              />
              <StatCard
                label="Inventory value"
                value={currency(data.inventory.inventory_cost_value, { compact: true })}
                meta={`${number(data.inventory.total_products)} products, at cost`}
                icon="inventory"
              />
            </div>

            {/* --- Revenue and alerts ---------------------------------- */}
            <div className="grid grid--sidebar u-mt4">
              <Card
                title="Revenue, last 7 days"
                subtitle="Completed sales per day"
                actions={
                  <Link to="/app/analytics" className="u-small">
                    Full analytics
                  </Link>
                }
              >
                <LineChart
                  height={220}
                  series={[
                    {
                      name: 'Revenue',
                      points: (data.revenue_series || []).map((point) => ({
                        label: point.date,
                        value: Number(point.revenue),
                      })),
                    },
                  ]}
                  formatValue={(value) => currency(value, { compact: true })}
                  formatLabel={(label) => date(label, { year: undefined })}
                />
              </Card>

              <Card
                title="Reorder recommendations"
                subtitle={data.forecast_available ? 'Most urgent first' : undefined}
                actions={
                  canManage && data.reorders?.length ? (
                    <Link to="/app/purchases/new" className="u-small">
                      Order all
                    </Link>
                  ) : null
                }
              >
                {!data.forecast_available ? (
                  <EmptyState
                    inline
                    icon="forecast"
                    title="Forecasting not ready"
                    message="Train the demand model on your sales history to get reorder recommendations."
                    actions={
                      canManage ? (
                        <Link to="/app/forecasting">
                          <Button size="sm" variant="primary">
                            Go to Forecasting
                          </Button>
                        </Link>
                      ) : null
                    }
                  />
                ) : data.reorders?.length === 0 ? (
                  <EmptyState
                    inline
                    icon="check"
                    title="Nothing to reorder"
                    message="Every product has enough stock to cover expected demand through its supplier lead time."
                  />
                ) : (
                  <ul className="u-col" style={{ gap: 'var(--s4)' }}>
                    {data.reorders.map((row) => (
                      <li key={row.product_id}>
                        <div className="u-row-between">
                          <Link to={`/app/products/${row.product_id}`} className="u-small u-strong">
                            {row.name}
                          </Link>
                          <RiskBadge risk={row.risk} />
                        </div>
                        <div className="u-xs u-muted" style={{ marginTop: 2 }}>
                          {number(row.current_stock)} left · expect{' '}
                          {number(Math.round(row.expected_7_day_demand))} in 7 days ·{' '}
                          <strong>order {number(row.recommended_reorder_quantity)}</strong>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>

            {/* --- Movers, anomalies, recent --------------------------- */}
            <div className="grid grid--3 u-mt4">
              <Card title="Top sellers" subtitle="Last 30 days by units">
                <MoverList rows={data.top_products} emptyLabel="No sales in the last 30 days." />
              </Card>

              <Card title="Slow movers" subtitle="Candidates for dead stock">
                <MoverList
                  rows={data.slow_movers}
                  emptyLabel="Nothing is moving unusually slowly."
                  muted
                />
              </Card>

              <Card title="Demand anomalies" subtitle="Unusual against each product's own baseline">
                {data.anomalies?.length === 0 ? (
                  <p className="u-small u-muted">
                    {data.forecast_available
                      ? 'No unusual demand detected this week.'
                      : 'Anomaly detection needs more sales history.'}
                  </p>
                ) : (
                  <ul className="u-col" style={{ gap: 'var(--s3)' }}>
                    {data.anomalies.map((anomaly) => (
                      <li key={anomaly.product_id}>
                        <div className="u-row">
                          <Icon
                            name={anomaly.direction === 'SPIKE' ? 'arrowUp' : 'arrowDown'}
                            size={13}
                            style={{
                              color:
                                anomaly.direction === 'SPIKE'
                                  ? 'var(--success-600)'
                                  : 'var(--danger-600)',
                            }}
                          />
                          <span className="u-small u-strong">{anomaly.name}</span>
                        </div>
                        <p className="u-xs u-muted" style={{ marginTop: 2 }}>
                          {anomaly.message}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>

            <Card
              title="Recent transactions"
              className="u-mt4"
              flush
              actions={
                <Link to="/app/sales" className="u-small">
                  All sales
                </Link>
              }
            >
              {data.recent_sales?.length === 0 ? (
                <EmptyState
                  inline
                  icon="sales"
                  title="No sales yet"
                  message="Ring up your first sale and it will appear here."
                  actions={
                    <Link to="/app/pos">
                      <Button size="sm" variant="primary" icon="pos">
                        Open POS
                      </Button>
                    </Link>
                  }
                />
              ) : (
                <Table
                  columns={[
                    {
                      key: 'invoice',
                      header: 'Invoice',
                      render: (row) => <span className="u-mono u-small">{row.invoice_number}</span>,
                    },
                    {
                      key: 'customer',
                      header: 'Customer',
                      render: (row) => row.customer_name || <span className="u-subtle">Walk-in</span>,
                    },
                    {
                      key: 'units',
                      header: 'Units',
                      align: 'right',
                      render: (row) => <span className="u-num">{number(row.unit_count)}</span>,
                    },
                    {
                      key: 'time',
                      header: 'Time',
                      align: 'right',
                      render: (row) => <span className="u-xs u-muted">{time(row.created_at)}</span>,
                    },
                    {
                      key: 'total',
                      header: 'Total',
                      align: 'right',
                      render: (row) => <span className="u-num u-strong">{currency(row.total)}</span>,
                    },
                  ]}
                  rows={data.recent_sales}
                  onRowClick={(row) => navigate(`/app/sales/${row.id}`)}
                />
              )}
            </Card>
          </>
        ) : null}
      </AsyncSection>
    </div>
  );
}

function HeadlineIcon({ kind }) {
  const map = {
    revenue: { icon: 'money', color: 'var(--success-600)' },
    stock: { icon: 'package', color: 'var(--warn-600)' },
    purchase: { icon: 'purchases', color: 'var(--info-500)' },
    trend: { icon: 'trending', color: 'var(--accent-600)' },
  };
  const entry = map[kind] || { icon: 'info', color: 'var(--grey-500)' };
  return <Icon name={entry.icon} size={15} style={{ color: entry.color, flexShrink: 0 }} />;
}

function MoverList({ rows = [], emptyLabel, muted = false }) {
  if (rows.length === 0) return <p className="u-small u-muted">{emptyLabel}</p>;

  return (
    <ul className="u-col" style={{ gap: 'var(--s3)' }}>
      {rows.map((row) => (
        <li key={row.product_id} className="u-row-between">
          <Link to={`/app/products/${row.product_id}`} className="u-small u-truncate">
            {row.name}
          </Link>
          <span className={`u-xs u-num u-nowrap${muted ? ' u-muted' : ''}`}>
            {number(row.total_units)} units
          </span>
        </li>
      ))}
    </ul>
  );
}
