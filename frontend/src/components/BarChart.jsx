/** Horizontal bar chart for category and product comparisons. */
export default function BarChart({ rows, valueKey = 'value', labelKey = 'label', format = (v) => v }) {
  if (!rows?.length) return null;
  const max = Math.max(...rows.map((row) => Math.abs(row[valueKey])), 1);

  return (
    <ul className="bars">
      {rows.map((row) => (
        <li key={row[labelKey]} className="bars__row">
          <span className="bars__label">{row[labelKey]}</span>
          <span className="bars__track">
            <span
              className="bars__fill"
              style={{ width: `${(Math.abs(row[valueKey]) / max) * 100}%` }}
            />
          </span>
          <span className="bars__value">{format(row[valueKey])}</span>
        </li>
      ))}
    </ul>
  );
}
