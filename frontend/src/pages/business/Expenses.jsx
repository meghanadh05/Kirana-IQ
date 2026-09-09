import { useState } from 'react';

import PageHeader from '../../components/layout/PageHeader.jsx';
import BarChart from '../../components/charts/BarChart.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Modal, { ConfirmDialog } from '../../components/ui/Modal.jsx';
import Pagination from '../../components/ui/Pagination.jsx';
import Table from '../../components/ui/Table.jsx';
import { SelectField, TextAreaField, TextField } from '../../components/ui/Field.jsx';
import { AsyncSection, EmptyState, TableSkeleton } from '../../components/ui/States.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { currency, date, number, today } from '../../lib/format.js';

const LIMIT = 25;
const CATEGORIES = ['Rent', 'Electricity', 'Salaries', 'Transport', 'Maintenance', 'Other'];

export default function Expenses() {
  const toast = useToast();
  const [category, setCategory] = useState('');
  const [offset, setOffset] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);

  const expenses = useApi(
    () => api.listExpenses({ category: category || undefined, limit: LIMIT, offset }),
    [category, offset],
  );

  const rows = expenses.data?.items || [];

  async function remove() {
    setBusy(true);
    try {
      await api.deleteExpense(deleting.id);
      toast.success('Expense deleted');
      setDeleting(null);
      expenses.reload();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        title="Expenses"
        subtitle="Running costs, so gross profit can become an operating estimate."
        actions={
          <Button variant="primary" icon="plus" onClick={() => setFormOpen(true)}>
            Record expense
          </Button>
        }
      />

      <div className="grid grid--sidebar">
        <Card flush>
          <div className="toolbar">
            <select
              className="select"
              style={{ width: 180 }}
              value={category}
              onChange={(event) => {
                setCategory(event.target.value);
                setOffset(0);
              }}
              aria-label="Category"
            >
              <option value="">All categories</option>
              {CATEGORIES.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            <div className="toolbar__spacer" />
            <span className="u-xs u-muted">
              {number(expenses.data?.total || 0)} entries ·{' '}
              {currency(expenses.data?.total_amount || 0)}
            </span>
          </div>

          <AsyncSection
            loading={expenses.loading}
            error={expenses.error}
            onRetry={expenses.reload}
            isEmpty={rows.length === 0}
            skeleton={<TableSkeleton columns={4} />}
            empty={
              <EmptyState
                icon="expenses"
                title="No expenses recorded"
                message="Record rent, salaries, electricity and other running costs to see an estimated operating profit."
                actions={
                  <Button variant="primary" icon="plus" onClick={() => setFormOpen(true)}>
                    Record expense
                  </Button>
                }
              />
            }
          >
            <>
              <Table
                columns={[
                  {
                    key: 'date',
                    header: 'Date',
                    render: (row) => <span className="u-small">{date(row.expense_date)}</span>,
                  },
                  {
                    key: 'category',
                    header: 'Category',
                    render: (row) => (
                      <div>
                        <div className="table__primary">{row.category}</div>
                        {row.description ? (
                          <div className="table__secondary">{row.description}</div>
                        ) : null}
                      </div>
                    ),
                  },
                  {
                    key: 'method',
                    header: 'Paid by',
                    render: (row) => <span className="u-small u-muted">{row.payment_method}</span>,
                  },
                  {
                    key: 'amount',
                    header: 'Amount',
                    align: 'right',
                    render: (row) => <span className="u-num u-strong">{currency(row.amount)}</span>,
                  },
                  {
                    key: 'actions',
                    header: '',
                    align: 'right',
                    render: (row) => (
                      <Button size="sm" variant="ghost" onClick={() => setDeleting(row)}>
                        Delete
                      </Button>
                    ),
                  },
                ]}
                rows={rows}
              />
              <Pagination
                total={expenses.data?.total || 0}
                limit={LIMIT}
                offset={offset}
                onChange={setOffset}
                noun="expenses"
              />
            </>
          </AsyncSection>
        </Card>

        <Card title="By category" subtitle="For the current filter">
          {(expenses.data?.by_category || []).length === 0 ? (
            <p className="u-small u-muted">Nothing recorded yet.</p>
          ) : (
            <BarChart
              data={expenses.data.by_category.map((row) => ({
                label: `${row.category} (${row.entries})`,
                value: row.total,
                color: 'var(--warn-500)',
              }))}
              formatValue={(value) => currency(value, { compact: true })}
            />
          )}
        </Card>
      </div>

      <ExpenseForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSaved={() => {
          setFormOpen(false);
          expenses.reload();
        }}
      />

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        onConfirm={remove}
        loading={busy}
        destructive
        title="Delete this expense?"
        confirmLabel="Delete"
        message="It will no longer count towards your estimated operating profit."
      />
    </div>
  );
}

function ExpenseForm({ open, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState({
    category: 'Rent',
    description: '',
    amount: '',
    expense_date: today(),
    payment_method: 'CASH',
    notes: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.createExpense({
        category: form.category,
        description: form.description.trim() || null,
        amount: form.amount,
        expense_date: form.expense_date,
        payment_method: form.payment_method,
        notes: form.notes.trim() || null,
      });
      toast.success('Expense recorded');
      setForm({ ...form, description: '', amount: '', notes: '' });
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
      title="Record an expense"
      footer={
        <>
          <Button onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} loading={saving}>
            Record expense
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

        <div className="form-grid">
          <SelectField
            label="Category"
            value={form.category}
            onChange={set('category')}
            options={CATEGORIES.map((option) => ({ value: option, label: option }))}
          />
          <TextField
            label="Amount"
            type="number"
            min="0.01"
            step="0.01"
            required
            value={form.amount}
            onChange={set('amount')}
          />
          <TextField
            label="Date"
            type="date"
            required
            value={form.expense_date}
            onChange={set('expense_date')}
          />
          <SelectField
            label="Paid by"
            value={form.payment_method}
            onChange={set('payment_method')}
            options={['CASH', 'UPI', 'CARD', 'BANK', 'OTHER'].map((option) => ({
              value: option,
              label: option,
            }))}
          />
          <TextField
            label="Description"
            optional
            className="form-grid__full"
            placeholder="e.g. September shop rent"
            value={form.description}
            onChange={set('description')}
          />
          <TextAreaField
            label="Notes"
            optional
            className="form-grid__full"
            value={form.notes}
            onChange={set('notes')}
          />
        </div>
      </form>
    </Modal>
  );
}
