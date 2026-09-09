import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import PageHeader from '../../components/layout/PageHeader.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Icon from '../../components/ui/Icon.jsx';
import Modal from '../../components/ui/Modal.jsx';
import Pagination from '../../components/ui/Pagination.jsx';
import Table from '../../components/ui/Table.jsx';
import { TextAreaField, TextField } from '../../components/ui/Field.jsx';
import { AsyncSection, EmptyState, TableSkeleton } from '../../components/ui/States.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import { useDebounce } from '../../hooks/useDebounce.js';
import * as api from '../../services/api.js';
import { currency, date, number } from '../../lib/format.js';

const LIMIT = 25;

export default function Customers() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const debounced = useDebounce(search, 300);

  const customers = useApi(
    () => api.listCustomers({ search: debounced || undefined, limit: LIMIT, offset }),
    [debounced, offset],
  );

  const rows = customers.data?.items || [];

  return (
    <div className="page">
      <PageHeader
        title="Customers"
        subtitle="Regulars you have recorded at the till, and what they spend."
        actions={
          <Button variant="primary" icon="plus" onClick={() => setFormOpen(true)}>
            Add customer
          </Button>
        }
      />

      <Card flush>
        <div className="toolbar">
          <div className="search-input">
            <Icon name="search" size={14} />
            <input
              className="input"
              placeholder="Name, phone or email"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setOffset(0);
              }}
              aria-label="Search customers"
            />
          </div>
          <div className="toolbar__spacer" />
          <span className="u-xs u-muted">{number(customers.data?.total || 0)} customers</span>
        </div>

        <AsyncSection
          loading={customers.loading}
          error={customers.error}
          onRetry={customers.reload}
          isEmpty={rows.length === 0}
          skeleton={<TableSkeleton columns={5} />}
          empty={
            <EmptyState
              icon="customers"
              title={debounced ? 'No customers match' : 'No customers yet'}
              message={
                debounced
                  ? 'Try a different search.'
                  : 'Enter a phone number at checkout and the customer is recorded automatically.'
              }
              actions={
                <Button variant="primary" icon="plus" onClick={() => setFormOpen(true)}>
                  Add customer
                </Button>
              }
            />
          }
        >
          <>
            <Table
              columns={[
                {
                  key: 'name',
                  header: 'Customer',
                  render: (row) => (
                    <div>
                      <div className="table__primary">{row.name}</div>
                      <div className="table__secondary">{row.phone || row.email || '—'}</div>
                    </div>
                  ),
                },
                {
                  key: 'purchases',
                  header: 'Purchases',
                  align: 'right',
                  render: (row) => <span className="u-num">{number(row.purchase_count)}</span>,
                },
                {
                  key: 'spent',
                  header: 'Total spent',
                  align: 'right',
                  render: (row) => (
                    <span className="u-num u-strong">{currency(row.total_spent)}</span>
                  ),
                },
                {
                  key: 'average',
                  header: 'Average order',
                  align: 'right',
                  render: (row) => (
                    <span className="u-num u-muted">
                      {row.purchase_count
                        ? currency(Number(row.total_spent) / row.purchase_count)
                        : '—'}
                    </span>
                  ),
                },
                {
                  key: 'last',
                  header: 'Last visit',
                  align: 'right',
                  render: (row) => <span className="u-small u-muted">{date(row.last_purchase)}</span>,
                },
              ]}
              rows={rows}
              onRowClick={(row) => navigate(`/app/customers/${row.id}`)}
            />
            <Pagination
              total={customers.data?.total || 0}
              limit={LIMIT}
              offset={offset}
              onChange={setOffset}
              noun="customers"
            />
          </>
        </AsyncSection>
      </Card>

      <CustomerForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSaved={() => {
          setFormOpen(false);
          customers.reload();
        }}
      />
    </div>
  );
}

function CustomerForm({ open, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState({ name: '', phone: '', email: '', notes: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.createCustomer({
        name: form.name.trim(),
        phone: form.phone.trim() || null,
        email: form.email.trim() || null,
        notes: form.notes.trim() || null,
      });
      toast.success(`${form.name} added`);
      setForm({ name: '', phone: '', email: '', notes: '' });
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add a customer"
      footer={
        <>
          <Button onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} loading={saving}>
            Add customer
          </Button>
        </>
      }
    >
      <form onSubmit={submit} className="u-col u-gap4">
        {error ? (
          <div className="alert alert--error" role="alert">
            {error}
          </div>
        ) : null}
        <TextField label="Name" required value={form.name} onChange={set('name')} />
        <TextField
          label="Phone"
          type="tel"
          optional
          hint="Used to match them automatically at checkout."
          value={form.phone}
          onChange={set('phone')}
        />
        <TextField label="Email" type="email" optional value={form.email} onChange={set('email')} />
        <TextAreaField label="Notes" optional value={form.notes} onChange={set('notes')} />
      </form>
    </Modal>
  );
}
