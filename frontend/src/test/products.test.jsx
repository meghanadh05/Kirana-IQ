import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ProductForm from '../pages/catalog/ProductForm.jsx';
import Products from '../pages/catalog/Products.jsx';
import { makeProduct, renderWithProviders, renderWithRouter } from './helpers.jsx';
import * as api from '../services/api.js';

vi.mock('../services/api.js', async () => {
  const actual = await vi.importActual('../services/api.js');
  return {
    ...actual,
    listProducts: vi.fn(),
    getProductCategories: vi.fn(),
    getCatalogueStats: vi.fn(),
    createProduct: vi.fn(),
    updateProduct: vi.fn(),
    listSuppliers: vi.fn(),
    getMe: vi.fn(),
    setUnauthorizedHandler: vi.fn(),
  };
});

const products = [
  makeProduct({ id: 1, name: 'Amul Milk 1L', current_stock: 40, reorder_level: 10 }),
  makeProduct({ id: 2, name: 'Parle-G', sku: 'SNK-001', barcode: null, current_stock: 4, reorder_level: 10 }),
  makeProduct({ id: 3, name: 'Sold Out', sku: 'SNK-002', barcode: null, current_stock: 0 }),
];

function mockList(rows = products) {
  api.listProducts.mockResolvedValue({ items: rows, total: rows.length, limit: 25, offset: 0 });
  api.getProductCategories.mockResolvedValue(['Dairy', 'Snacks']);
  api.getCatalogueStats.mockResolvedValue({
    total: rows.length,
    low_stock: 1,
    out_of_stock: 1,
    inventory_cost_value: '1188.00',
    inventory_retail_value: '1452.00',
  });
  api.listSuppliers.mockResolvedValue([]);
}

describe('Products list', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockList();
    // A stored token makes AuthProvider resolve a real session, so the
    // role-gated actions render exactly as they would for a signed-in owner.
    localStorage.setItem('kiranaiq.token', 'test-token');
    localStorage.setItem('kiranaiq.store', '1');
    api.getMe.mockResolvedValue({
      user: { id: 1, full_name: 'Owner', email: 'o@example.com', is_active: true },
      stores: [{ id: 1, name: 'Store', role: 'OWNER', onboarding_completed: true }],
    });
  });

  it('renders one row per product', async () => {
    renderWithProviders(<Products />);
    expect(await screen.findByText('Amul Milk 1L')).toBeInTheDocument();
    expect(screen.getByText('Parle-G')).toBeInTheDocument();
  });

  it('labels stock status from the reorder level', async () => {
    renderWithProviders(<Products />);
    await screen.findByText('Amul Milk 1L');

    // Scoped to the table: the same words appear in the filter dropdown.
    const table = screen.getByRole('table');
    expect(within(table).getByText('In stock')).toBeInTheDocument();
    expect(within(table).getByText('Low')).toBeInTheDocument();
    expect(within(table).getByText('Out of stock')).toBeInTheDocument();
  });

  it('shows the margin per product', async () => {
    renderWithProviders(<Products />);
    await screen.findByText('Amul Milk 1L');
    // (33 - 27) / 33 = 18%
    expect(screen.getAllByText('18%').length).toBeGreaterThan(0);
  });

  it('passes the search term to the API', async () => {
    renderWithProviders(<Products />);
    await screen.findByText('Amul Milk 1L');

    await userEvent.type(screen.getByLabelText(/search products/i), 'milk');

    await waitFor(() =>
      expect(api.listProducts).toHaveBeenCalledWith(expect.objectContaining({ search: 'milk' })),
    );
  });

  it('passes the stock filter to the API', async () => {
    renderWithProviders(<Products />);
    await screen.findByText('Amul Milk 1L');

    await userEvent.selectOptions(screen.getByLabelText(/stock status/i), 'low');

    await waitFor(() =>
      expect(api.listProducts).toHaveBeenCalledWith(
        expect.objectContaining({ stock_status: 'low' }),
      ),
    );
  });

  it('offers a way forward when the catalogue is empty', async () => {
    mockList([]);
    renderWithProviders(<Products />);

    await screen.findByText('No products yet');
    expect(await screen.findAllByRole('button', { name: /add product/i })).not.toHaveLength(0);
    expect(screen.getAllByRole('button', { name: /import csv/i })).not.toHaveLength(0);
  });

  it('shows an error state with a retry when the request fails', async () => {
    api.listProducts.mockRejectedValue(new Error('Could not reach the server.'));
    renderWithProviders(<Products />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach the server.');
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });
});

describe('Product form', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listSuppliers.mockResolvedValue([]);
  });

  it('creates a product from the entered values', async () => {
    api.createProduct.mockResolvedValue(makeProduct());
    const onSaved = vi.fn();

    renderWithRouter(<ProductForm open onClose={() => {}} onSaved={onSaved} />);

    await userEvent.type(screen.getByLabelText(/^name$/i), 'Amul Milk 1L');
    await userEvent.type(screen.getByLabelText(/^sku$/i), 'DRY-001');
    await userEvent.type(screen.getByLabelText(/^category$/i), 'Dairy');
    await userEvent.type(screen.getByLabelText(/selling price/i), '33');
    await userEvent.type(screen.getByLabelText(/opening stock/i), '40');
    await userEvent.click(screen.getByRole('button', { name: /add product/i }));

    await waitFor(() =>
      expect(api.createProduct).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Amul Milk 1L',
          sku: 'DRY-001',
          category: 'Dairy',
          selling_price: '33',
          current_stock: 40,
        }),
      ),
    );
    expect(onSaved).toHaveBeenCalled();
  });

  it('sends an empty barcode as null, not an empty string', async () => {
    api.createProduct.mockResolvedValue(makeProduct());
    renderWithRouter(<ProductForm open onClose={() => {}} onSaved={() => {}} />);

    await userEvent.type(screen.getByLabelText(/^name$/i), 'No Barcode');
    await userEvent.type(screen.getByLabelText(/^sku$/i), 'NB-1');
    await userEvent.type(screen.getByLabelText(/^category$/i), 'Other');
    await userEvent.type(screen.getByLabelText(/selling price/i), '10');
    await userEvent.click(screen.getByRole('button', { name: /add product/i }));

    await waitFor(() =>
      expect(api.createProduct).toHaveBeenCalledWith(expect.objectContaining({ barcode: null })),
    );
  });

  it('warns when the cost price is above the selling price', async () => {
    renderWithRouter(<ProductForm open onClose={() => {}} onSaved={() => {}} />);

    await userEvent.type(screen.getByLabelText(/selling price/i), '10');
    await userEvent.type(screen.getByLabelText(/cost price/i), '20');

    expect(screen.getByText(/Cost is above the selling price/i)).toBeInTheDocument();
  });

  it('shows a duplicate-SKU conflict from the API', async () => {
    api.createProduct.mockRejectedValue(new Error("SKU 'DRY-001' already exists in this store"));
    renderWithRouter(<ProductForm open onClose={() => {}} onSaved={() => {}} />);

    await userEvent.type(screen.getByLabelText(/^name$/i), 'Duplicate');
    await userEvent.type(screen.getByLabelText(/^sku$/i), 'DRY-001');
    await userEvent.type(screen.getByLabelText(/^category$/i), 'Dairy');
    await userEvent.type(screen.getByLabelText(/selling price/i), '33');
    await userEvent.click(screen.getByRole('button', { name: /add product/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('already exists');
  });

  it('omits the stock field when editing, because stock moves via the ledger', () => {
    renderWithRouter(
      <ProductForm open product={makeProduct()} onClose={() => {}} onSaved={() => {}} />,
    );
    expect(screen.queryByLabelText(/opening stock/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Stock levels change through the inventory ledger/i)).toBeInTheDocument();
  });

  it('pre-fills the form when editing', () => {
    renderWithRouter(
      <ProductForm open product={makeProduct()} onClose={() => {}} onSaved={() => {}} />,
    );
    expect(screen.getByLabelText(/^name$/i)).toHaveValue('Amul Taaza Milk 1L');
    expect(screen.getByLabelText(/^sku$/i)).toHaveValue('DRY-001');
  });
});
