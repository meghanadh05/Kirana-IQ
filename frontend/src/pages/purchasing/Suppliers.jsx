import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import SupplierForm from './SupplierForm.jsx';
import PageHeader from '../../components/layout/PageHeader.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Icon from '../../components/ui/Icon.jsx';
import Table from '../../components/ui/Table.jsx';
import { AsyncSection, EmptyState, TableSkeleton } from '../../components/ui/States.jsx';
import { useApi } from '../../hooks/useApi.js';
import { useDebounce } from '../../hooks/useDebounce.js';
import * as api from '../../services/api.js';
import { currency, number } from '../../lib/format.js';

export default function Suppliers() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const debounced = useDebounce(search, 300);

  const suppliers = useApi(
    () => api.listSuppliers({ search: debounced || undefined }),
    [debounced],
  );

  const rows = suppliers.data || [];

  return (
    <div className="page">
      <PageHeader
        title="Suppliers"
        subtitle="Who you buy from, what they supply, and how long they take."
        actions={
          <Button variant="primary" icon="plus" onClick={() => setFormOpen(true)}>
            Add supplier
          </Button>
        }
      />

      <Card flush>
        <div className="toolbar">
          <div className="search-input">
            <Icon name="search" size={14} />
            <input
              className="input"
              placeholder="Name, contact or phone"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="Search suppliers"
            />
          </div>
          <div className="toolbar__spacer" />
          <span className="u-xs u-muted">{number(rows.length)} suppliers</span>
        </div>

        <AsyncSection
          loading={suppliers.loading}
          error={suppliers.error}
          onRetry={suppliers.reload}
          isEmpty={rows.length === 0}
          skeleton={<TableSkeleton columns={5} />}
          empty={
            <EmptyState
              icon="suppliers"
              title={debounced ? 'No suppliers match' : 'No suppliers yet'}
              message={
                debounced
                  ? 'Try a different search term.'
                  : 'Add your suppliers so reorder recommendations can be grouped into purchase orders.'
              }
              actions={
                <Button variant="primary" icon="plus" onClick={() => setFormOpen(true)}>
                  Add supplier
                </Button>
              }
            />
          }
        >
          <Table
            columns={[
              {
                key: 'name',
                header: 'Supplier',
                render: (row) => (
                  <div>
                    <div className="table__primary">{row.name}</div>
                    {row.contact_person ? (
                      <div className="table__secondary">{row.contact_person}</div>
                    ) : null}
                  </div>
                ),
              },
              {
                key: 'contact',
                header: 'Contact',
                render: (row) => (
                  <div className="u-small">
                    <div>{row.phone || <span className="u-subtle">—</span>}</div>
                    {row.email ? <div className="table__secondary">{row.email}</div> : null}
                  </div>
                ),
              },
              {
                key: 'lead',
                header: 'Lead time',
                align: 'right',
                render: (row) => (
                  <span className="u-num u-small">{row.default_lead_time_days} days</span>
                ),
              },
              {
                key: 'products',
                header: 'Products',
                align: 'right',
                render: (row) => <span className="u-num">{number(row.product_count)}</span>,
              },
              {
                key: 'open',
                header: 'Open orders',
                align: 'right',
                render: (row) =>
                  row.open_orders > 0 ? (
                    <span className="badge badge--info">{row.open_orders}</span>
                  ) : (
                    <span className="u-subtle">—</span>
                  ),
              },
              {
                key: 'total',
                header: 'Purchased',
                align: 'right',
                render: (row) => (
                  <span className="u-num">{currency(row.total_purchased, { compact: true })}</span>
                ),
              },
            ]}
            rows={rows}
            onRowClick={(row) => navigate(`/app/suppliers/${row.id}`)}
          />
        </AsyncSection>
      </Card>

      <SupplierForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSaved={() => {
          setFormOpen(false);
          suppliers.reload();
        }}
      />
    </div>
  );
}
