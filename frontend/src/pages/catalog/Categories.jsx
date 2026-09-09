import { useState } from 'react';
import { Link } from 'react-router-dom';

import PageHeader from '../../components/layout/PageHeader.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Modal, { ConfirmDialog } from '../../components/ui/Modal.jsx';
import Table from '../../components/ui/Table.jsx';
import { TextField } from '../../components/ui/Field.jsx';
import { AsyncSection, EmptyState, TableSkeleton } from '../../components/ui/States.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { number } from '../../lib/format.js';

export default function Categories() {
  const toast = useToast();
  const categories = useApi(() => api.listCategories(), []);

  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);

  async function remove() {
    setBusy(true);
    try {
      await api.deleteCategory(deleting.id);
      toast.success(`${deleting.name} deleted`);
      setDeleting(null);
      categories.reload();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setBusy(false);
    }
  }

  const rows = categories.data || [];

  return (
    <div className="page">
      <PageHeader
        title="Categories"
        subtitle="How your catalogue is grouped, in analytics and at the till."
        actions={
          <Button variant="primary" icon="plus" onClick={() => setEditing({})}>
            Add category
          </Button>
        }
      />

      <Card flush>
        <AsyncSection
          loading={categories.loading}
          error={categories.error}
          onRetry={categories.reload}
          isEmpty={rows.length === 0}
          skeleton={<TableSkeleton columns={3} />}
          empty={
            <EmptyState
              icon="categories"
              title="No categories yet"
              message="Categories are created automatically as you add products, or you can define them up front."
              actions={
                <>
                  <Button variant="primary" icon="plus" onClick={() => setEditing({})}>
                    Add category
                  </Button>
                  <Link to="/app/products">
                    <Button>Go to products</Button>
                  </Link>
                </>
              }
            />
          }
        >
          <Table
            columns={[
              {
                key: 'name',
                header: 'Category',
                render: (row) => (
                  <div>
                    <div className="table__primary">{row.name}</div>
                    {row.description ? (
                      <div className="table__secondary">{row.description}</div>
                    ) : null}
                  </div>
                ),
              },
              {
                key: 'count',
                header: 'Products',
                align: 'right',
                render: (row) => (
                  <Link to={`/app/products?category=${encodeURIComponent(row.name)}`} className="u-num">
                    {number(row.product_count)}
                  </Link>
                ),
              },
              {
                key: 'actions',
                header: '',
                align: 'right',
                render: (row) => (
                  <div className="u-row" style={{ justifyContent: 'flex-end' }}>
                    <Button size="sm" onClick={() => setEditing(row)}>
                      Rename
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={row.product_count > 0}
                      title={
                        row.product_count > 0
                          ? 'Move its products elsewhere before deleting'
                          : undefined
                      }
                      onClick={() => setDeleting(row)}
                    >
                      Delete
                    </Button>
                  </div>
                ),
              },
            ]}
            rows={rows}
          />
        </AsyncSection>
      </Card>

      <CategoryForm
        open={editing !== null}
        category={editing?.id ? editing : null}
        onClose={() => setEditing(null)}
        onSaved={() => {
          setEditing(null);
          categories.reload();
        }}
      />

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        onConfirm={remove}
        loading={busy}
        destructive
        title={`Delete ${deleting?.name}?`}
        confirmLabel="Delete"
        message="Only empty categories can be deleted. Products keep their category name."
      />
    </div>
  );
}

function CategoryForm({ open, category, onClose, onSaved }) {
  const toast = useToast();
  const editing = Boolean(category);
  const [form, setForm] = useState({ name: '', description: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Re-seed the form each time the dialog opens for a different category.
  const [seeded, setSeeded] = useState(null);
  if (open && seeded !== (category?.id ?? 'new')) {
    setSeeded(category?.id ?? 'new');
    setForm({ name: category?.name || '', description: category?.description || '' });
    setError(null);
  }
  if (!open && seeded !== null) setSeeded(null);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = { name: form.name.trim(), description: form.description.trim() || null };
      if (editing) {
        await api.updateCategory(category.id, payload);
        toast.success('Category updated');
      } else {
        await api.createCategory(payload);
        toast.success(`${payload.name} added`);
      }
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
      size="narrow"
      title={editing ? `Rename ${category.name}` : 'Add a category'}
      footer={
        <>
          <Button onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} loading={saving}>
            Save
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
        <TextField
          label="Name"
          required
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
        />
        <TextField
          label="Description"
          optional
          value={form.description}
          onChange={(event) => setForm({ ...form, description: event.target.value })}
        />
        {editing ? (
          <p className="u-xs u-muted">
            Renaming here does not move existing products — update them from the products page.
          </p>
        ) : null}
      </form>
    </Modal>
  );
}
