import { useEffect, useState } from 'react';

import Button from '../../components/ui/Button.jsx';
import Modal from '../../components/ui/Modal.jsx';
import { SelectField, TextAreaField, TextField } from '../../components/ui/Field.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';

const UNITS = ['piece', 'kg', 'gram', 'litre', 'ml', 'packet', 'box'];

const BLANK = {
  sku: '', barcode: '', name: '', description: '', category: '', brand: '',
  unit: 'piece', selling_price: '', cost_price: '', tax_rate: '',
  current_stock: '', reorder_level: '', lead_time_days: '', supplier_id: '',
};

/**
 * Create or edit a product.
 *
 * When editing, the stock field is absent: stock moves only through the
 * inventory ledger, so a form that appeared to set it would be lying.
 */
export default function ProductForm({ open, onClose, onSaved, product = null }) {
  const toast = useToast();
  const editing = Boolean(product);

  const [form, setForm] = useState(BLANK);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const suppliers = useApi(() => api.listSuppliers(), [open], { enabled: open });

  useEffect(() => {
    if (!open) return;
    setError(null);
    setForm(
      product
        ? {
            ...BLANK,
            ...Object.fromEntries(
              Object.keys(BLANK).map((key) => [key, product[key] ?? '']),
            ),
          }
        : BLANK,
    );
  }, [open, product]);

  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);

    const payload = {
      sku: form.sku.trim(),
      barcode: form.barcode.trim() || null,
      name: form.name.trim(),
      description: form.description.trim() || null,
      category: form.category.trim() || 'Uncategorised',
      brand: form.brand.trim() || null,
      unit: form.unit,
      selling_price: form.selling_price || '0',
      cost_price: form.cost_price || '0',
      tax_rate: form.tax_rate || '0',
      reorder_level: Number(form.reorder_level || 0),
      lead_time_days: Number(form.lead_time_days || 3),
      supplier_id: form.supplier_id ? Number(form.supplier_id) : null,
    };

    try {
      if (editing) {
        await api.updateProduct(product.id, payload);
        toast.success(`${payload.name} updated`);
      } else {
        await api.createProduct({ ...payload, current_stock: Number(form.current_stock || 0) });
        toast.success(`${payload.name} added`);
      }
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const belowCost =
    form.selling_price && form.cost_price && Number(form.cost_price) > Number(form.selling_price);

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="wide"
      title={editing ? `Edit ${product.name}` : 'Add a product'}
      subtitle={
        editing
          ? 'Stock levels change through the inventory ledger, not this form.'
          : 'SKU and barcode must be unique within your store.'
      }
      footer={
        <>
          <Button onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} loading={saving}>
            {editing ? 'Save changes' : 'Add product'}
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
          <TextField label="Name" required value={form.name} onChange={set('name')} placeholder="Amul Taaza Milk 1L" />
          <TextField label="SKU" required value={form.sku} onChange={set('sku')} placeholder="DRY-001" />
          <TextField
            label="Barcode"
            optional
            value={form.barcode}
            onChange={set('barcode')}
            hint="Scanned at the till."
            placeholder="8901234567890"
          />
          <TextField label="Category" required value={form.category} onChange={set('category')} placeholder="Dairy" />
          <TextField label="Brand" optional value={form.brand} onChange={set('brand')} />
          <SelectField
            label="Unit"
            value={form.unit}
            onChange={set('unit')}
            options={UNITS.map((unit) => ({ value: unit, label: unit }))}
          />

          <TextField
            label="Selling price"
            type="number" min="0" step="0.01" required
            value={form.selling_price}
            onChange={set('selling_price')}
          />
          <TextField
            label="Cost price"
            type="number" min="0" step="0.01"
            value={form.cost_price}
            onChange={set('cost_price')}
            hint={belowCost ? undefined : 'Used for margin and profit reporting.'}
            error={belowCost ? 'Cost is above the selling price — check this is intended.' : null}
          />
          <TextField
            label="Tax rate (%)"
            type="number" min="0" max="100" step="0.01"
            value={form.tax_rate}
            onChange={set('tax_rate')}
          />

          {!editing ? (
            <TextField
              label="Opening stock"
              type="number" min="0"
              value={form.current_stock}
              onChange={set('current_stock')}
              hint="Recorded as an opening-stock movement."
            />
          ) : null}

          <TextField
            label="Reorder level"
            type="number" min="0"
            value={form.reorder_level}
            onChange={set('reorder_level')}
            hint="Flags the product as low stock."
          />
          <TextField
            label="Lead time (days)"
            type="number" min="0"
            value={form.lead_time_days}
            onChange={set('lead_time_days')}
            hint="How long the supplier takes. Drives reorder urgency."
          />
          <SelectField
            label="Supplier"
            value={form.supplier_id}
            onChange={set('supplier_id')}
            options={[
              { value: '', label: 'No supplier' },
              ...(suppliers.data || []).map((supplier) => ({
                value: supplier.id,
                label: supplier.name,
              })),
            ]}
          />
          <TextAreaField
            label="Description"
            optional
            className="form-grid__full"
            value={form.description}
            onChange={set('description')}
          />
        </div>
      </form>
    </Modal>
  );
}
