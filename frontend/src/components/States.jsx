/** Shared loading / error / empty placeholders. */

export function Loading({ label = 'Loading…' }) {
  return <div className="state state--loading">{label}</div>;
}

export function ErrorState({ error, onRetry }) {
  const notTrained = error?.status === 503;
  return (
    <div className="state state--error">
      <strong>{notTrained ? 'No model trained yet' : 'Could not load data'}</strong>
      <span>{error?.message}</span>
      {notTrained && <span>Train one from the Dashboard, or run “python -m app.ml.train_model”.</span>}
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function Empty({ label = 'Nothing to show.' }) {
  return <div className="state state--empty">{label}</div>;
}
