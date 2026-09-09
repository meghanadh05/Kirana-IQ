import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';

import Receipt from './Receipt.jsx';
import PageHeader from '../../components/layout/PageHeader.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Modal, { ConfirmDialog } from '../../components/ui/Modal.jsx';
import Table from '../../components/ui/Table.jsx';
import { SaleStatusBadge } from '../../components/ui/Badge.jsx';
import { ErrorState, Loading } from '../../components/ui/States.jsx';
import { useAuth, useCan } from '../../context/AuthContext.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { currency, dateTime, titleCase } from '../../lib/format.js';

export default function SaleDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { store } = useAuth();
  const canManage = useCan('MANAGER');
  const [searchParams, setSearchParams] = useSearchParams();

  const sale = useApi(() => api.getSale(id), [id]);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  // Arriving straight from checkout opens the receipt automatically.
  useEffect(() => {
    if (searchParams.get('receipt') === '1' && sale.data) {
      setReceiptOpen(true);
      searchParams.delete('receipt');
      setSearchParams(searchParams, { replace: true });
    }
  }, [sale.data, searchParams, setSearchParams]);

  if (sale.loading) return <div className="page"><Loading /></div>;
  if (sale.error) {
    return (
      <div className="page">
        <ErrorState error={sale.error} onRetry={sale.reload} />
      </div>
    );
  }

  const data = sale.data;

  async function cancel() {
    setCancelling(true);
    try {
      await api.cancelSale(data.id, 'Cancelled from sale detail');
      toast.success(`${data.invoice_number} cancelled and stock returned`);
      setCancelOpen(false);
      sale.reload();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setCancelling(false);
    }
  }

  const columns = [
    {
      key: 'product',
      header: 'Product',
      render: (row) => (
        <div>
          <div className="table__primary">{row.product_name}</div>
          <div className="table__secondary u-mono">{row.sku}</div>
        </div>
      ),
    },
    { key: 'qty', header: 'Qty', align: 'right', render: (row) => <span className="u-num">{row.quantity}</span> },
    {
      key: 'price',
      header: 'Unit price',
      align: 'right',
      render: (row) => <span className="u-num">{currency(row.unit_price)}</span>,
    },
    {
      key: 'tax',
      header: 'Tax',
      align: 'right',
      render: (row) => (
        <span className="u-num u-muted">
          {Number(row.tax_rate) > 0 ? `${row.tax_rate}%` : '—'}
        </span>
      ),
    },
    {
      key: 'total',
      header: 'Line total',
      align: 'right',
      render: (row) => <span className="u-num u-strong">{currency(row.line_total)}</span>,
    },
  ];

  return (
    <div className="page">
      <PageHeader
        breadcrumb={[{ label: 'Sales', to: '/app/sales' }, { label: data.invoice_number }]}
        title={data.invoice_number}
        subtitle={`${dateTime(data.created_at)}${data.created_by_name ? ` · billed by ${data.created_by_name}` : ''}`}
        actions={
          <>
            <Button icon="print" onClick={() => setReceiptOpen(true)}>
              Receipt
            </Button>
            {canManage && data.status === 'COMPLETED' ? (
              <Button variant="dangerGhost" onClick={() => setCancelOpen(true)}>
                Cancel sale
              </Button>
            ) : null}
            <Link to="/app/pos">
              <Button variant="primary" icon="pos">
                New sale
              </Button>
            </Link>
          </>
        }
      />

      {data.status !== 'COMPLETED' ? (
        <div className="alert alert--warn" style={{ marginBottom: 'var(--s4)' }}>
          This sale is {data.status.toLowerCase()}. Its stock has been returned to inventory and it
          no longer counts towards demand history.
        </div>
      ) : null}

      <div className="grid grid--sidebar">
        <Card title="Items" flush>
          <Table columns={columns} rows={data.items} />
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
              {Number(data.discount) > 0 ? (
                <div className="cart__row">
                  <span>Discount</span>
                  <span>−{currency(data.discount)}</span>
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
          <Card title="Payment">
            <dl className="u-col" style={{ gap: 'var(--s3)' }}>
              <Detail label="Status" value={<SaleStatusBadge status={data.status} />} />
              <Detail label="Method" value={titleCase(data.payment_method)} />
              <Detail label="Received" value={currency(data.amount_received)} />
              {Number(data.change_due) > 0 ? (
                <Detail label="Change given" value={currency(data.change_due)} />
              ) : null}
              {data.payments?.length > 1 ? (
                <Detail
                  label="Split"
                  value={data.payments
                    .map((payment) => `${titleCase(payment.method)} ${currency(payment.amount)}`)
                    .join(', ')}
                />
              ) : null}
            </dl>
          </Card>

          <Card title="Customer">
            {data.customer_name || data.customer_phone ? (
              <dl className="u-col" style={{ gap: 'var(--s3)' }}>
                <Detail label="Name" value={data.customer_name || '—'} />
                <Detail label="Phone" value={data.customer_phone || '—'} />
                {data.customer_id ? (
                  <Link className="u-small" to={`/app/customers/${data.customer_id}`}>
                    View purchase history
                  </Link>
                ) : null}
              </dl>
            ) : (
              <p className="u-small u-muted">Walk-in customer — no details recorded.</p>
            )}
          </Card>

          <Card title="Margin" subtitle="Revenue net of tax, minus cost of goods.">
            <dl className="u-col" style={{ gap: 'var(--s3)' }}>
              <Detail label="Cost of goods" value={currency(data.cost_total)} />
              <Detail
                label="Gross profit"
                value={
                  <span
                    style={{
                      color: data.gross_profit >= 0 ? 'var(--success-600)' : 'var(--danger-600)',
                      fontWeight: 600,
                    }}
                  >
                    {currency(data.gross_profit)}
                  </span>
                }
              />
            </dl>
          </Card>
        </div>
      </div>

      <Modal
        open={receiptOpen}
        onClose={() => setReceiptOpen(false)}
        title="Receipt"
        subtitle={data.invoice_number}
        footer={
          <>
            <Button onClick={() => navigate('/app/pos')}>New sale</Button>
            <Button variant="primary" icon="print" onClick={() => window.print()}>
              Print receipt
            </Button>
          </>
        }
      >
        <div style={{ background: 'var(--grey-100)', padding: 'var(--s4)', borderRadius: 'var(--radius)' }}>
          <Receipt sale={data} store={store} />
        </div>
      </Modal>

      <ConfirmDialog
        open={cancelOpen}
        onClose={() => setCancelOpen(false)}
        onConfirm={cancel}
        loading={cancelling}
        destructive
        title={`Cancel ${data.invoice_number}?`}
        confirmLabel="Cancel sale"
        message="The invoice is kept for your records, the stock goes back on the shelf, and the sale stops counting towards demand history."
      />
    </div>
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
