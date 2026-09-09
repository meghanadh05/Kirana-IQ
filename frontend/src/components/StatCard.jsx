/** A single headline number, optionally emphasised by tone. */
export default function StatCard({ label, value, hint, tone = 'neutral' }) {
  return (
    <div className={`stat stat--${tone}`}>
      <span className="stat__label">{label}</span>
      <span className="stat__value">{value}</span>
      {hint && <span className="stat__hint">{hint}</span>}
    </div>
  );
}
