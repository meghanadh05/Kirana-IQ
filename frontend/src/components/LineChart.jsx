const GRID_LINES = 4;
const NICE_STEPS = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 7.5, 8, 10];

/**
 * Choose a round gridline step so labels read 0/250/500/750/1000 rather than
 * 0/213/425/638/850. Picks the smallest "nice" step whose four intervals still
 * cover the data.
 */
function niceStep(value) {
  const target = value / GRID_LINES;
  const magnitude = Math.pow(10, Math.floor(Math.log10(target)));
  for (const multiple of NICE_STEPS) {
    const candidate = multiple * magnitude;
    if (candidate >= target) return candidate;
  }
  return 10 * magnitude;
}

const formatTick = (value) => (Number.isInteger(value) ? value : value.toFixed(1));

/**
 * Small multi-series line chart drawn as inline SVG.
 *
 * Hand-rolled rather than pulling in a charting library: the project needs one
 * chart type, and a dependency would be more code than this file.
 *
 * `series` is [{ name, colour, dashed, points: [{ label, value }] }]. Every
 * series shares one x axis, so points are indexed positionally.
 */
export default function LineChart({ series, height = 260, yLabel = 'Units' }) {
  const populated = series.filter((s) => s.points.length > 0);
  if (!populated.length) return null;

  const width = 720;
  const padding = { top: 16, right: 16, bottom: 34, left: 44 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  // The x axis must span every series' furthest position, offsets included.
  // Sizing it to the longest series alone pushes an offset series off the edge.
  const span = Math.max(...populated.map((s) => (s.offset ?? 0) + s.points.length));
  const maxValue = Math.max(...populated.flatMap((s) => s.points.map((p) => p.value)), 1);
  const step = niceStep(maxValue);
  const axisMax = step * GRID_LINES;

  const x = (index) => padding.left + (span === 1 ? plotWidth / 2 : (index / (span - 1)) * plotWidth);
  const y = (value) => padding.top + plotHeight - (value / axisMax) * plotHeight;

  const ticks = Array.from({ length: GRID_LINES + 1 }, (_, index) => index * step);

  // One label slot per x position, filled from whichever series covers it.
  const labels = new Array(span).fill(null);
  populated.forEach((line) => {
    line.points.forEach((point, index) => {
      labels[(line.offset ?? 0) + index] = point.label;
    });
  });
  const labelStride = Math.max(1, Math.ceil(span / 8));

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${yLabel} over time`}>
        {ticks.map((tick) => (
          <g key={tick}>
            <line className="chart__grid" x1={padding.left} x2={width - padding.right} y1={y(tick)} y2={y(tick)} />
            <text className="chart__axis" x={padding.left - 8} y={y(tick) + 4} textAnchor="end">
              {formatTick(tick)}
            </text>
          </g>
        ))}

        {labels.map((label, index) =>
          label && index % labelStride === 0 ? (
            <text key={`${label}-${index}`} className="chart__axis" x={x(index)} y={height - 12} textAnchor="middle">
              {label}
            </text>
          ) : null
        )}

        {populated.map((line) => (
          <polyline
            key={line.name}
            className="chart__line"
            fill="none"
            stroke={line.colour}
            strokeDasharray={line.dashed ? '5 4' : undefined}
            points={line.points
              .map((point, index) => `${x((line.offset ?? 0) + index)},${y(point.value)}`)
              .join(' ')}
          />
        ))}
      </svg>

      <div className="chart__legend">
        {populated.map((line) => (
          <span key={line.name} className="chart__legend-item">
            <span className="chart__swatch" style={{ background: line.colour, opacity: line.dashed ? 0.6 : 1 }} />
            {line.name}
          </span>
        ))}
      </div>
    </div>
  );
}
