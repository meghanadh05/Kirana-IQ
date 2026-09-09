/** Colour-coded stockout risk level. */
export default function RiskBadge({ level }) {
  return <span className={`badge badge--${level.toLowerCase()}`}>{level}</span>;
}
