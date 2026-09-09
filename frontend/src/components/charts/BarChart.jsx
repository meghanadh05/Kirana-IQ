/** A compact horizontal bar list — for category and product comparisons. */
export default function BarChart({ data = [], formatValue = (value) => value, tone = 'accent' }) {
  if (data.length === 0) {
    return <div className="u-center u-muted u-small" style={{ padding: '2rem' }}>No data</div>;
  }

  const max = Math.max(...data.map((row) => Math.abs(row.value)), 1);
  const colour = tone === 'accent' ? 'var(--accent-500)' : 'var(--grey-400)';

  return (
    <div className="u-col" style={{ gap: 'var(--s3)' }}>
      {data.map((row) => (
        <div key={row.label}>
          <div className="u-row-between u-small" style={{ marginBottom: 3 }}>
            <span className="u-truncate">{row.label}</span>
            <span className="u-num u-strong u-nowrap">{formatValue(row.value)}</span>
          </div>
          <div className="progress">
            <div
              className="progress__bar"
              style={{
                width: `${(Math.abs(row.value) / max) * 100}%`,
                background: row.color || colour,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
