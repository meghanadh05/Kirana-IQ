import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AdjustmentModal from '../pages/inventory/AdjustmentModal.jsx';
import Inventory from '../pages/inventory/Inventory.jsx';
import { renderWithProviders, renderWithRouter } from './helpers.jsx';
import * as api from '../services/api.js';

vi.mock('../services/api.js', async () => {
  const actual = await vi.importActual('../services/api.js');
  return {
    ...actual,
    getStockPosition: vi.fn(),
    createAdjustment: vi.fn(),
    listProducts: vi.fn(),
    getMe: vi.fn(),
    setUnauthorizedHandler: vi.fn(),
  };
});

function stockRow(overrides = {}) {
  return {
    product_id: 1,
    sku: 'DRY-001',
    name: 'Amul Milk 1L',
    category: 'Dairy',
    unit: 'piece',
    current_stock: 40,
    reorder_level: 10,
    lead_time_days: 2,
    cost_price: 27,
    selling_price: 33,
    stock_value: 1080,
    stock_status: 'OK',
    last_movement_at: '2026-09-09T10:00:00Z',
    ...overrides,
  };
}

const position = {
  products: [
    stockRow(),
    stockRow({ product_id: 2, name: 'Parle-G', sku: 'SNK-001', current_stock: 4, stock_status: 'LOW', stock_value: 108 }),
    stockRow({ product_id: 3, name: 'Sold Out', sku: 'SNK-002', current_stock: 0, stock_status: 'OUT_OF_STOCK', stock_value: 0 }),
  ],
  total_products: 3,
  out_of_stock: 1,
  low_stock: 1,
  inventory_cost_value: 1188,
  inventory_retail_value: 1452,
};

describe('Inventory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('kiranaiq.token', 'test-token');
    localStorage.setItem('kiranaiq.store', '1');
    api.getStockPosition.mockResolvedValue(position);
    api.getMe.mockResolvedValue({
      user: { id: 1, full_name: 'Owner', email: 'o@example.com', is_active: true },
      stores: [{ id: 1, name: 'Store', role: 'OWNER', onboarding_completed: true }],
    });
  });

  it('shows every product with its stock status', async () => {
    renderWithProviders(<Inventory />);
    await screen.findByText('Amul Milk 1L');

    const table = screen.getByRole('table');
    expect(within(table).getByText('In stock')).toBeInTheDocument();
    expect(within(table).getByText('Low')).toBeInTheDocument();
    expect(within(table).getByText('Out of stock')).toBeInTheDocument();
  });

  it('reports the inventory valuation at cost and at retail', async () => {
    renderWithProviders(<Inventory />);
    await screen.findByText('Amul Milk 1L');

    expect(screen.getByText('₹1,188')).toBeInTheDocument();
    expect(screen.getByText(/retail ₹1,452/)).toBeInTheDocument();
  });

  it('filters to low stock only', async () => {
    renderWithProviders(<Inventory />);
    await screen.findByText('Amul Milk 1L');

    await userEvent.click(screen.getByRole('button', { name: /low stock/i }));

    expect(screen.getByText('Parle-G')).toBeInTheDocument();
    expect(screen.queryByText('Amul Milk 1L')).not.toBeInTheDocument();
  });

  it('filters by search term', async () => {
    renderWithProviders(<Inventory />);
    await screen.findByText('Amul Milk 1L');

    await userEvent.type(screen.getByLabelText(/search inventory/i), 'parle');

    expect(screen.getByText('Parle-G')).toBeInTheDocument();
    expect(screen.queryByText('Amul Milk 1L')).not.toBeInTheDocument();
  });

  it('renders without a trained model, because stock is a fact not a forecast', async () => {
    renderWithProviders(<Inventory />);
    expect(await screen.findByText('Amul Milk 1L')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});

describe('Stock adjustment', () => {
  const product = {
    product_id: 1,
    name: 'Amul Milk 1L',
    sku: 'DRY-001',
    unit: 'piece',
    current_stock: 40,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    api.listProducts.mockResolvedValue({ items: [], total: 0, limit: 300, offset: 0 });
  });

  it('sends a negative change when removing stock', async () => {
    api.createAdjustment.mockResolvedValue({ id: 1, quantity_after: 35 });
    const onSaved = vi.fn();

    renderWithRouter(
      <AdjustmentModal open product={product} onClose={() => {}} onSaved={onSaved} />,
    );

    await userEvent.type(screen.getByLabelText(/quantity/i), '5');
    await userEvent.click(screen.getByRole('button', { name: /apply adjustment/i }));

    await waitFor(() =>
      expect(api.createAdjustment).toHaveBeenCalledWith(
        expect.objectContaining({ product_id: 1, quantity_change: -5, reason: 'DAMAGE' }),
      ),
    );
    expect(onSaved).toHaveBeenCalled();
  });

  it('sends a positive change when adding stock', async () => {
    api.createAdjustment.mockResolvedValue({ id: 1 });
    renderWithRouter(<AdjustmentModal open product={product} onClose={() => {}} onSaved={() => {}} />);

    await userEvent.selectOptions(screen.getByLabelText(/direction/i), 'increase');
    await userEvent.type(screen.getByLabelText(/quantity/i), '5');
    await userEvent.click(screen.getByRole('button', { name: /apply adjustment/i }));

    await waitFor(() =>
      expect(api.createAdjustment).toHaveBeenCalledWith(
        expect.objectContaining({ quantity_change: 5 }),
      ),
    );
  });

  it('picks the direction implied by the reason', async () => {
    renderWithRouter(<AdjustmentModal open product={product} onClose={() => {}} onSaved={() => {}} />);

    await userEvent.selectOptions(screen.getByLabelText(/reason/i), 'RETURN');
    expect(screen.getByLabelText(/direction/i)).toHaveValue('increase');

    await userEvent.selectOptions(screen.getByLabelText(/reason/i), 'EXPIRED');
    expect(screen.getByLabelText(/direction/i)).toHaveValue('decrease');
  });

  it('previews the resulting stock level', async () => {
    renderWithRouter(<AdjustmentModal open product={product} onClose={() => {}} onSaved={() => {}} />);

    await userEvent.type(screen.getByLabelText(/quantity/i), '5');
    expect(screen.getByText('Stock becomes 35.')).toBeInTheDocument();
  });

  it('blocks an adjustment that would take stock below zero', async () => {
    renderWithRouter(<AdjustmentModal open product={product} onClose={() => {}} onSaved={() => {}} />);

    await userEvent.type(screen.getByLabelText(/quantity/i), '500');

    expect(screen.getByText(/would take stock below zero/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /apply adjustment/i })).toBeDisabled();
    expect(api.createAdjustment).not.toHaveBeenCalled();
  });

  it('requires a quantity', () => {
    renderWithRouter(<AdjustmentModal open product={product} onClose={() => {}} onSaved={() => {}} />);
    expect(screen.getByRole('button', { name: /apply adjustment/i })).toBeDisabled();
  });

  it('surfaces a rejection from the API', async () => {
    api.createAdjustment.mockRejectedValue(new Error('Insufficient stock: 40 on hand'));
    renderWithRouter(<AdjustmentModal open product={product} onClose={() => {}} onSaved={() => {}} />);

    await userEvent.type(screen.getByLabelText(/quantity/i), '5');
    await userEvent.click(screen.getByRole('button', { name: /apply adjustment/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Insufficient stock');
  });
});
