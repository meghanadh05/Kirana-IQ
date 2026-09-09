import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import PageHeader from '../../components/layout/PageHeader.jsx';
import Card from '../../components/ui/Card.jsx';
import Pagination from '../../components/ui/Pagination.jsx';
import Table from '../../components/ui/Table.jsx';
import Badge from '../../components/ui/Badge.jsx';
import { AsyncSection, EmptyState, TableSkeleton } from '../../components/ui/States.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { dateTime, number, titleCase } from '../../lib/format.js';

const LIMIT = 30;

const TYPES = [
  '', 'SALE', 'PURCHASE', 'RETURN', 'DAMAGE', 'MANUAL_ADJUSTMENT', 'OPENING_STOCK',
];

const TONE = {
  SALE: 'info',
  PURCHASE: 'success',
  RETURN: 'accent',
  DAMAGE: 'danger',
  MANUAL_ADJUSTMENT: 'warn',
  OPENING_STOCK: 'neutral',
};

/**
 * The stock ledger.
 *
 * Every unit that entered or left is here with its reason, so the current stock
 * figure is always explainable rather than merely asserted.
 */
export default function Movements() {
  const [searchParams] = useSearchParams();
  const productId = searchParams.get('product');

  const [type, setType] = useState('');
  const [offset, setOffset] = useState(0);

  const movements = useApi(
    () =>
      api.listMovements({
        product_id: productId || undefined,
        type: type || undefined,
        limit: LIMIT,
        offset,
      }),
    [productId, type, offset],
  );

  const rows = movements.data?.items || [];

  return (
    <div className="page">
      <PageHeader
        breadcrumb={[{ label: 'Inventory', to: '/app/inventory' }, { label: 'Movements' }]}
        title="Stock movements"
        subtitle="Every change to stock, with the reason it happened."
      />

      <Card flush>
        <div className="toolbar">
          <select
            className="select"
            style={{ width: 200 }}
            value={type}
            onChange={(event) => {
              setType(event.target.value);
              setOffset(0);
            }}
            aria-label="Movement type"
          >
            {TYPES.map((option) => (
              <option key={option || 'all'} value={option}>
                {option ? titleCase(option) : 'All movement types'}
              </option>
            ))}
          </select>
          <div className="toolbar__spacer" />
          <span className="u-xs u-muted">{number(movements.data?.total || 0)} movements</span>
        </div>

        <AsyncSection
          loading={movements.loading}
          error={movements.error}
          onRetry={movements.reload}
          isEmpty={rows.length === 0}
          skeleton={<TableSkeleton columns={6} />}
          empty={
            <EmptyState
              icon="inventory"
              title="No movements recorded"
              message="Sales, deliveries, adjustments and opening stock all appear here as they happen."
            />
          }
        >
          <>
            <Table
              columns={[
                {
                  key: 'product',
                  header: 'Product',
                  render: (row) => (
                    <div>
                      <div className="table__primary">{row.product_name}</div>
                      <div className="table__secondary u-mono">{row.sku}</div>
                    </div>
                  ),
                },
                {
                  key: 'type',
                  header: 'Type',
                  render: (row) => (
                    <Badge tone={TONE[row.type] || 'neutral'}>{titleCase(row.type)}</Badge>
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
                        color:
                          row.quantity_change > 0 ? 'var(--success-600)' : 'var(--danger-600)',
                      }}
                    >
                      {row.quantity_change > 0 ? '+' : ''}
                      {number(row.quantity_change)}
                    </span>
                  ),
                },
                {
                  key: 'balance',
                  header: 'Before → after',
                  align: 'right',
                  render: (row) => (
                    <span className="u-num u-small u-muted">
                      {number(row.quantity_before)} → <strong>{number(row.quantity_after)}</strong>
                    </span>
                  ),
                },
                {
                  key: 'why',
                  header: 'Reason',
                  render: (row) => (
                    <div>
                      <div className="u-small">{row.notes || '—'}</div>
                      {row.created_by_name ? (
                        <div className="table__secondary">by {row.created_by_name}</div>
                      ) : null}
                    </div>
                  ),
                },
                {
                  key: 'when',
                  header: 'When',
                  align: 'right',
                  render: (row) => <span className="u-xs u-muted">{dateTime(row.created_at)}</span>,
                },
              ]}
              rows={rows}
            />
            <Pagination
              total={movements.data?.total || 0}
              limit={LIMIT}
              offset={offset}
              onChange={setOffset}
              noun="movements"
            />
          </>
        </AsyncSection>
      </Card>
    </div>
  );
}
