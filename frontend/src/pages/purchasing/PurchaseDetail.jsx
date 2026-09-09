import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import PageHeader from '../../components/layout/PageHeader.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Modal, { ConfirmDialog } from '../../components/ui/Modal.jsx';
import Table from '../../components/ui/Table.jsx';
import { OrderStatusBadge } from '../../components/ui/Badge.jsx';
import { ErrorState, Loading } from '../../components/ui/States.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { currency, date, dateTime, number } from '../../lib/format.js';

export default function PurchaseDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();

  const order = useApi(() => api.getPurchaseOrder(id), [id]);
  const [receiveOpen, setReceiveOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  if (order.loading) return <div className="page"><Loading /></div>;
  if (order.error) {
    return (
      <div className="page">
        <ErrorState error={order.error} onRetry={order.reload} />
      </div>
    );
  }

  const data = order.data;
  const outstanding = data.items.reduce(
    (sum, item) => sum + (item.quantity - item.received_quantity),
    0,
  );

  async function setStatus(status) {
    setBusy(true);
    try {
      await api.setPurchaseStatus(data.id, status);
      toast.success(`${data.po_number} is now ${status.toLowerCase().replace('_', ' ')}`);
      setCancelOpen(false);
      order.reload();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        breadcrumb={[{ label: 'Purchase orders', to: '/app/purchases' }, { label: data.po_number }]}
        title={data.po_number}
        subtitle={
          data.supplier_name
            ? `${data.supplier_name} · raised ${date(data.created_at)}`
            : `Raised ${date(data.created_at)}`
        }
        actions={
          <>
            {data.status === 'DRAFT' ? (
              <Button variant="primary" loading={busy} onClick={() => setStatus('ORDERED')}>
                Place order
              </Button>
            ) : null}
            {['ORDERED', 'PARTIALLY_RECEIVED'].includes(data.status) ? (
              <Button variant="primary" icon="package" onClick={() => setReceiveOpen(true)}>
                Receive delivery
              </Button>
            ) : null}
            {!['RECEIVED', 'CANCELLED'].includes(data.status) ? (
              <Button variant="dangerGhost" onClick={() => setCancelOpen(true)}>
                Cancel
              </Button>
            ) : null}
          </>
        }
      />

      {data.status === 'DRAFT' ? (
        <div className="alert alert--info" style={{ marginBottom: 'var(--s4)' }}>
          This is a draft. Place the order to record that it has been sent to the supplier — only
          then can a delivery be received against it.
        </div>
      ) : null}
      {data.status === 'PARTIALLY_RECEIVED' ? (
        <div className="alert alert--warn" style={{ marginBottom: 'var(--s4)' }}>
          {number(outstanding)} units are still outstanding on this order.
        </div>
      ) : null}

      <div className="grid grid--sidebar">
        <Card title="Order lines" flush>
          <Table
            columns={[
              {
                key: 'product',
                header: 'Product',
                render: (row) => (
                  <div>
                    <Link to={`/app/products/${row.product_id}`} className="table__primary">
                      {row.product_name}
                    </Link>
                    <div className="table__secondary u-mono">{row.sku}</div>
                  </div>
                ),
              },
              {
                key: 'ordered',
                header: 'Ordered',
                align: 'right',
                render: (row) => (
                  <span className="u-num">
                    {number(row.quantity)} <span className="u-subtle u-xs">{row.unit}</span>
                  </span>
                ),
              },
              {
                key: 'received',
                header: 'Received',
                align: 'right',
                render: (row) => (
                  <span
                    className="u-num"
                    style={{
                      color:
                        row.received_quantity >= row.quantity ? 'var(--success-600)' : undefined,
                    }}
                  >
                    {number(row.received_quantity)}
                  </span>
                ),
              },
              {
                key: 'stock',
                header: 'In stock now',
                align: 'right',
                render: (row) => <span className="u-num u-muted">{number(row.current_stock)}</span>,
              },
              {
                key: 'cost',
                header: 'Unit cost',
                align: 'right',
                render: (row) => <span className="u-num">{currency(row.cost_price)}</span>,
              },
              {
                key: 'total',
                header: 'Line total',
                align: 'right',
                render: (row) => <span className="u-num u-strong">{currency(row.line_total)}</span>,
              },
            ]}
            rows={data.items}
          />
          <div className="card__footer">
            <div className="u-col" style={{ gap: 2, maxWidth: 280, marginLeft: 'auto' }}>
              <div className="cart__row">
                <span>Subtotal</span>
                <span>{currency(data.subtotal)}</span>
              </div>
              {Number(data.tax) > 0 ? (
                <div className="cart__row">
                  <span>Tax</span>
                  <span>{currency(data.tax)}</span>
                </div>
              ) : null}
              <div className="cart__row cart__row--total">
                <span>Total</span>
                <span>{currency(data.total)}</span>
              </div>
            </div>
          </div>
        </Card>

        <div className="u-col u-gap4">
          <Card title="Status">
            <dl className="u-col" style={{ gap: 'var(--s3)' }}>
              <Detail label="Status" value={<OrderStatusBadge status={data.status} />} />
              <Detail label="Expected" value={date(data.expected_delivery)} />
              <Detail
                label="Progress"
                value={`${number(data.received_count)} of ${number(data.unit_count)} units`}
              />
              {data.received_at ? (
                <Detail label="Received" value={dateTime(data.received_at)} />
              ) : null}
            </dl>
            <div className="progress u-mt4">
              <div
                className="progress__bar"
                style={{
                  width: `${data.unit_count ? (data.received_count / data.unit_count) * 100 : 0}%`,
                  background: data.status === 'RECEIVED' ? 'var(--success-500)' : undefined,
                }}
              />
            </div>
          </Card>

          <Card title="Supplier">
            {data.supplier_id ? (
              <dl className="u-col" style={{ gap: 'var(--s3)' }}>
                <Detail
                  label="Name"
                  value={
                    <Link to={`/app/suppliers/${data.supplier_id}`}>{data.supplier_name}</Link>
                  }
                />
                <Detail label="Contact" value={data.supplier_contact || '—'} />
                <Detail label="Phone" value={data.supplier_phone || '—'} />
              </dl>
            ) : (
              <p className="u-small u-muted">
                No supplier assigned. Assign one to track spend and lead times.
              </p>
            )}
          </Card>

          {data.notes ? (
            <Card title="Notes">
              <p className="u-small u-muted">{data.notes}</p>
            </Card>
          ) : null}
        </div>
      </div>

      <ReceiveModal
        open={receiveOpen}
        order={data}
        onClose={() => setReceiveOpen(false)}
        onReceived={() => {
          setReceiveOpen(false);
          order.reload();
        }}
      />

      <ConfirmDialog
        open={cancelOpen}
        onClose={() => setCancelOpen(false)}
        onConfirm={() => setStatus('CANCELLED')}
        loading={busy}
        destructive
        title={`Cancel ${data.po_number}?`}
        confirmLabel="Cancel order"
        message="The order is kept for your records but can no longer be received. Anything already received stays in stock."
      />
    </div>
  );
}

/**
 * Receiving a delivery.
 *
 * Defaults to "everything outstanding" because that is the usual case, but each
 * line can be trimmed when the supplier shorts the order.
 */
function ReceiveModal({ open, order, onClose, onReceived }) {
  const toast = useToast();
  const [quantities, setQuantities] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const outstanding = (item) => item.quantity - item.received_quantity;

  const value = (item) =>
    quantities[item.id] === undefined ? outstanding(item) : quantities[item.id];

  async function submit() {
    setSaving(true);
    setError(null);
    try {
      const items = order.items
        .map((item) => ({ item_id: item.id, quantity: Number(value(item)) || 0 }))
        .filter((item) => item.quantity > 0);

      const updated = await api.receivePurchaseOrder(order.id, items);
      toast.success(
        updated.status === 'RECEIVED'
          ? `${order.po_number} fully received — stock updated`
          : `Partial delivery recorded for ${order.po_number}`,
      );
      setQuantities({});
      onReceived();
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
      size="wide"
      title={`Receive ${order.po_number}`}
      subtitle="Stock rises and the ledger records where it came from."
      footer={
        <>
          <Button onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} loading={saving}>
            Receive stock
          </Button>
        </>
      }
    >
      <div className="u-col u-gap4">
        {error ? (
          <div className="alert alert--error" role="alert">
            {error}
          </div>
        ) : null}

        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th className="is-right">Outstanding</th>
                <th className="is-right">Receiving now</th>
              </tr>
            </thead>
            <tbody>
              {order.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <div className="table__primary">{item.product_name}</div>
                    <div className="table__secondary u-mono">{item.sku}</div>
                  </td>
                  <td className="is-right u-num">{number(outstanding(item))}</td>
                  <td className="is-right">
                    <input
                      type="number"
                      min="0"
                      max={outstanding(item)}
                      className="input u-right"
                      style={{ width: 100, marginLeft: 'auto' }}
                      value={value(item)}
                      aria-label={`Quantity received for ${item.product_name}`}
                      onChange={(event) =>
                        setQuantities({
                          ...quantities,
                          [item.id]: Math.max(
                            0,
                            Math.min(Number(event.target.value) || 0, outstanding(item)),
                          ),
                        })
                      }
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="u-xs u-muted">
          Receiving also updates each product's cost price to the price on this order — the most
          recent evidence of what it actually costs you.
        </p>
      </div>
    </Modal>
  );
}

function Detail({ label, value }) {
  return (
    <div className="u-row-between">
      <dt className="u-xs u-muted">{label}</dt>
      <dd className="u-small" style={{ margin: 0, textAlign: 'right' }}>
        {value}
      </dd>
    </div>
  );
}
