import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import PageHeader from '../../components/layout/PageHeader.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Icon from '../../components/ui/Icon.jsx';
import { RiskBadge } from '../../components/ui/Badge.jsx';
import { SelectField, TextAreaField, TextField } from '../../components/ui/Field.jsx';
import { AsyncSection, EmptyState } from '../../components/ui/States.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { currency, date, number, today } from '../../lib/format.js';

/**
 * Build a purchase order.
 *
 * The left column is where the forecast becomes a decision: the model's reorder
 * recommendations, already grouped by supplier, each with the reasoning behind
 * the quantity. Adding one to the order carries that quantity across, and the
 * buyer can still overrule it — the recommendation is advice, not an instruction.
 */
export default function NewPurchase() {
  const navigate = useNavigate();
  const toast = useToast();
  const [searchParams] = useSearchParams();

  const [supplierId, setSupplierId] = useState(searchParams.get('supplier') || '');
  const [expected, setExpected] = useState('');
  const [notes, setNotes] = useState('');
  const [lines, setLines] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const suggestions = useApi(() => api.getReorderSuggestions(), []);
  const suppliers = useApi(() => api.listSuppliers(), []);
  const products = useApi(() => api.listProducts({ limit: 300, sort: 'name' }), []);

  // Arriving from a product's reorder advice pre-loads that line.
  const presetProduct = searchParams.get('product');
  const presetQuantity = searchParams.get('quantity');

  useEffect(() => {
    if (!presetProduct || !products.data || lines.length > 0) return;
    const product = products.data.items.find((row) => String(row.id) === presetProduct);
    if (product) {
      setLines([
        {
          product_id: product.id,
          name: product.name,
          sku: product.sku,
          quantity: Number(presetQuantity) || 1,
          cost_price: Number(product.cost_price),
        },
      ]);
      if (product.supplier_id) setSupplierId(String(product.supplier_id));
    }
  }, [presetProduct, presetQuantity, products.data, lines.length]);

  // Default the delivery date to the supplier's own lead time.
  useEffect(() => {
    const supplier = (suppliers.data || []).find((row) => String(row.id) === supplierId);
    if (!supplier) return;
    const due = new Date();
    due.setDate(due.getDate() + supplier.default_lead_time_days);
    setExpected(due.toISOString().slice(0, 10));
  }, [supplierId, suppliers.data]);

  const group = useMemo(() => {
    if (!suggestions.data) return null;
    return (
      suggestions.data.groups.find((candidate) =>
        supplierId ? String(candidate.supplier_id) === supplierId : false,
      ) || null
    );
  }, [suggestions.data, supplierId]);

  function addLine(product, quantity = 1, cost) {
    setLines((current) => {
      const productId = product.product_id ?? product.id;
      const existing = current.find((line) => line.product_id === productId);
      if (existing) {
        return current.map((line) =>
          line.product_id === productId
            ? { ...line, quantity: (Number(line.quantity) || 0) + quantity }
            : line,
        );
      }
      return [
        ...current,
        {
          product_id: productId,
          name: product.name,
          sku: product.sku,
          quantity,
          cost_price: Number(cost ?? product.cost_price ?? 0),
        },
      ];
    });
  }

  function addWholeGroup() {
    if (!group) return;
    group.items.forEach((item) =>
      addLine(item, item.recommended_reorder_quantity, item.cost_price),
    );
    toast.success(`${group.items.length} recommended products added`);
  }

  // Quantity is held as typed so the field can be cleared and retyped; it is
  // coerced to a number here and again on submit.
  const quantityOf = (line) => Number(line.quantity) || 0;

  const totals = useMemo(() => {
    const subtotal = lines.reduce((sum, line) => sum + quantityOf(line) * line.cost_price, 0);
    return { subtotal, units: lines.reduce((sum, line) => sum + quantityOf(line), 0) };
  }, [lines]);

  async function submit(status) {
    if (lines.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      const order = await api.createPurchaseOrder({
        supplier_id: supplierId ? Number(supplierId) : null,
        status,
        expected_delivery: expected || null,
        notes: notes || null,
        items: lines
          .map((line) => ({
            product_id: line.product_id,
            quantity: Math.max(1, quantityOf(line)),
            cost_price: line.cost_price.toFixed(2),
          })),
      });
      toast.success(`${order.po_number} created`);
      navigate(`/app/purchases/${order.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        breadcrumb={[{ label: 'Purchase orders', to: '/app/purchases' }, { label: 'New' }]}
        title="New purchase order"
        subtitle="Start from the forecast's recommendations, or add products yourself."
      />

      {error ? (
        <div className="alert alert--error" role="alert" style={{ marginBottom: 'var(--s4)' }}>
          {error}
        </div>
      ) : null}

      <div className="grid grid--sidebar">
        <div className="u-col u-gap4">
          <Card title="Order details">
            <div className="form-grid">
              <SelectField
                label="Supplier"
                value={supplierId}
                onChange={(event) => setSupplierId(event.target.value)}
                hint="Grouping by supplier is what turns advice into one order."
                options={[
                  { value: '', label: 'No supplier' },
                  ...(suppliers.data || []).map((supplier) => ({
                    value: String(supplier.id),
                    label: `${supplier.name} — ${supplier.default_lead_time_days}d lead time`,
                  })),
                ]}
              />
              <TextField
                label="Expected delivery"
                type="date"
                min={today()}
                value={expected}
                onChange={(event) => setExpected(event.target.value)}
              />
              <TextAreaField
                label="Notes"
                optional
                className="form-grid__full"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </div>
          </Card>

          <Card
            title="Order lines"
            subtitle={lines.length ? `${lines.length} products, ${number(totals.units)} units` : undefined}
            flush
          >
            {lines.length === 0 ? (
              <EmptyState
                inline
                icon="purchases"
                title="No lines yet"
                message="Add products from the recommendations on the right, or pick them manually below."
              />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th className="is-right">Quantity</th>
                      <th className="is-right">Unit cost</th>
                      <th className="is-right">Line total</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {lines.map((line) => (
                      <tr key={line.product_id}>
                        <td>
                          <div className="table__primary">{line.name}</div>
                          <div className="table__secondary u-mono">{line.sku}</div>
                        </td>
                        <td className="is-right">
                          <input
                            type="number"
                            min="1"
                            className="input u-right"
                            style={{ width: 88, marginLeft: 'auto' }}
                            value={line.quantity}
                            aria-label={`Quantity for ${line.name}`}
                            onChange={(event) =>
                              setLines((current) =>
                                current.map((row) =>
                                  row.product_id === line.product_id
                                    ? { ...row, quantity: event.target.value }
                                    : row,
                                ),
                              )
                            }
                            onBlur={(event) =>
                              setLines((current) =>
                                current.map((row) =>
                                  row.product_id === line.product_id
                                    ? { ...row, quantity: Math.max(1, Number(event.target.value) || 1) }
                                    : row,
                                ),
                              )
                            }
                          />
                        </td>
                        <td className="is-right">
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            className="input u-right"
                            style={{ width: 100, marginLeft: 'auto' }}
                            value={line.cost_price}
                            aria-label={`Unit cost for ${line.name}`}
                            onChange={(event) =>
                              setLines((current) =>
                                current.map((row) =>
                                  row.product_id === line.product_id
                                    ? { ...row, cost_price: Number(event.target.value) || 0 }
                                    : row,
                                ),
                              )
                            }
                          />
                        </td>
                        <td className="is-right u-num u-strong">
                          {currency(quantityOf(line) * line.cost_price)}
                        </td>
                        <td className="is-right">
                          <button
                            type="button"
                            className="icon-button"
                            aria-label={`Remove ${line.name}`}
                            onClick={() =>
                              setLines((current) =>
                                current.filter((row) => row.product_id !== line.product_id),
                              )
                            }
                          >
                            <Icon name="close" size={14} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="card__footer u-row-between">
              <AddProductPicker products={products.data?.items || []} onAdd={addLine} />
              <div className="u-row u-gap4">
                <span className="u-small u-muted">Subtotal</span>
                <span className="u-strong" style={{ fontSize: 'var(--text-lg)' }}>
                  {currency(totals.subtotal)}
                </span>
              </div>
            </div>
          </Card>

          <div className="u-row" style={{ justifyContent: 'flex-end' }}>
            <Button onClick={() => navigate('/app/purchases')} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={() => submit('DRAFT')} loading={saving} disabled={lines.length === 0}>
              Save as draft
            </Button>
            <Button
              variant="primary"
              onClick={() => submit('ORDERED')}
              loading={saving}
              disabled={lines.length === 0}
            >
              Place order
            </Button>
          </div>
        </div>

        <Card
          title="Recommended to reorder"
          subtitle="From your demand forecast"
          actions={
            group ? (
              <Button size="sm" onClick={addWholeGroup}>
                Add all
              </Button>
            ) : null
          }
        >
          <AsyncSection
            loading={suggestions.loading}
            error={suggestions.error}
            onRetry={suggestions.reload}
            isEmpty={!suggestions.data?.groups?.length}
            empty={
              <EmptyState
                inline
                icon="check"
                title="Nothing needs reordering"
                message="Every product has enough stock to cover expected demand through its lead time."
              />
            }
          >
            <div className="u-col u-gap4">
              {!supplierId ? (
                <p className="u-xs u-muted">
                  Choose a supplier to see what the forecast recommends ordering from them.
                </p>
              ) : null}

              {(supplierId ? (group ? [group] : []) : suggestions.data?.groups || []).map(
                (candidate) => (
                  <div key={candidate.supplier_id ?? 'none'}>
                    {!supplierId ? (
                      <button
                        type="button"
                        className="u-row-between u-small u-strong"
                        style={{
                          width: '100%',
                          background: 'none',
                          border: 'none',
                          padding: 'var(--s1) 0',
                          textAlign: 'left',
                        }}
                        onClick={() =>
                          candidate.supplier_id && setSupplierId(String(candidate.supplier_id))
                        }
                      >
                        <span>{candidate.supplier_name || 'Unassigned products'}</span>
                        <span className="u-xs u-muted">
                          {currency(candidate.estimated_cost, { compact: true })}
                        </span>
                      </button>
                    ) : null}

                    <ul className="u-col" style={{ gap: 'var(--s3)', marginTop: 'var(--s2)' }}>
                      {candidate.items.slice(0, supplierId ? 20 : 3).map((item) => (
                        <li key={item.product_id}>
                          <div className="u-row-between">
                            <span className="u-small u-strong u-truncate">{item.name}</span>
                            <RiskBadge risk={item.risk} />
                          </div>
                          <p className="u-xs u-muted" style={{ margin: '2px 0 2px' }}>
                            {number(item.current_stock)} left · order{' '}
                            <strong>{number(item.recommended_reorder_quantity)}</strong> ·{' '}
                            {currency(item.estimated_cost)}
                          </p>
                          {/* The reasoning travels with the number: a quantity
                              nobody can explain is a quantity nobody trusts. */}
                          <p className="u-xs u-subtle" style={{ margin: '0 0 6px' }}>
                            {item.reason}
                          </p>
                          <Button
                            size="sm"
                            icon="plus"
                            onClick={() =>
                              addLine(item, item.recommended_reorder_quantity, item.cost_price)
                            }
                          >
                            Add to order
                          </Button>
                        </li>
                      ))}
                    </ul>

                    {candidate.expected_delivery && supplierId ? (
                      <p className="u-xs u-subtle u-mt4">
                        Suggested delivery date: {date(candidate.expected_delivery)}
                      </p>
                    ) : null}
                  </div>
                ),
              )}

              {supplierId && !group ? (
                <p className="u-small u-muted">
                  Nothing from this supplier needs reordering right now.
                </p>
              ) : null}
            </div>
          </AsyncSection>
        </Card>
      </div>
    </div>
  );
}

function AddProductPicker({ products, onAdd }) {
  const [value, setValue] = useState('');

  return (
    <div className="u-row">
      <select
        className="select"
        style={{ width: 260 }}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        aria-label="Add a product to the order"
      >
        <option value="">Add a product…</option>
        {products.map((product) => (
          <option key={product.id} value={product.id}>
            {product.name} — {product.current_stock} in stock
          </option>
        ))}
      </select>
      <Button
        icon="plus"
        disabled={!value}
        onClick={() => {
          const product = products.find((row) => String(row.id) === value);
          if (product) onAdd(product, 1, product.cost_price);
          setValue('');
        }}
      >
        Add
      </Button>
    </div>
  );
}
