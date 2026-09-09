import Button from './Button.jsx';
import Icon from './Icon.jsx';

/**
 * Loading, empty and error states.
 *
 * Every data-driven screen renders one of these rather than a blank area, so
 * "nothing here" is always distinguishable from "still loading" and "broken".
 */

export function Loading({ label = 'Loading…', inline = false }) {
  return (
    <div className={`state${inline ? ' state--inline' : ''}`} role="status" aria-live="polite">
      <div className="skeleton" style={{ width: 120, height: 10 }} />
      <div className="skeleton" style={{ width: 200, height: 10 }} />
      <span className="u-visually-hidden">{label}</span>
    </div>
  );
}

/** Placeholder rows shaped like the table they stand in for. */
export function TableSkeleton({ rows = 6, columns = 5 }) {
  return (
    <table className="table" aria-hidden="true">
      <tbody>
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <tr key={rowIndex}>
            {Array.from({ length: columns }).map((__, columnIndex) => (
              <td key={columnIndex}>
                <div
                  className="skeleton"
                  style={{ height: 10, width: columnIndex === 0 ? '60%' : '40%' }}
                />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function CardSkeleton({ height = 120 }) {
  return <div className="skeleton" style={{ height, borderRadius: 'var(--radius-lg)' }} />;
}

export function EmptyState({
  icon = 'inbox',
  title,
  message,
  actions = null,
  inline = false,
}) {
  return (
    <div className={`state${inline ? ' state--inline' : ''}`}>
      <div className="state__icon">
        <Icon name={icon} size={20} />
      </div>
      <div className="state__title">{title}</div>
      {message ? <p className="state__message">{message}</p> : null}
      {actions ? <div className="state__actions">{actions}</div> : null}
    </div>
  );
}

/**
 * Error state.
 *
 * Shows the API's own message — services return sentences a shopkeeper can act
 * on — and never a stack trace. Retry is always offered, because a failed fetch
 * is usually transient.
 */
export function ErrorState({ error, onRetry, inline = false }) {
  const status = error?.status;
  const message =
    status === 503
      ? 'Forecasts need a trained model. Train one from the Forecasting page.'
      : error?.message || 'Something went wrong loading this data.';

  return (
    <div className={`state state--error${inline ? ' state--inline' : ''}`} role="alert">
      <div className="state__icon">
        <Icon name="warning" size={20} />
      </div>
      <div className="state__title">
        {status === 503 ? 'Not available yet' : "Couldn't load this"}
      </div>
      <p className="state__message">{message}</p>
      {onRetry ? (
        <div className="state__actions">
          <Button icon="refresh" onClick={onRetry}>
            Try again
          </Button>
        </div>
      ) : null}
    </div>
  );
}

/**
 * The standard loading → error → empty → content ladder.
 *
 * Screens pass their `useApi` result straight in, which is what stops each page
 * inventing its own idea of what an empty table looks like.
 */
export function AsyncSection({
  loading,
  error,
  onRetry,
  isEmpty = false,
  empty = null,
  skeleton = null,
  children,
}) {
  if (loading) return skeleton || <Loading inline />;
  if (error) return <ErrorState error={error} onRetry={onRetry} inline />;
  if (isEmpty) return empty;
  return children;
}
