import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import LineChart from '../components/LineChart.jsx';

const points = (values, prefix = 'd') =>
  values.map((value, index) => ({ label: `${prefix}${index}`, value }));

const history = { name: 'Actual', colour: '#000', points: points([10, 20, 30, 40]) };
const forecast = {
  name: 'Predicted',
  colour: '#f00',
  dashed: true,
  offset: 3,
  points: points([40, 45, 50], 'f'),
};

const polylines = (container) => [...container.querySelectorAll('polyline')];
const xs = (polyline) =>
  polyline.getAttribute('points').split(' ').map((pair) => Number(pair.split(',')[0]));

describe('LineChart', () => {
  it('renders nothing when every series is empty', () => {
    const { container } = render(<LineChart series={[{ name: 'a', colour: '#000', points: [] }]} />);
    expect(container.querySelector('svg')).toBeNull();
  });

  it('draws one line per populated series', () => {
    const { container } = render(<LineChart series={[history, forecast]} />);
    expect(polylines(container)).toHaveLength(2);
  });

  /**
   * Regression: the x axis used to be scaled to the longest series, so an
   * offset series was drawn past the right edge and never appeared.
   */
  it('keeps an offset series inside the plot area', () => {
    const { container } = render(<LineChart series={[history, forecast]} />);
    const viewBoxWidth = Number(container.querySelector('svg').getAttribute('viewBox').split(' ')[2]);

    const forecastXs = xs(polylines(container)[1]);
    expect(Math.max(...forecastXs)).toBeLessThanOrEqual(viewBoxWidth);
    expect(Math.min(...forecastXs)).toBeGreaterThanOrEqual(0);
  });

  it('ends the furthest series at the right edge of the plot', () => {
    const { container } = render(<LineChart series={[history, forecast]} />);
    const historyEnd = Math.max(...xs(polylines(container)[0]));
    const forecastEnd = Math.max(...xs(polylines(container)[1]));
    expect(forecastEnd).toBeGreaterThan(historyEnd);
  });

  it('starts the offset series where the previous one ends', () => {
    const { container } = render(<LineChart series={[history, forecast]} />);
    const historyXs = xs(polylines(container)[0]);
    const forecastXs = xs(polylines(container)[1]);
    // offset 3 lines up with the fourth (last) history point.
    expect(forecastXs[0]).toBeCloseTo(historyXs[3], 5);
  });

  it('labels the y axis with round numbers', () => {
    const { container } = render(<LineChart series={[{ ...history, points: points([0, 213, 425, 850]) }]} />);
    const labels = [...container.querySelectorAll('text')]
      .map((node) => node.textContent)
      .filter((text) => /^[\d.]+$/.test(text))
      .map(Number);

    // Every tick should be a multiple of the smallest non-zero tick.
    const step = Math.min(...labels.filter((value) => value > 0));
    for (const label of labels) {
      expect(label % step).toBeCloseTo(0, 5);
    }
  });

  it('scales the axis above the largest value', () => {
    const { container } = render(<LineChart series={[{ ...history, points: points([0, 46]) }]} />);
    const labels = [...container.querySelectorAll('text')]
      .map((node) => Number(node.textContent))
      .filter((value) => Number.isFinite(value));
    expect(Math.max(...labels)).toBeGreaterThanOrEqual(46);
  });

  it('handles a single data point without dividing by zero', () => {
    const { container } = render(<LineChart series={[{ ...history, points: points([5]) }]} />);
    expect(xs(polylines(container)[0]).every(Number.isFinite)).toBe(true);
  });

  it('renders a legend entry per series', () => {
    const { container } = render(<LineChart series={[history, forecast]} />);
    expect(container.querySelectorAll('.chart__legend-item')).toHaveLength(2);
  });

  it('dashes only the series marked dashed', () => {
    const { container } = render(<LineChart series={[history, forecast]} />);
    const [actual, predicted] = polylines(container);
    expect(actual.getAttribute('stroke-dasharray')).toBeNull();
    expect(predicted.getAttribute('stroke-dasharray')).not.toBeNull();
  });
});
