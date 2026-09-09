import { useId, useMemo, useState } from 'react';

/**
 * A dependency-free SVG line chart.
 *
 * Handles one or two series (observed and forecast) and draws the forecast
 * dashed, so a prediction is never mistaken for a measurement.
 */
export default function LineChart({
  series = [],
  height = 200,
  formatValue = (value) => value,
  formatLabel = (label) => label,
  showArea = true,
}) {
  const gradientId = useId();
  const [hover, setHover] = useState(null);

  const width = 720;
  const padding = { top: 12, right: 12, bottom: 24, left: 46 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  const model = useMemo(() => {
    const points = series.flatMap((line) => line.points);
    if (points.length === 0) return null;

    const labels = [];
    points.forEach((point) => {
      if (!labels.includes(point.label)) labels.push(point.label);
    });

    const values = points.map((point) => point.value);
    const maxValue = Math.max(...values, 0);
    const minValue = Math.min(...values, 0);
    // A flat zero series would otherwise divide by zero and collapse the plot.
    const span = maxValue - minValue || 1;

    const x = (label) =>
      labels.length === 1
        ? padding.left + plotWidth / 2
        : padding.left + (labels.indexOf(label) / (labels.length - 1)) * plotWidth;
    const y = (value) => padding.top + plotHeight - ((value - minValue) / span) * plotHeight;

    return { labels, maxValue, minValue, span, x, y };
  }, [series, plotWidth, plotHeight, padding.left, padding.top]);

  if (!model) {
    return (
      <div className="u-center u-muted u-small" style={{ padding: '3rem 1rem' }}>
        No data for this period
      </div>
    );
  }

  const { labels, maxValue, minValue, x, y } = model;
  const ticks = [minValue, minValue + (maxValue - minValue) / 2, maxValue];

  return (
    <div style={{ position: 'relative' }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: '100%', height: 'auto', display: 'block', overflow: 'visible' }}
        role="img"
        aria-label={series.map((line) => line.name).join(' and ')}
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent-500)" stopOpacity="0.16" />
            <stop offset="100%" stopColor="var(--accent-500)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {ticks.map((tick, index) => (
          <g key={index}>
            <line
              x1={padding.left} x2={width - padding.right}
              y1={y(tick)} y2={y(tick)}
              stroke="var(--grey-100)" strokeWidth="1"
            />
            <text
              x={padding.left - 8} y={y(tick) + 3}
              textAnchor="end" fontSize="10" fill="var(--text-subtle)"
            >
              {formatValue(Math.round(tick))}
            </text>
          </g>
        ))}

        {series.map((line, index) => {
          const path = line.points
            .map((point, pointIndex) => `${pointIndex === 0 ? 'M' : 'L'}${x(point.label)},${y(point.value)}`)
            .join(' ');
          const colour = line.color || 'var(--accent-500)';

          return (
            <g key={line.name}>
              {showArea && !line.dashed && line.points.length > 1 ? (
                <path
                  d={`${path} L${x(line.points[line.points.length - 1].label)},${padding.top + plotHeight} L${x(line.points[0].label)},${padding.top + plotHeight} Z`}
                  fill={`url(#${gradientId})`}
                />
              ) : null}
              <path
                d={path}
                fill="none"
                stroke={colour}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={line.dashed ? '5 4' : undefined}
              />
              {line.points.length === 1 ? (
                <circle cx={x(line.points[0].label)} cy={y(line.points[0].value)} r="3" fill={colour} />
              ) : null}
            </g>
          );
        })}

        {/* One hit area per label, so hovering anywhere in a column works. */}
        {labels.map((label) => (
          <rect
            key={label}
            x={x(label) - plotWidth / Math.max(labels.length - 1, 1) / 2}
            y={padding.top}
            width={plotWidth / Math.max(labels.length - 1, 1)}
            height={plotHeight}
            fill="transparent"
            onMouseEnter={() => setHover(label)}
          />
        ))}

        {hover ? (
          <line
            x1={x(hover)} x2={x(hover)}
            y1={padding.top} y2={padding.top + plotHeight}
            stroke="var(--grey-400)" strokeWidth="1" strokeDasharray="3 3"
          />
        ) : null}

        {labels
          .filter((_, index) => index % Math.ceil(labels.length / 7) === 0)
          .map((label) => (
            <text
              key={label}
              x={x(label)} y={height - 6}
              textAnchor="middle" fontSize="10" fill="var(--text-subtle)"
            >
              {formatLabel(label)}
            </text>
          ))}
      </svg>

      {hover ? (
        <div
          style={{
            position: 'absolute',
            left: `${(x(hover) / width) * 100}%`,
            top: 0,
            transform: 'translateX(-50%)',
            pointerEvents: 'none',
            background: 'var(--grey-900)',
            color: 'var(--grey-0)',
            padding: '6px 8px',
            borderRadius: 'var(--radius)',
            fontSize: 'var(--text-xs)',
            whiteSpace: 'nowrap',
            zIndex: 2,
          }}
        >
          <div style={{ fontWeight: 600 }}>{formatLabel(hover)}</div>
          {series.map((line) => {
            const point = line.points.find((candidate) => candidate.label === hover);
            if (!point) return null;
            return (
              <div key={line.name} style={{ opacity: 0.85 }}>
                {line.name}: {formatValue(point.value)}
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
