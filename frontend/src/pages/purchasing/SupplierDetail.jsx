import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import SupplierForm from './SupplierForm.jsx';
import PageHeader from '../../components/layout/PageHeader.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Table from '../../components/ui/Table.jsx';
import { OrderStatusBadge } from '../../components/ui/Badge.jsx';
import { EmptyState, ErrorState, Loading } from '../../components/ui/States.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { currency, date, number } from '../../lib/format.js';

export default function SupplierDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const supplier = useApi(() => api.getSupplier(id), [id]);
  const [editing, setEditing] = useState(false);

  if (supplier.loading) return <div className="page"><Loading /></div>;
  if (supplier.error) {
    return (
      <div className="page">
        <ErrorState error={supplier.error} onRetry={supplier.reload} />
      </div>
    );
  }

  const data = supplier.data;

  return (
    <div className="page">
      <PageHeader
        breadcrumb={[{ label: 'Suppliers', to: '/app/suppliers' }, { label: data.name }]}
        title={data.name}
        subtitle={data.contact_person || 'Supplier'}
        actions={
          <>
            <Button icon="edit" onClick={() => setEditing(true)}>
              Edit
            </Button>
            <Button
              variant="primary"
              icon="purchases"
              onClick={() => navigate(`/app/purchases/new?supplier=${data.id}`)}
            >
              New purchase order
            </Button>
          </>
        }
      />

      <div className="grid grid--kpi" style={{ marginBottom: 'var(--s5)' }}>
        <div className="stat">
          <span className="stat__label">Products supplied</span>
          <span className="stat__value stat__value--sm">{number(data.products.length)}</span>
        </div>
        <div className="stat">
          <span className="stat__label">Lead time</span>
          <span className="stat__value stat__value--sm">{data.default_lead_time_days}d</span>
        </div>
        <div className={`stat${data.open_orders ? ' stat--warn' : ''}`}>
          <span className="stat__label">Open orders</span>
          <span className="stat__value stat__value--sm">{number(data.open_orders)}</span>
        </div>
        <div className="stat">
          <span className="stat__label">Total purchased</span>
          <span className="stat__value stat__value--sm">
            {currency(data.total_purchased, { compact: true })}
          </span>
          <span className="stat__meta">across {number(data.order_count)} orders</span>
        </div>
      </div>

      <div className="grid grid--sidebar">
        <div className="u-col u-gap4">
          <Card title="Purchase history" flush>
            {data.purchase_orders.length === 0 ? (
              <EmptyState
                inline
                icon="purchases"
                title="No orders yet"
                message="Purchase orders raised with this supplier will appear here."
                actions={
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => navigate(`/app/purchases/new?supplier=${data.id}`)}
                  >
                    Create one
                  </Button>
                }
              />
            ) : (
              <Table
                columns={[
                  {
                    key: 'po',
                    header: 'Order',
                    render: (row) => <span className="u-mono u-small">{row.po_number}</span>,
                  },
                  {
                    key: 'status',
                    header: 'Status',
                    render: (row) => <OrderStatusBadge status={row.status} />,
                  },
                  {
                    key: 'expected',
                    header: 'Expected',
                    render: (row) => (
                      <span className="u-small u-muted">{date(row.expected_delivery)}</span>
                    ),
                  },
                  {
                    key: 'total',
                    header: 'Total',
                    align: 'right',
                    render: (row) => <span className="u-num u-strong">{currency(row.total)}</span>,
                  },
                ]}
                rows={data.purchase_orders}
                onRowClick={(row) => navigate(`/app/purchases/${row.id}`)}
              />
            )}
          </Card>

          <Card title="Products supplied" flush>
            {data.products.length === 0 ? (
              <EmptyState
                inline
                icon="products"
                title="No products assigned"
                message="Assign this supplier on a product to group its reorder recommendations here."
                actions={
                  <Link to="/app/products">
                    <Button size="sm">Go to products</Button>
                  </Link>
                }
              />
            ) : (
              <Table
                columns={[
                  {
                    key: 'name',
                    header: 'Product',
                    render: (row) => (
                      <div>
                        <div className="table__primary">{row.name}</div>
                        <div className="table__secondary u-mono">{row.sku}</div>
                      </div>
                    ),
                  },
                  {
                    key: 'stock',
                    header: 'Stock',
                    align: 'right',
                    render: (row) => <span className="u-num">{number(row.current_stock)}</span>,
                  },
                  {
                    key: 'cost',
                    header: 'Cost',
                    align: 'right',
                    render: (row) => <span className="u-num">{currency(row.cost_price)}</span>,
                  },
                ]}
                rows={data.products}
                rowKey={(row) => row.product_id}
                onRowClick={(row) => navigate(`/app/products/${row.product_id}`)}
              />
            )}
          </Card>
        </div>

        <Card title="Contact details">
          <dl className="u-col" style={{ gap: 'var(--s3)' }}>
            <Detail label="Contact" value={data.contact_person || '—'} />
            <Detail label="Phone" value={data.phone || '—'} />
            <Detail label="Email" value={data.email || '—'} />
            <Detail label="GST" value={data.gst_number || '—'} />
            <Detail label="Address" value={data.address || '—'} />
            {data.notes ? <Detail label="Notes" value={data.notes} /> : null}
          </dl>
        </Card>
      </div>

      <SupplierForm
        open={editing}
        supplier={data}
        onClose={() => setEditing(false)}
        onSaved={() => {
          setEditing(false);
          supplier.reload();
        }}
      />
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div className="u-row-between">
      <dt className="u-xs u-muted">{label}</dt>
      <dd className="u-small" style={{ margin: 0, textAlign: 'right', maxWidth: '60%' }}>
        {value}
      </dd>
    </div>
  );
}
