import { currency, dateTime } from '../../lib/format.js';

/**
 * Printable receipt.
 *
 * Sized for an 80mm thermal roll and rendered in a monospace face, so what
 * prints matches what is on screen. The print stylesheet hides everything else
 * on the page rather than opening a second window.
 */
export default function Receipt({ sale, store }) {
  if (!sale) return null;

  const line = (label, value, strong = false) => (
    <div className={`receipt__row${strong ? ' receipt__row--total' : ''}`}>
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );

  return (
    <div className="receipt">
      <div className="receipt__center">
        <div className="receipt__store">{store?.name || 'Store'}</div>
        {store?.address ? <div>{store.address}</div> : null}
        {store?.city ? (
          <div>
            {store.city}
            {store.state ? `, ${store.state}` : ''} {store.pin_code || ''}
          </div>
        ) : null}
        {store?.phone ? <div>Ph: {store.phone}</div> : null}
        {store?.gst_number ? <div>GSTIN: {store.gst_number}</div> : null}
      </div>

      <div className="receipt__rule" />

      {line('Invoice', sale.invoice_number)}
      {line('Date', dateTime(sale.created_at))}
      {sale.customer_name ? line('Customer', sale.customer_name) : null}
      {sale.customer_phone ? line('Phone', sale.customer_phone) : null}

      <div className="receipt__rule" />

      {sale.items?.map((item) => (
        <div className="receipt__item" key={item.id}>
          <div className="receipt__item-name">{item.product_name}</div>
          <div className="receipt__row">
            <span>
              {item.quantity} × {currency(item.unit_price)}
            </span>
            <span>{currency(item.line_total)}</span>
          </div>
        </div>
      ))}

      <div className="receipt__rule" />

      {line('Subtotal', currency(sale.subtotal))}
      {Number(sale.tax) > 0 ? line('Tax', currency(sale.tax)) : null}
      {Number(sale.discount) > 0 ? line('Discount', `-${currency(sale.discount)}`) : null}
      {line('TOTAL', currency(sale.total), true)}

      <div className="receipt__rule" />

      {line('Paid by', sale.payment_method)}
      {line('Received', currency(sale.amount_received))}
      {Number(sale.change_due) > 0 ? line('Change', currency(sale.change_due)) : null}

      <div className="receipt__rule" />

      <div className="receipt__center">
        {sale.status !== 'COMPLETED' ? (
          <div style={{ fontWeight: 700 }}>** {sale.status} **</div>
        ) : null}
        <div>Thank you for shopping with us!</div>
        <div style={{ marginTop: 4, fontSize: 9 }}>Billed with Kirana-IQ</div>
      </div>
    </div>
  );
}
