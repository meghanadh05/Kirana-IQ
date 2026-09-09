import { titleCase } from '../../lib/format.js';

const TONES = {
  neutral: 'badge--neutral',
  success: 'badge--success',
  warn: 'badge--warn',
  danger: 'badge--danger',
  info: 'badge--info',
  accent: 'badge--accent',
};

export default function Badge({ tone = 'neutral', dot = false, children }) {
  return (
    <span className={`badge ${TONES[tone] || TONES.neutral}${dot ? ' badge--dot' : ''}`}>
      {children}
    </span>
  );
}

const RISK_TONE = { CRITICAL: 'danger', HIGH: 'warn', MEDIUM: 'info', LOW: 'success' };

/** Stockout risk from the forecasting service. */
export function RiskBadge({ risk }) {
  return (
    <Badge tone={RISK_TONE[risk] || 'neutral'} dot>
      {titleCase(risk)}
    </Badge>
  );
}

const STOCK_TONE = { OUT_OF_STOCK: 'danger', LOW: 'warn', OK: 'success' };
const STOCK_LABEL = { OUT_OF_STOCK: 'Out of stock', LOW: 'Low', OK: 'In stock' };

export function StockBadge({ status }) {
  return <Badge tone={STOCK_TONE[status] || 'neutral'} dot>{STOCK_LABEL[status] || status}</Badge>;
}

const ORDER_TONE = {
  DRAFT: 'neutral',
  ORDERED: 'info',
  PARTIALLY_RECEIVED: 'warn',
  RECEIVED: 'success',
  CANCELLED: 'danger',
};

export function OrderStatusBadge({ status }) {
  return <Badge tone={ORDER_TONE[status] || 'neutral'}>{titleCase(status)}</Badge>;
}

const SALE_TONE = { COMPLETED: 'success', CANCELLED: 'danger', RETURNED: 'warn' };

export function SaleStatusBadge({ status }) {
  return <Badge tone={SALE_TONE[status] || 'neutral'}>{titleCase(status)}</Badge>;
}
