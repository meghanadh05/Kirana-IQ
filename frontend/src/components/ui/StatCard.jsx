import Sparkline from '../charts/Sparkline.jsx';
import Icon from './Icon.jsx';

/**
 * A headline figure.
 *
 * `delta` is only rendered when a comparison actually exists — showing "0%"
 * against a period with no data would be a claim the numbers do not support.
 */
export default function StatCard({
  label,
  value,
  meta,
  delta,
  deltaLabel,
  tone,
  sparkline,
  icon,
}) {
  const hasDelta = delta !== null && delta !== undefined && Number.isFinite(delta);
  const direction = hasDelta ? (delta >= 0 ? 'up' : 'down') : null;

  return (
    <div className={`stat${tone ? ` stat--${tone}` : ''}`}>
      <div className="u-row-between">
        <span className="stat__label">{label}</span>
        {icon ? <Icon name={icon} size={14} className="u-subtle" /> : null}
      </div>
      <div className="u-row-between">
        <span className="stat__value">{value}</span>
        {sparkline ? <Sparkline values={sparkline} /> : null}
      </div>
      {hasDelta || meta ? (
        <div className="stat__meta">
          {hasDelta ? (
            <span className={`stat__delta stat__delta--${direction}`}>
              {direction === 'up' ? '↑' : '↓'} {Math.abs(delta).toFixed(1)}%
            </span>
          ) : null}
          {hasDelta && (meta || deltaLabel) ? ' ' : null}
          {deltaLabel || meta}
        </div>
      ) : null}
    </div>
  );
}
