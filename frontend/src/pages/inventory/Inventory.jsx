import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import AdjustmentModal from './AdjustmentModal.jsx';
import PageHeader from '../../components/layout/PageHeader.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Icon from '../../components/ui/Icon.jsx';
import Table from '../../components/ui/Table.jsx';
import { StockBadge } from '../../components/ui/Badge.jsx';
import { AsyncSection, EmptyState, TableSkeleton } from '../../components/ui/States.jsx';
import { useCan } from '../../context/AuthContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { currency, number, relativeTime } from '../../lib/format.js';

const FILTERS = [
  { id: '', label: 'All' },
  { id: 'low', label: 'Low stock' },
  { id: 'out', label: 'Out of stock' },
];

export default function Inventory() {
  const navigate = useNavigate();
  const canManage = useCan('MANAGER');
  const [searchParams, setSearchParams] = useSearchParams();

  const [filter, setFilter] = useState(searchParams.get('status') || '');
  const [search, setSearch] = useState('');
  const [adjusting, setAdjusting] = useState(null);

  const position = useApi(() => api.getStockPosition({ limit: 500 }), []);

  const all = position.data?.products || [];
  const rows = all
    .filter((row) => {
      if (filter === 'low') return row.stock_status === 'LOW';
      if (filter === 'out') return row.stock_status === 'OUT_OF_STOCK';
      return true;
    })
    .filter((row) => {
      if (!search) return true;
      const term = search.toLowerCase();
      return (
        row.name.toLowerCase().includes(term) ||
        row.sku.toLowerCase().includes(term) ||
        row.category.toLowerCase().includes(term)
      );
    });

  const columns = [
    {
      key: 'product',
      header: 'Product',
      render: (row) => (
        <div>
          <div className="table__primary">{row.name}</div>
          <div className="table__secondary u-mono">
            {row.sku} · {row.category}
          </div>
        </div>
      ),
    },
    {
      key: 'stock',
      header: 'On hand',
      align: 'right',
      render: (row) => (
        <span className="u-num u-strong">
          {number(row.current_stock)} <span className="u-xs u-subtle">{row.unit}</span>
        </span>
      ),
    },
    {
      key: 'reorder',
      header: 'Reorder at',
      align: 'right',
      render: (row) => <span className="u-num u-muted">{number(row.reorder_level)}</span>,
    },
    {
      key: 'value',
      header: 'Stock value',
      align: 'right',
      render: (row) => <span className="u-num">{currency(row.stock_value)}</span>,
    },
    {
      key: 'moved',
      header: 'Last movement',
      align: 'right',
      render: (row) => (
        <span className="u-xs u-muted">
          {row.last_movement_at ? relativeTime(row.last_movement_at) : '—'}
        </span>
      ),
    },
    { key: 'status', header: 'Status', render: (row) => <StockBadge status={row.stock_status} /> },
    ...(canManage
      ? [
          {
            key: 'actions',
            header: '',
            align: 'right',
            render: (row) => (
              <Button
                size="sm"
                onClick={(event) => {
                  event.stopPropagation();
                  setAdjusting(row);
                }}
              >
                Adjust
              </Button>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="page">
      <PageHeader
        title="Inventory"
        subtitle="What is on your shelves right now, and what it is worth."
        actions={
          <>
            <Link to="/app/inventory/movements">
              <Button icon="sales">Movement ledger</Button>
            </Link>
            {canManage ? (
              <Button variant="primary" icon="edit" onClick={() => setAdjusting({})}>
                Adjust stock
              </Button>
            ) : null}
          </>
        }
      />

      {position.data ? (
        <div className="grid grid--kpi" style={{ marginBottom: 'var(--s5)' }}>
          <div className="stat">
            <span className="stat__label">Products tracked</span>
            <span className="stat__value stat__value--sm">{number(position.data.total_products)}</span>
          </div>
          <div className={`stat${position.data.low_stock ? ' stat--warn' : ''}`}>
            <span className="stat__label">Low stock</span>
            <span className="stat__value stat__value--sm">{number(position.data.low_stock)}</span>
          </div>
          <div className={`stat${position.data.out_of_stock ? ' stat--alert' : ''}`}>
            <span className="stat__label">Out of stock</span>
            <span className="stat__value stat__value--sm">{number(position.data.out_of_stock)}</span>
          </div>
          <div className="stat">
            <span className="stat__label">Value at cost</span>
            <span className="stat__value stat__value--sm">
              {currency(position.data.inventory_cost_value, { compact: true })}
            </span>
            <span className="stat__meta">
              retail {currency(position.data.inventory_retail_value, { compact: true })}
            </span>
          </div>
        </div>
      ) : null}

      <Card flush>
        <div className="toolbar">
          <div className="segment">
            {FILTERS.map((option) => (
              <button
                key={option.id}
                type="button"
                className={`segment__option${filter === option.id ? ' segment__option--active' : ''}`}
                onClick={() => {
                  setFilter(option.id);
                  setSearchParams(option.id ? { status: option.id } : {}, { replace: true });
                }}
              >
                {option.label}
              </button>
            ))}
          </div>
          <div className="search-input">
            <Icon name="search" size={14} />
            <input
              className="input"
              placeholder="Search by name, SKU or category"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="Search inventory"
            />
          </div>
          <div className="toolbar__spacer" />
          <span className="u-xs u-muted">{number(rows.length)} shown</span>
        </div>

        <AsyncSection
          loading={position.loading}
          error={position.error}
          onRetry={position.reload}
          isEmpty={rows.length === 0}
          skeleton={<TableSkeleton columns={6} />}
          empty={
            <EmptyState
              icon="inventory"
              title={all.length === 0 ? 'No products to track yet' : 'Nothing matches'}
              message={
                all.length === 0
                  ? 'Inventory insights appear once you have added products and started selling.'
                  : 'Try a different search, or switch back to All.'
              }
              actions={
                all.length === 0 ? (
                  <Link to="/app/products">
                    <Button variant="primary" icon="plus">
                      Add products
                    </Button>
                  </Link>
                ) : (
                  <Button
                    onClick={() => {
                      setSearch('');
                      setFilter('');
                    }}
                  >
                    Clear filters
                  </Button>
                )
              }
            />
          }
        >
          <Table
            columns={columns}
            rows={rows}
            rowKey={(row) => row.product_id}
            onRowClick={(row) => navigate(`/app/products/${row.product_id}`)}
          />
        </AsyncSection>
      </Card>

      <AdjustmentModal
        open={adjusting !== null}
        product={adjusting?.product_id ? adjusting : null}
        onClose={() => setAdjusting(null)}
        onSaved={() => {
          setAdjusting(null);
          position.reload();
        }}
      />
    </div>
  );
}
