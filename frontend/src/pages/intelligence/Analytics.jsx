import { useState } from 'react';
import { Link } from 'react-router-dom';

import BarChart from '../../components/charts/BarChart.jsx';
import LineChart from '../../components/charts/LineChart.jsx';
import PageHeader from '../../components/layout/PageHeader.jsx';
import Card from '../../components/ui/Card.jsx';
import StatCard from '../../components/ui/StatCard.jsx';
import Table from '../../components/ui/Table.jsx';
import { AsyncSection, CardSkeleton, EmptyState } from '../../components/ui/States.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { currency, date, number, percent, titleCase } from '../../lib/format.js';

const TABS = [
  { id: 'sales', label: 'Sales' },
  { id: 'products', label: 'Products' },
  { id: 'inventory', label: 'Inventory' },
  { id: 'categories', label: 'Categories' },
  { id: 'profit', label: 'Profit' },
];

const PERIODS = [
  { id: '7d', label: '7 days' },
  { id: '30d', label: '30 days' },
  { id: '90d', label: '90 days' },
  { id: '365d', label: '1 year' },
];

export default function Analytics() {
  const [tab, setTab] = useState('sales');
  const [period, setPeriod] = useState('30d');

  return (
    <div className="page">
      <PageHeader
        title="Analytics"
        subtitle="How the business is actually performing, measured from your invoices."
        actions={
          <div className="segment">
            {PERIODS.map((option) => (
              <button
                key={option.id}
                type="button"
                className={`segment__option${period === option.id ? ' segment__option--active' : ''}`}
                onClick={() => setPeriod(option.id)}
              >
                {option.label}
              </button>
            ))}
          </div>
        }
      />

      <div className="tabs" style={{ marginBottom: 'var(--s5)' }}>
        {TABS.map((option) => (
          <button
            key={option.id}
            type="button"
            className={`tab${tab === option.id ? ' tab--active' : ''}`}
            onClick={() => setTab(option.id)}
          >
            {option.label}
          </button>
        ))}
      </div>

      {tab === 'sales' ? <SalesTab period={period} /> : null}
      {tab === 'products' ? <ProductsTab period={period} /> : null}
      {tab === 'inventory' ? <InventoryTab period={period} /> : null}
      {tab === 'categories' ? <CategoriesTab period={period} /> : null}
      {tab === 'profit' ? <ProfitTab period={period} /> : null}
    </div>
  );
}

function SalesTab({ period }) {
  const sales = useApi(() => api.getSalesAnalytics({ period }), [period]);

  return (
    <AsyncSection
      loading={sales.loading}
      error={sales.error}
      onRetry={sales.reload}
      skeleton={<CardSkeleton height={300} />}
    >
      {sales.data ? (
        <>
          <div className="grid grid--kpi">
            <StatCard label="Revenue" value={currency(sales.data.revenue, { compact: true })} />
            <StatCard label="Transactions" value={number(sales.data.orders)} />
            <StatCard label="Units sold" value={number(sales.data.units)} />
            <StatCard
              label="Average order"
              value={currency(sales.data.average_order_value)}
              meta={`${currency(sales.data.daily_average_revenue, { compact: true })} / day`}
            />
          </div>

          <Card
            title="Revenue over time"
            subtitle={`${date(sales.data.start_date)} – ${date(sales.data.end_date)}`}
            className="u-mt4"
          >
            <LineChart
              height={260}
              series={[
                {
                  name: 'Revenue',
                  points: sales.data.series.map((point) => ({
                    label: point.date,
                    value: Number(point.revenue),
                  })),
                },
              ]}
              formatValue={(value) => currency(value, { compact: true })}
              formatLabel={(label) => date(label, { year: undefined })}
            />
          </Card>

          <Card title="Payment methods" className="u-mt4">
            {sales.data.payment_split.length === 0 ? (
              <p className="u-small u-muted">No sales in this period.</p>
            ) : (
              <BarChart
                data={sales.data.payment_split.map((row) => ({
                  label: `${titleCase(row.payment_method)} · ${row.orders} orders`,
                  value: row.revenue,
                }))}
                formatValue={(value) => currency(value, { compact: true })}
              />
            )}
          </Card>
        </>
      ) : null}
    </AsyncSection>
  );
}

function ProductsTab({ period }) {
  const products = useApi(() => api.getProductAnalytics({ period, limit: 10 }), [period]);

  const table = (rows, valueKey, formatter) => (
    <Table
      columns={[
        {
          key: 'name',
          header: 'Product',
          render: (row) => (
            <Link to={`/app/products/${row.product_id}`} className="table__primary">
              {row.name}
            </Link>
          ),
        },
        {
          key: 'value',
          header: titleCase(valueKey.replace(/_/g, ' ')),
          align: 'right',
          render: (row) => <span className="u-num u-strong">{formatter(row[valueKey])}</span>,
        },
      ]}
      rows={rows}
      rowKey={(row) => row.product_id}
      emptyMessage="No sales in this period"
    />
  );

  return (
    <AsyncSection
      loading={products.loading}
      error={products.error}
      onRetry={products.reload}
      skeleton={<CardSkeleton height={300} />}
    >
      {products.data ? (
        <div className="grid grid--2">
          <Card title="Best sellers" subtitle="By units sold" flush>
            {table(products.data.best_sellers, 'total_units', number)}
          </Card>
          <Card title="Most profitable" subtitle="Gross profit, net of tax" flush>
            {table(products.data.most_profitable, 'gross_profit', (value) => currency(value))}
          </Card>
          <Card title="Worst sellers" subtitle="Sold, but slowly" flush>
            {table(products.data.worst_sellers, 'total_units', number)}
          </Card>
          <Card title="No sales at all" subtitle="Nothing sold in this period" flush>
            {products.data.no_sales.length === 0 ? (
              <EmptyState
                inline
                icon="check"
                title="Everything sold"
                message="Every active product moved at least once in this period."
              />
            ) : (
              <Table
                columns={[
                  {
                    key: 'name',
                    header: 'Product',
                    render: (row) => (
                      <Link to={`/app/products/${row.product_id}`} className="table__primary">
                        {row.name}
                      </Link>
                    ),
                  },
                  {
                    key: 'stock',
                    header: 'Stock held',
                    align: 'right',
                    render: (row) => <span className="u-num">{number(row.current_stock)}</span>,
                  },
                ]}
                rows={products.data.no_sales}
                rowKey={(row) => row.product_id}
              />
            )}
          </Card>
        </div>
      ) : null}
    </AsyncSection>
  );
}

function InventoryTab({ period }) {
  const inventory = useApi(() => api.getInventoryAnalytics({ period }), [period]);

  return (
    <AsyncSection
      loading={inventory.loading}
      error={inventory.error}
      onRetry={inventory.reload}
      skeleton={<CardSkeleton height={300} />}
    >
      {inventory.data ? (
        <>
          <div className="grid grid--kpi">
            <StatCard
              label="Inventory value"
              value={currency(inventory.data.inventory_cost_value, { compact: true })}
              meta="at cost price"
            />
            <StatCard
              label="Retail value"
              value={currency(inventory.data.inventory_retail_value, { compact: true })}
              meta="if everything sold at list"
            />
            <StatCard
              label="Stock turnover"
              value={inventory.data.stock_turnover ?? '—'}
              meta={
                inventory.data.stock_turnover
                  ? 'cost of goods ÷ inventory value'
                  : 'needs inventory and sales'
              }
            />
            <StatCard
              label="Dead stock"
              value={currency(inventory.data.dead_stock_value, { compact: true })}
              tone={inventory.data.dead_stock_value > 0 ? 'warn' : undefined}
              meta={`${number(inventory.data.dead_stock.length)} products unsold`}
            />
          </div>

          <div className="grid grid--2 u-mt4">
            <Card title="Dead stock" subtitle="Held, but nothing sold this period" flush>
              {inventory.data.dead_stock.length === 0 ? (
                <EmptyState
                  inline
                  icon="check"
                  title="No dead stock"
                  message="Everything on your shelves sold at least once."
                />
              ) : (
                <Table
                  columns={[
                    {
                      key: 'name',
                      header: 'Product',
                      render: (row) => (
                        <Link to={`/app/products/${row.product_id}`} className="table__primary">
                          {row.name}
                        </Link>
                      ),
                    },
                    {
                      key: 'stock',
                      header: 'Held',
                      align: 'right',
                      render: (row) => <span className="u-num">{number(row.current_stock)}</span>,
                    },
                    {
                      key: 'value',
                      header: 'Tied-up capital',
                      align: 'right',
                      render: (row) => (
                        <span className="u-num u-strong">{currency(row.stock_value)}</span>
                      ),
                    },
                  ]}
                  rows={inventory.data.dead_stock}
                  rowKey={(row) => row.product_id}
                />
              )}
            </Card>

            <Card title="Overstocked" subtitle="More cover than the demand justifies" flush>
              {inventory.data.overstock.length === 0 ? (
                <EmptyState
                  inline
                  icon="check"
                  title="Nothing overstocked"
                  message="Or the forecast model has not been trained yet."
                />
              ) : (
                <Table
                  columns={[
                    {
                      key: 'name',
                      header: 'Product',
                      render: (row) => (
                        <Link to={`/app/products/${row.product_id}`} className="table__primary">
                          {row.name}
                        </Link>
                      ),
                    },
                    {
                      key: 'stock',
                      header: 'Stock',
                      align: 'right',
                      render: (row) => <span className="u-num">{number(row.current_stock)}</span>,
                    },
                    {
                      key: 'cover',
                      header: 'Days of cover',
                      align: 'right',
                      render: (row) => (
                        <span className="u-num">
                          {row.stock_cover_days === null ? '—' : row.stock_cover_days.toFixed(0)}
                        </span>
                      ),
                    },
                  ]}
                  rows={inventory.data.overstock}
                  rowKey={(row) => row.product_id}
                />
              )}
            </Card>
          </div>
        </>
      ) : null}
    </AsyncSection>
  );
}

function CategoriesTab({ period }) {
  const days = { '7d': 7, '30d': 30, '90d': 90, '365d': 365 }[period] || 30;
  const categories = useApi(() => api.getCategoryAnalytics(days), [days]);

  return (
    <AsyncSection
      loading={categories.loading}
      error={categories.error}
      onRetry={categories.reload}
      isEmpty={(categories.data || []).length === 0}
      skeleton={<CardSkeleton height={280} />}
      empty={
        <EmptyState
          icon="categories"
          title="No category data yet"
          message="Category performance appears once you have sales across your catalogue."
        />
      }
    >
      <div className="grid grid--2">
        <Card title="Revenue by category">
          <BarChart
            data={(categories.data || []).map((row) => ({
              label: row.category,
              value: row.current_revenue,
            }))}
            formatValue={(value) => currency(value, { compact: true })}
          />
        </Card>

        <Card title="Growth" subtitle="This period versus the one before" flush>
          <Table
            columns={[
              { key: 'category', header: 'Category', render: (row) => row.category },
              {
                key: 'units',
                header: 'Units',
                align: 'right',
                render: (row) => <span className="u-num">{number(row.current_units)}</span>,
              },
              {
                key: 'change',
                header: 'Change',
                align: 'right',
                render: (row) =>
                  row.change_pct === null ? (
                    <span className="u-subtle u-xs">no prior data</span>
                  ) : (
                    <span
                      className="u-num u-strong"
                      style={{
                        color:
                          row.change_pct > 0
                            ? 'var(--success-600)'
                            : row.change_pct < 0
                              ? 'var(--danger-600)'
                              : undefined,
                      }}
                    >
                      {row.change_pct > 0 ? '+' : ''}
                      {percent(row.change_pct)}
                    </span>
                  ),
              },
              {
                key: 'share',
                header: 'Share',
                align: 'right',
                render: (row) => <span className="u-num u-muted">{percent(row.contribution_pct)}</span>,
              },
            ]}
            rows={categories.data || []}
            rowKey={(row) => row.category}
          />
        </Card>
      </div>
    </AsyncSection>
  );
}

function ProfitTab({ period }) {
  const profit = useApi(() => api.getProfitAnalytics({ period }), [period]);

  return (
    <AsyncSection
      loading={profit.loading}
      error={profit.error}
      onRetry={profit.reload}
      skeleton={<CardSkeleton height={280} />}
    >
      {profit.data ? (
        <>
          <div className="grid grid--kpi">
            <StatCard
              label="Revenue"
              value={currency(profit.data.revenue, { compact: true })}
              meta={`incl. ${currency(profit.data.tax, { compact: true })} tax`}
            />
            <StatCard
              label="Cost of goods"
              value={currency(profit.data.cost_of_goods, { compact: true })}
            />
            <StatCard
              label="Gross profit"
              value={currency(profit.data.gross_profit, { compact: true })}
              meta={
                profit.data.gross_margin_pct === null
                  ? 'no revenue in this period'
                  : `${percent(profit.data.gross_margin_pct)} margin`
              }
            />
            <StatCard
              label="Estimated operating profit"
              value={currency(profit.data.estimated_operating_profit, { compact: true })}
              meta={`after ${currency(profit.data.recorded_expenses, { compact: true })} expenses`}
            />
          </div>

          <div className="grid grid--2 u-mt4">
            <Card title="How it breaks down">
              <dl className="u-col" style={{ gap: 'var(--s3)' }}>
                <Line label="Revenue (incl. tax)" value={profit.data.revenue} />
                <Line label="Less: tax collected" value={-profit.data.tax} />
                <Line label="Net revenue" value={profit.data.net_revenue} strong />
                <Line label="Less: cost of goods sold" value={-profit.data.cost_of_goods} />
                <Line label="Gross profit" value={profit.data.gross_profit} strong />
                <Line label="Less: recorded expenses" value={-profit.data.recorded_expenses} />
                <Line
                  label="Estimated operating profit"
                  value={profit.data.estimated_operating_profit}
                  strong
                />
              </dl>
              <p className="u-xs u-muted u-mt4">{profit.data.note}</p>
            </Card>

            <Card title="Expenses by category">
              {profit.data.expense_breakdown.length === 0 ? (
                <EmptyState
                  inline
                  icon="expenses"
                  title="No expenses recorded"
                  message="Record rent, salaries and other costs to turn gross profit into an operating estimate."
                  actions={
                    <Link to="/app/expenses">
                      <span className="btn btn--secondary btn--sm">Record an expense</span>
                    </Link>
                  }
                />
              ) : (
                <BarChart
                  data={profit.data.expense_breakdown.map((row) => ({
                    label: row.category,
                    value: row.total,
                    color: 'var(--warn-500)',
                  }))}
                  formatValue={(value) => currency(value, { compact: true })}
                />
              )}
            </Card>
          </div>
        </>
      ) : null}
    </AsyncSection>
  );
}

function Line({ label, value, strong = false }) {
  return (
    <div className="u-row-between" style={{ paddingTop: strong ? 'var(--s2)' : 0, borderTop: strong ? '1px solid var(--border)' : 'none' }}>
      <dt className={`u-small${strong ? ' u-strong' : ' u-muted'}`}>{label}</dt>
      <dd className={`u-num${strong ? ' u-strong' : ''}`} style={{ margin: 0 }}>
        {currency(value)}
      </dd>
    </div>
  );
}
