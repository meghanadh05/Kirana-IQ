import { useNavigate, useParams } from 'react-router-dom';

import PageHeader from '../../components/layout/PageHeader.jsx';
import Card from '../../components/ui/Card.jsx';
import Table from '../../components/ui/Table.jsx';
import { SaleStatusBadge } from '../../components/ui/Badge.jsx';
import { EmptyState, ErrorState, Loading } from '../../components/ui/States.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { currency, date, dateTime, number } from '../../lib/format.js';

export default function CustomerDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const customer = useApi(() => api.getCustomer(id), [id]);

  if (customer.loading) return <div className="page"><Loading /></div>;
  if (customer.error) {
    return (
      <div className="page">
        <ErrorState error={customer.error} onRetry={customer.reload} />
      </div>
    );
  }

  const data = customer.data;

  return (
    <div className="page">
      <PageHeader
        breadcrumb={[{ label: 'Customers', to: '/app/customers' }, { label: data.name }]}
        title={data.name}
        subtitle={[data.phone, data.email].filter(Boolean).join(' · ') || 'No contact details'}
      />

      <div className="grid grid--kpi" style={{ marginBottom: 'var(--s5)' }}>
        <div className="stat">
          <span className="stat__label">Total spent</span>
          <span className="stat__value stat__value--sm">{currency(data.total_spent)}</span>
        </div>
        <div className="stat">
          <span className="stat__label">Purchases</span>
          <span className="stat__value stat__value--sm">{number(data.purchase_count)}</span>
        </div>
        <div className="stat">
          <span className="stat__label">Average order</span>
          <span className="stat__value stat__value--sm">{currency(data.average_order_value)}</span>
        </div>
        <div className="stat">
          <span className="stat__label">Last visit</span>
          <span className="stat__value stat__value--sm">{date(data.last_purchase)}</span>
        </div>
      </div>

      <Card title="Purchase history" flush>
        {data.purchases.length === 0 ? (
          <EmptyState
            inline
            icon="sales"
            title="No purchases recorded"
            message="Sales linked to this customer's phone number will appear here."
          />
        ) : (
          <Table
            columns={[
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
                key: 'items',
                header: 'Items',
                align: 'right',
                render: (row) => <span className="u-num">{number(row.unit_count)} units</span>,
              },
              { key: 'status', header: 'Status', render: (row) => <SaleStatusBadge status={row.status} /> },
              {
                key: 'total',
                header: 'Total',
                align: 'right',
                render: (row) => <span className="u-num u-strong">{currency(row.total)}</span>,
              },
            ]}
            rows={data.purchases}
            onRowClick={(row) => navigate(`/app/sales/${row.id}`)}
          />
        )}
      </Card>

      {data.notes ? (
        <Card title="Notes" className="u-mt4">
          <p className="u-small u-muted">{data.notes}</p>
        </Card>
      ) : null}
    </div>
  );
}
