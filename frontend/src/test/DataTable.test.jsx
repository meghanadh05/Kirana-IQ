import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import DataTable from '../components/DataTable.jsx';
import RiskBadge from '../components/RiskBadge.jsx';

const columns = [
  { key: 'sku', label: 'SKU' },
  { key: 'units', label: 'Units', align: 'right' },
];
const rows = [
  { id: 1, sku: 'DRY-001', units: 12 },
  { id: 2, sku: 'SNK-002', units: 7 },
];

describe('DataTable', () => {
  it('renders a row per record', () => {
    const { container } = render(<DataTable columns={columns} rows={rows} />);
    expect(container.querySelectorAll('tbody tr')).toHaveLength(2);
  });

  it('shows the empty state instead of a bare table', () => {
    render(<DataTable columns={columns} rows={[]} empty="Nothing here." />);
    expect(screen.getByText('Nothing here.')).toBeInTheDocument();
  });

  it('treats a null row list as empty', () => {
    const { container } = render(<DataTable columns={columns} rows={null} />);
    expect(container.querySelector('table')).toBeNull();
  });

  it('uses a custom cell renderer when given one', () => {
    const custom = [{ key: 'risk', label: 'Risk', render: (row) => <b>{row.sku}!</b> }];
    render(<DataTable columns={custom} rows={rows} />);
    expect(screen.getByText('DRY-001!')).toBeInTheDocument();
  });

  it('right-aligns columns that ask for it', () => {
    const { container } = render(<DataTable columns={columns} rows={rows} />);
    const headers = [...container.querySelectorAll('th')];
    expect(headers[0].className).not.toContain('right');
    expect(headers[1].className).toContain('right');
  });

  it('supports a custom row key', () => {
    const custom = [{ product_id: 9, sku: 'X' }];
    const { container } = render(
      <DataTable columns={columns} rows={custom} rowKey={(row) => row.product_id} />
    );
    expect(container.querySelectorAll('tbody tr')).toHaveLength(1);
  });
});

describe('RiskBadge', () => {
  it.each(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'])('styles %s distinctly', (level) => {
    const { container } = render(<RiskBadge level={level} />);
    expect(container.firstChild.className).toBe(`badge badge--${level.toLowerCase()}`);
  });
});
