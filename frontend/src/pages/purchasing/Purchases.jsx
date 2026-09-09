import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import PageHeader from '../../components/layout/PageHeader.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Pagination from '../../components/ui/Pagination.jsx';
import Table from '../../components/ui/Table.jsx';
import { OrderStatusBadge } from '../../components/ui/Badge.jsx';
import { AsyncSection, EmptyState, TableSkeleton } from '../../components/ui/States.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { currency, date, number } from '../../lib/format.js';

const LIMIT = 25;
const STATUSES = ['', 'DRAFT', 'ORDERED', 'PARTIALLY_RECEIVED', 'RECEIVED', 'CANCELLED'];

export default function Purchases() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState(searchParams.get('status') || '');
  const [offset, setOffset] = useState(0);

  const orders = useApi(
    () => api.listPurchaseOrders({ status: status || undefined, limit: LIMIT, offset }),
    [status, offset],
  );

  const rows = orders.data?.items || [];

  return (
    <div className="page">
      <PageHeader
        title="Purchase orders"
        subtitle="What you have ordered, what is on its way, and what has landed."
        actions={
          <Link to="/app/purchases/new">
            <Button variant="primary" icon="plus">
              New purchase order
            </Button>
          </Link>
        }
      />

      <Card flush>
        <div className="toolbar">
          <div className="segment">
            {STATUSES.map((option) => (
              <button
                key={option || 'all'}
                type="button"
                className={`segment__option${status === option ? ' segment__option--active' : ''}`}
                onClick={() => {
                  setStatus(option);
                  setOffset(0);
                }}
              >
                {option
                  ? option
                      .split('_')
                      .map((part) => part[0] + part.slice(1).toLowerCase())
                      .join(' ')
                  : 'All'}
              </button>
            ))}
          </div>
          <div className="toolbar__spacer" />
          <span className="u-xs u-muted">{number(orders.data?.total || 0)} orders</span>
        </div>

        <AsyncSection
          loading={orders.loading}
          error={orders.error}
          onRetry={orders.reload}
          isEmpty={rows.length === 0}
          skeleton={<TableSkeleton columns={6} />}
          empty={
            <EmptyState
              icon="purchases"
              title={status ? `No ${status.toLowerCase().replace('_', ' ')} orders` : 'No purchase orders yet'}
              message={
                status
                  ? 'Switch to All to see every order.'
                  : 'Create an order by hand, or let the forecast suggest what to reorder and from whom.'
              }
              actions={
                <Link to="/app/purchases/new">
                  <Button variant="primary" icon="plus">
                    New purchase order
                  </Button>
                </Link>
              }
            />
          }
        >
          <>
            <Table
              columns={[
                {
                  key: 'po',
                  header: 'Order',
                  render: (row) => (
                    <div>
                      <div className="table__primary u-mono">{row.po_number}</div>
                      <div className="table__secondary">raised {date(row.created_at)}</div>
                    </div>
                  ),
                },
                {
                  key: 'supplier',
                  header: 'Supplier',
                  render: (row) =>
                    row.supplier_name || <span className="u-subtle">Unassigned</span>,
                },
                {
                  key: 'items',
                  header: 'Items',
                  align: 'right',
                  render: (row) => (
                    <span className="u-num u-small">
                      {number(row.item_count)}
                      <span className="u-subtle"> / {number(row.unit_count)} units</span>
                    </span>
                  ),
                },
                {
                  key: 'received',
                  header: 'Received',
                  align: 'right',
                  render: (row) => (
                    <span className="u-num u-small">
                      {row.unit_count
                        ? `${Math.round((row.received_count / row.unit_count) * 100)}%`
                        : '—'}
                    </span>
                  ),
                },
                {
                  key: 'expected',
                  header: 'Expected',
                  render: (row) => (
                    <span className="u-small u-muted">{date(row.expected_delivery)}</span>
                  ),
                },
                {
                  key: 'status',
                  header: 'Status',
                  render: (row) => <OrderStatusBadge status={row.status} />,
                },
                {
                  key: 'total',
                  header: 'Total',
                  align: 'right',
                  render: (row) => <span className="u-num u-strong">{currency(row.total)}</span>,
                },
              ]}
              rows={rows}
              onRowClick={(row) => navigate(`/app/purchases/${row.id}`)}
            />
            <Pagination
              total={orders.data?.total || 0}
              limit={LIMIT}
              offset={offset}
              onChange={setOffset}
              noun="orders"
            />
          </>
        </AsyncSection>
      </Card>
    </div>
  );
}
