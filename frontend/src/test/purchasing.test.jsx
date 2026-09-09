import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import NewPurchase from '../pages/purchasing/NewPurchase.jsx';
import { makeProduct, renderWithProviders } from './helpers.jsx';
import * as api from '../services/api.js';

vi.mock('../services/api.js', async () => {
  const actual = await vi.importActual('../services/api.js');
  return {
    ...actual,
    getReorderSuggestions: vi.fn(),
    listSuppliers: vi.fn(),
    listProducts: vi.fn(),
    createPurchaseOrder: vi.fn(),
    getMe: vi.fn(),
    setUnauthorizedHandler: vi.fn(),
  };
});

const supplier = {
  id: 7,
  name: 'Deccan Beverage Supply',
  default_lead_time_days: 4,
  product_count: 3,
  open_orders: 0,
  total_purchased: 0,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  store_id: 1,
};

const recommendation = {
  product_id: 1,
  sku: 'BEV-001',
  name: 'Coca-Cola 750ml',
  category: 'Beverages',
  unit: 'piece',
  supplier_id: 7,
  cost_price: 32.8,
  current_stock: 12,
  reorder_level: 40,
  lead_time_days: 4,
  expected_7_day_demand: 180,
  average_daily_demand: 25.7,
  stock_cover_days: 0.5,
  risk: 'CRITICAL',
  overstock: false,
  demand_std_dev: 6.2,
  safety_stock: 20,
  target_stock: 200,
  recommended_reorder_quantity: 188,
  estimated_cost: 6166.4,
  reason: 'Only 0.5 days of stock left and the supplier takes 4 days.',
};

const suggestions = {
  total_products: 1,
  groups: [
    {
      supplier_id: 7,
      supplier_name: 'Deccan Beverage Supply',
      expected_delivery: '2026-09-13',
      product_count: 1,
      total_units: 188,
      estimated_cost: 6166.4,
      items: [recommendation],
    },
  ],
};

describe('Purchase order builder', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('kiranaiq.token', 'test-token');
    localStorage.setItem('kiranaiq.store', '1');

    api.getReorderSuggestions.mockResolvedValue(suggestions);
    api.listSuppliers.mockResolvedValue([supplier]);
    api.listProducts.mockResolvedValue({
      items: [makeProduct({ id: 1, name: 'Coca-Cola 750ml', sku: 'BEV-001', cost_price: '32.80', supplier_id: 7 })],
      total: 1,
      limit: 300,
      offset: 0,
    });
    api.getMe.mockResolvedValue({
      user: { id: 1, full_name: 'Owner', email: 'o@example.com', is_active: true },
      stores: [{ id: 1, name: 'Store', role: 'OWNER', onboarding_completed: true }],
    });
  });

  it('shows the reorder recommendation with its reasoning', async () => {
    renderWithProviders(<NewPurchase />);

    expect(await screen.findByText('Deccan Beverage Supply')).toBeInTheDocument();
    // The quantity is emphasised inside the sentence, so match on the element.
    expect(screen.getByText('188')).toBeInTheDocument();
    expect(screen.getByText(/Only 0.5 days of stock left/)).toBeInTheDocument();
  });

  it('starts with no order lines', async () => {
    renderWithProviders(<NewPurchase />);
    expect(await screen.findByText('No lines yet')).toBeInTheDocument();
  });

  it('carries the recommended quantity onto the order', async () => {
    renderWithProviders(<NewPurchase />);
    await userEvent.click(await screen.findByRole('button', { name: /add to order/i }));

    expect(screen.getByLabelText('Quantity for Coca-Cola 750ml')).toHaveValue(188);
    expect(screen.getByLabelText('Unit cost for Coca-Cola 750ml')).toHaveValue(32.8);
  });

  it('lets the buyer overrule the recommended quantity', async () => {
    renderWithProviders(<NewPurchase />);
    await userEvent.click(await screen.findByRole('button', { name: /add to order/i }));

    const quantity = screen.getByLabelText('Quantity for Coca-Cola 750ml');
    await userEvent.clear(quantity);
    await userEvent.type(quantity, '50');

    expect(quantity).toHaveValue(50);
    // Appears twice: once on the line, once in the order subtotal.
    expect(screen.getAllByText('₹1,640.00')).toHaveLength(2);
  });

  it('totals the order from quantity times unit cost', async () => {
    renderWithProviders(<NewPurchase />);
    await userEvent.click(await screen.findByRole('button', { name: /add to order/i }));

    // 188 x 32.80 = 6166.40
    expect(screen.getAllByText('₹6,166.40').length).toBeGreaterThan(0);
  });

  it('removes a line', async () => {
    renderWithProviders(<NewPurchase />);
    await userEvent.click(await screen.findByRole('button', { name: /add to order/i }));
    await userEvent.click(screen.getByLabelText('Remove Coca-Cola 750ml'));

    expect(screen.getByText('No lines yet')).toBeInTheDocument();
  });

  it('cannot be submitted with no lines', async () => {
    renderWithProviders(<NewPurchase />);
    await screen.findByText('No lines yet');

    expect(screen.getByRole('button', { name: /place order/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /save as draft/i })).toBeDisabled();
  });

  it('saves a draft with the chosen supplier and lines', async () => {
    api.createPurchaseOrder.mockResolvedValue({ id: 3, po_number: 'PO-0003' });
    renderWithProviders(<NewPurchase />);

    await userEvent.selectOptions(await screen.findByLabelText(/supplier/i), '7');
    await userEvent.click(await screen.findByRole('button', { name: /add to order/i }));
    await userEvent.click(screen.getByRole('button', { name: /save as draft/i }));

    await waitFor(() =>
      expect(api.createPurchaseOrder).toHaveBeenCalledWith(
        expect.objectContaining({
          supplier_id: 7,
          status: 'DRAFT',
          items: [{ product_id: 1, quantity: 188, cost_price: '32.80' }],
        }),
      ),
    );
  });

  it('places an order directly when asked to', async () => {
    api.createPurchaseOrder.mockResolvedValue({ id: 4, po_number: 'PO-0004' });
    renderWithProviders(<NewPurchase />);

    await userEvent.click(await screen.findByRole('button', { name: /add to order/i }));
    await userEvent.click(screen.getByRole('button', { name: /place order/i }));

    await waitFor(() =>
      expect(api.createPurchaseOrder).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'ORDERED' }),
      ),
    );
  });

  it('adds a whole supplier group at once', async () => {
    renderWithProviders(<NewPurchase />);

    await userEvent.selectOptions(await screen.findByLabelText(/supplier/i), '7');
    await userEvent.click(await screen.findByRole('button', { name: /^add all$/i }));

    expect(screen.getByLabelText('Quantity for Coca-Cola 750ml')).toHaveValue(188);
  });

  it('defaults the delivery date to the supplier lead time', async () => {
    renderWithProviders(<NewPurchase />);
    await userEvent.selectOptions(await screen.findByLabelText(/supplier/i), '7');

    const expected = new Date();
    expected.setDate(expected.getDate() + 4);
    await waitFor(() =>
      expect(screen.getByLabelText(/expected delivery/i)).toHaveValue(
        expected.toISOString().slice(0, 10),
      ),
    );
  });

  it('says so when nothing needs reordering', async () => {
    api.getReorderSuggestions.mockResolvedValue({ groups: [], total_products: 0 });
    renderWithProviders(<NewPurchase />);

    expect(await screen.findByText('Nothing needs reordering')).toBeInTheDocument();
  });

  it('surfaces a rejected order instead of navigating away', async () => {
    api.createPurchaseOrder.mockRejectedValue(new Error('Purchase quantities must be at least 1'));
    renderWithProviders(<NewPurchase />);

    await userEvent.click(await screen.findByRole('button', { name: /add to order/i }));
    await userEvent.click(screen.getByRole('button', { name: /place order/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('must be at least 1');
  });
});
