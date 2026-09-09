import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import PageHeader from '../../components/layout/PageHeader.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Icon from '../../components/ui/Icon.jsx';
import Pagination from '../../components/ui/Pagination.jsx';
import Table from '../../components/ui/Table.jsx';
import { SaleStatusBadge } from '../../components/ui/Badge.jsx';
import { AsyncSection, EmptyState, TableSkeleton } from '../../components/ui/States.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { useDebounce } from '../../hooks/useDebounce.js';
import { currency, dateTime, number, titleCase } from '../../lib/format.js';

const LIMIT = 25;

/** Named ranges, resolved to dates so the API only ever sees explicit bounds. */
const RANGES = [
  { id: 'today', label: 'Today', days: 0 },
  { id: 'yesterday', label: 'Yesterday', days: 1, single: true },
  { id: 'week', label: 'This week', days: 6 },
  { id: 'month', label: 'This month', days: 29 },
  { id: 'all', label: 'All time', days: null },
];

function resolveRange(id) {
  const range = RANGES.find((candidate) => candidate.id === id);
  if (!range || range.days === null) return {};

  const end = new Date();
  const start = new Date();
  if (range.single) {
    start.setDate(start.getDate() - range.days);
    end.setDate(end.getDate() - range.days);
  } else {
    start.setDate(start.getDate() - range.days);
  }
  const iso = (value) => value.toISOString().slice(0, 10);
  return { start_date: iso(start), end_date: iso(end) };
}

export default function Sales() {
  const navigate = useNavigate();
  const [range, setRange] = useState('month');
  const [custom, setCustom] = useState({ start_date: '', end_date: '' });
  const [paymentMethod, setPaymentMethod] = useState('');
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);

  const debouncedSearch = useDebounce(search, 300);
  const dates = range === 'custom' ? custom : resolveRange(range);

  const sales = useApi(
    () =>
      api.listSales({
        ...dates,
        payment_method: paymentMethod || undefined,
        search: debouncedSearch || undefined,
        limit: LIMIT,
        offset,
      }),
    [range, custom.start_date, custom.end_date, paymentMethod, debouncedSearch, offset],
  );

  const rows = sales.data?.items || [];
  const filtered = Boolean(debouncedSearch || paymentMethod || range !== 'all');

  const columns = [
    {
      key: 'invoice',
      header: 'Invoice',
      render: (row) => (
        <div>
          <div className="table__primary u-mono">{row.invoice_number}</div>
          <div className="table__secondary">{dateTime(row.created_at)}</div>
        </div>
      ),
    },
    {
      key: 'customer',
      header: 'Customer',
      render: (row) => (
        <div>
          <div>{row.customer_name || <span className="u-subtle">Walk-in</span>}</div>
          {row.customer_phone ? (
            <div className="table__secondary">{row.customer_phone}</div>
          ) : null}
        </div>
      ),
    },
    {
      key: 'items',
      header: 'Items',
      align: 'right',
      render: (row) => (
        <span className="u-num">
          {number(row.item_count)}
          <span className="u-subtle"> / {number(row.unit_count)} units</span>
        </span>
      ),
    },
    {
      key: 'payment',
      header: 'Payment',
      render: (row) => <span className="u-small">{titleCase(row.payment_method)}</span>,
    },
    { key: 'status', header: 'Status', render: (row) => <SaleStatusBadge status={row.status} /> },
    {
      key: 'total',
      header: 'Total',
      align: 'right',
      render: (row) => <span className="u-num u-strong">{currency(row.total)}</span>,
    },
  ];

  return (
    <div className="page">
      <PageHeader
        title="Sales"
        subtitle="Every invoice rung up at the counter."
        actions={
          <Link to="/app/pos">
            <Button variant="primary" icon="pos">
              Open POS
            </Button>
          </Link>
        }
      />

      <Card flush>
        <div className="toolbar">
          <div className="segment">
            {RANGES.map((option) => (
              <button
                key={option.id}
                type="button"
                className={`segment__option${range === option.id ? ' segment__option--active' : ''}`}
                onClick={() => {
                  setRange(option.id);
                  setOffset(0);
                }}
              >
                {option.label}
              </button>
            ))}
            <button
              type="button"
              className={`segment__option${range === 'custom' ? ' segment__option--active' : ''}`}
              onClick={() => setRange('custom')}
            >
              Custom
            </button>
          </div>

          {range === 'custom' ? (
            <div className="u-row">
              <input
                type="date"
                className="input"
                style={{ width: 150 }}
                value={custom.start_date}
                onChange={(event) => {
                  setCustom({ ...custom, start_date: event.target.value });
                  setOffset(0);
                }}
                aria-label="From date"
              />
              <span className="u-xs u-muted">to</span>
              <input
                type="date"
                className="input"
                style={{ width: 150 }}
                value={custom.end_date}
                onChange={(event) => {
                  setCustom({ ...custom, end_date: event.target.value });
                  setOffset(0);
                }}
                aria-label="To date"
              />
            </div>
          ) : null}

          <div className="toolbar__spacer" />

          <select
            className="select"
            style={{ width: 140 }}
            value={paymentMethod}
            onChange={(event) => {
              setPaymentMethod(event.target.value);
              setOffset(0);
            }}
            aria-label="Payment method"
          >
            <option value="">All payments</option>
            {['CASH', 'UPI', 'CARD', 'MIXED', 'OTHER'].map((option) => (
              <option key={option} value={option}>
                {titleCase(option)}
              </option>
            ))}
          </select>

          <div className="search-input">
            <Icon name="search" size={14} />
            <input
              className="input"
              placeholder="Invoice, name or phone"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setOffset(0);
              }}
              aria-label="Search sales"
            />
          </div>
        </div>

        <AsyncSection
          loading={sales.loading}
          error={sales.error}
          onRetry={sales.reload}
          isEmpty={rows.length === 0}
          skeleton={<TableSkeleton columns={6} />}
          empty={
            <EmptyState
              icon="sales"
              title={filtered ? 'No sales match these filters' : 'No sales yet'}
              message={
                filtered
                  ? 'Try widening the date range or clearing the search.'
                  : 'Sales appear here as soon as you ring one up at the counter.'
              }
              actions={
                filtered ? (
                  <Button
                    onClick={() => {
                      setSearch('');
                      setPaymentMethod('');
                      setRange('all');
                    }}
                  >
                    Clear filters
                  </Button>
                ) : (
                  <Link to="/app/pos">
                    <Button variant="primary" icon="pos">
                      Open POS
                    </Button>
                  </Link>
                )
              }
            />
          }
        >
          <>
            <Table
              columns={columns}
              rows={rows}
              onRowClick={(row) => navigate(`/app/sales/${row.id}`)}
            />
            <Pagination
              total={sales.data?.total || 0}
              limit={LIMIT}
              offset={offset}
              onChange={setOffset}
              noun="invoices"
            />
          </>
        </AsyncSection>
      </Card>
    </div>
  );
}
