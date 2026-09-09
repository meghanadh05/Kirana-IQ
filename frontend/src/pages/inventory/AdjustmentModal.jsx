import { useEffect, useState } from 'react';

import Button from '../../components/ui/Button.jsx';
import Modal from '../../components/ui/Modal.jsx';
import { SelectField, TextAreaField, TextField } from '../../components/ui/Field.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { number } from '../../lib/format.js';

/**
 * Stock adjustment.
 *
 * The direction is a choice rather than a sign the user has to remember, so
 * "damaged 5" cannot accidentally add five units to the shelf.
 */
const REASONS = [
  { value: 'DAMAGE', label: 'Damaged', direction: -1 },
  { value: 'EXPIRED', label: 'Expired', direction: -1 },
  { value: 'LOST', label: 'Lost or stolen', direction: -1 },
  { value: 'COUNT_CORRECTION', label: 'Stock count correction', direction: 0 },
  { value: 'RETURN', label: 'Customer return', direction: 1 },
  { value: 'OPENING_STOCK', label: 'Opening stock', direction: 1 },
  { value: 'OTHER', label: 'Other', direction: 0 },
];

export default function AdjustmentModal({ open, product, onClose, onSaved }) {
  const toast = useToast();

  const [productId, setProductId] = useState('');
  const [reason, setReason] = useState('DAMAGE');
  const [direction, setDirection] = useState('decrease');
  const [quantity, setQuantity] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const products = useApi(() => api.listProducts({ limit: 300, sort: 'name' }), [open], {
    enabled: open && !product,
  });

  useEffect(() => {
    if (!open) return;
    setProductId(product?.product_id ? String(product.product_id) : '');
    setReason('DAMAGE');
    setDirection('decrease');
    setQuantity('');
    setNotes('');
    setError(null);
  }, [open, product]);

  useEffect(() => {
    const preset = REASONS.find((option) => option.value === reason);
    if (preset?.direction === 1) setDirection('increase');
    if (preset?.direction === -1) setDirection('decrease');
  }, [reason]);

  const selected =
    product || (products.data?.items || []).find((row) => String(row.id) === productId);
  const change = (direction === 'increase' ? 1 : -1) * Number(quantity || 0);
  const resulting = selected ? Number(selected.current_stock) + change : null;
  const wouldGoNegative = resulting !== null && resulting < 0;

  async function submit(event) {
    event.preventDefault();
    if (!productId || !quantity || wouldGoNegative) return;

    setSaving(true);
    setError(null);
    try {
      await api.createAdjustment({
        product_id: Number(productId),
        quantity_change: change,
        reason,
        notes: notes || null,
      });
      toast.success('Stock adjusted and recorded in the ledger');
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
      title="Adjust stock"
      subtitle="Every adjustment is recorded in the ledger with its reason."
      footer={
        <>
          <Button onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={submit}
            loading={saving}
            disabled={!productId || !quantity || wouldGoNegative}
          >
            Apply adjustment
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

        {product ? (
          <div className="card" style={{ background: 'var(--surface-sunken)' }}>
            <div className="card__body" style={{ padding: 'var(--s3) var(--s4)' }}>
              <div className="u-strong u-small">{product.name}</div>
              <div className="u-xs u-muted">
                {product.sku} · {number(product.current_stock)} {product.unit} on hand
              </div>
            </div>
          </div>
        ) : (
          <SelectField
            label="Product"
            required
            value={productId}
            onChange={(event) => setProductId(event.target.value)}
            options={[
              { value: '', label: 'Choose a product…' },
              ...(products.data?.items || []).map((row) => ({
                value: String(row.id),
                label: `${row.name} — ${row.current_stock} ${row.unit}`,
              })),
            ]}
          />
        )}

        <SelectField
          label="Reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          options={REASONS.map((option) => ({ value: option.value, label: option.label }))}
        />

        <div className="form-grid">
          <SelectField
            label="Direction"
            value={direction}
            onChange={(event) => setDirection(event.target.value)}
            options={[
              { value: 'decrease', label: 'Remove from stock' },
              { value: 'increase', label: 'Add to stock' },
            ]}
          />
          <TextField
            label="Quantity"
            type="number"
            min="1"
            required
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            error={wouldGoNegative ? 'This would take stock below zero.' : null}
            hint={
              !wouldGoNegative && resulting !== null && quantity
                ? `Stock becomes ${number(resulting)}.`
                : undefined
            }
          />
        </div>

        <TextAreaField
          label="Notes"
          optional
          placeholder="What happened? This appears in the ledger."
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />
      </form>
    </Modal>
  );
}
