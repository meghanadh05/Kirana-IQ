import { useEffect, useMemo, useState } from 'react';

import Button from '../../components/ui/Button.jsx';
import Icon from '../../components/ui/Icon.jsx';
import Modal from '../../components/ui/Modal.jsx';
import { TextField } from '../../components/ui/Field.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import * as api from '../../services/api.js';
import { currency } from '../../lib/format.js';

const METHODS = [
  { value: 'CASH', label: 'Cash', icon: 'money' },
  { value: 'UPI', label: 'UPI', icon: 'trending' },
  { value: 'CARD', label: 'Card', icon: 'money' },
  { value: 'OTHER', label: 'Other', icon: 'info' },
];

/** Quick-tender buttons: the note a customer is most likely to hand over. */
function tenderSuggestions(total) {
  const rounded = Math.ceil(total);
  const notes = [rounded, Math.ceil(total / 50) * 50, Math.ceil(total / 100) * 100, Math.ceil(total / 500) * 500];
  return [...new Set(notes)].filter((value) => value >= total).slice(0, 4);
}

export default function CheckoutModal({ open, cart, totals, onClose, onComplete }) {
  const toast = useToast();

  const [method, setMethod] = useState('CASH');
  const [discount, setDiscount] = useState('');
  const [received, setReceived] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const discountValue = Number(discount) || 0;
  const payable = Math.max(totals.total - discountValue, 0);
  const receivedValue = received === '' ? payable : Number(received) || 0;
  const change = Math.max(receivedValue - payable, 0);
  const short = method === 'CASH' && receivedValue < payable;

  useEffect(() => {
    if (open) {
      setMethod('CASH');
      setDiscount('');
      setReceived('');
      setCustomerName('');
      setCustomerPhone('');
      setError(null);
    }
  }, [open]);

  const suggestions = useMemo(() => tenderSuggestions(payable), [payable]);

  async function submit(event) {
    event?.preventDefault();
    if (short) return;

    setSubmitting(true);
    setError(null);
    try {
      const sale = await api.checkout({
        items: cart.map((line) => ({ product_id: line.product_id, quantity: line.quantity })),
        payment_method: method,
        discount: discountValue.toFixed(2),
        amount_received: (method === 'CASH' ? receivedValue : payable).toFixed(2),
        customer_name: customerName || null,
        customer_phone: customerPhone || null,
      });
      toast.success(`${sale.invoice_number} completed`);
      onComplete(sale);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Take payment"
      subtitle={`${cart.length} item${cart.length === 1 ? '' : 's'} · ${totals.units} unit${totals.units === 1 ? '' : 's'}`}
      footer={
        <>
          <Button onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={submit}
            loading={submitting}
            disabled={short || cart.length === 0}
          >
            Complete sale · {currency(payable)}
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

        <div>
          <div className="field__label" style={{ marginBottom: 'var(--s2)' }}>
            Payment method
          </div>
          <div className="choice-grid">
            {METHODS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`choice${method === option.value ? ' choice--active' : ''}`}
                onClick={() => setMethod(option.value)}
              >
                <span className="u-row">
                  <Icon name={option.icon} size={14} />
                  {option.label}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="form-grid">
          <TextField
            label="Discount"
            type="number"
            min="0"
            step="0.01"
            max={totals.total}
            placeholder="0.00"
            value={discount}
            onChange={(event) => setDiscount(event.target.value)}
          />
          {method === 'CASH' ? (
            <TextField
              label="Amount received"
              type="number"
              min="0"
              step="0.01"
              placeholder={payable.toFixed(2)}
              value={received}
              onChange={(event) => setReceived(event.target.value)}
              error={short ? 'Less than the amount payable.' : null}
            />
          ) : null}
        </div>

        {method === 'CASH' && suggestions.length > 0 ? (
          <div className="u-row u-wrap">
            <span className="u-xs u-muted">Quick tender:</span>
            {suggestions.map((amount) => (
              <button
                key={amount}
                type="button"
                className="pos__chip"
                onClick={() => setReceived(String(amount))}
              >
                {currency(amount, { compact: true })}
              </button>
            ))}
          </div>
        ) : null}

        <div className="form-grid">
          <TextField
            label="Customer name"
            optional
            value={customerName}
            onChange={(event) => setCustomerName(event.target.value)}
          />
          <TextField
            label="Customer phone"
            optional
            type="tel"
            hint="Links this sale to a customer record."
            value={customerPhone}
            onChange={(event) => setCustomerPhone(event.target.value)}
          />
        </div>

        <div className="card" style={{ background: 'var(--surface-sunken)' }}>
          <div className="card__body" style={{ padding: 'var(--s4)' }}>
            <div className="cart__row">
              <span>Subtotal</span>
              <span>{currency(totals.subtotal)}</span>
            </div>
            <div className="cart__row">
              <span>Tax</span>
              <span>{currency(totals.tax)}</span>
            </div>
            {discountValue > 0 ? (
              <div className="cart__row">
                <span>Discount</span>
                <span>−{currency(discountValue)}</span>
              </div>
            ) : null}
            <div className="cart__row cart__row--total">
              <span>Payable</span>
              <span>{currency(payable)}</span>
            </div>
            {method === 'CASH' && change > 0 ? (
              <div className="cart__row" style={{ color: 'var(--success-600)', fontWeight: 600 }}>
                <span>Change to return</span>
                <span>{currency(change)}</span>
              </div>
            ) : null}
          </div>
        </div>
      </form>
    </Modal>
  );
}
