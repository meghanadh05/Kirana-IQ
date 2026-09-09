import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import POS from '../pages/pos/POS.jsx';
import CheckoutModal from '../pages/pos/CheckoutModal.jsx';
import { makeProduct, makeSale, renderWithRouter } from './helpers.jsx';
import * as api from '../services/api.js';

vi.mock('../services/api.js', async () => {
  const actual = await vi.importActual('../services/api.js');
  return {
    ...actual,
    listProducts: vi.fn(),
    getProductCategories: vi.fn(),
    lookupBarcode: vi.fn(),
    checkout: vi.fn(),
  };
});

const milk = makeProduct({ id: 1, name: 'Amul Milk 1L', selling_price: '33.00', current_stock: 40 });
const bread = makeProduct({
  id: 2, name: 'Britannia Bread', sku: 'BKY-001', barcode: '8909999999999',
  selling_price: '50.00', tax_rate: '0.00', current_stock: 3, reorder_level: 5,
});

function mockCatalogue(products = [milk, bread]) {
  api.listProducts.mockResolvedValue({ items: products, total: products.length, limit: 60, offset: 0 });
  api.getProductCategories.mockResolvedValue(['Dairy', 'Bakery']);
}

describe('POS cart', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCatalogue();
  });

  it('adds a product to the cart when its tile is tapped', async () => {
    renderWithRouter(<POS />);

    await userEvent.click(await screen.findByRole('button', { name: /Amul Milk 1L/i }));

    const cart = screen.getByText('Current sale').closest('.cart');
    expect(within(cart).getByText('Amul Milk 1L')).toBeInTheDocument();
  });

  it('totals the cart including tax', async () => {
    renderWithRouter(<POS />);
    await userEvent.click(await screen.findByRole('button', { name: /Amul Milk 1L/i }));

    // 33.00 + 5% tax = 34.65
    expect(await screen.findByRole('button', { name: /Checkout · ₹34.65/ })).toBeInTheDocument();
  });

  it('merges a repeated product into one line', async () => {
    renderWithRouter(<POS />);
    const tile = await screen.findByRole('button', { name: /Amul Milk 1L/i });

    await userEvent.click(tile);
    await userEvent.click(tile);

    expect(screen.getByLabelText('Quantity of Amul Milk 1L')).toHaveValue(2);
  });

  it('increments and decrements a line with the stepper', async () => {
    renderWithRouter(<POS />);
    await userEvent.click(await screen.findByRole('button', { name: /Amul Milk 1L/i }));

    await userEvent.click(screen.getByLabelText('Increase quantity'));
    expect(screen.getByLabelText('Quantity of Amul Milk 1L')).toHaveValue(2);

    await userEvent.click(screen.getByLabelText('Decrease quantity'));
    expect(screen.getByLabelText('Quantity of Amul Milk 1L')).toHaveValue(1);
  });

  it('removes a line when it is decremented to zero', async () => {
    renderWithRouter(<POS />);
    await userEvent.click(await screen.findByRole('button', { name: /Amul Milk 1L/i }));
    await userEvent.click(screen.getByLabelText('Decrease quantity'));

    expect(screen.getByText(/Scan a barcode or tap a product/i)).toBeInTheDocument();
  });

  it('refuses to add more units than are in stock', async () => {
    renderWithRouter(<POS />);
    const tile = await screen.findByRole('button', { name: /Britannia Bread/i });

    // Only three in stock.
    await userEvent.click(tile);
    await userEvent.click(tile);
    await userEvent.click(tile);
    await userEvent.click(tile);

    expect(screen.getByLabelText('Quantity of Britannia Bread')).toHaveValue(3);
    expect(await screen.findByText(/Only 3 of Britannia Bread in stock/i)).toBeInTheDocument();
  });

  it('disables the tile for an out-of-stock product', async () => {
    mockCatalogue([makeProduct({ id: 3, name: 'Sold Out Item', current_stock: 0 })]);
    renderWithRouter(<POS />);

    expect(await screen.findByRole('button', { name: /Sold Out Item/i })).toBeDisabled();
  });

  it('cannot check out an empty cart', async () => {
    renderWithRouter(<POS />);
    expect(await screen.findByRole('button', { name: /Checkout/ })).toBeDisabled();
  });

  it('adds a scanned barcode to the cart', async () => {
    api.lookupBarcode.mockResolvedValue(bread);
    renderWithRouter(<POS />);

    const scan = screen.getByLabelText('Scan barcode');
    await userEvent.type(scan, '8909999999999{Enter}');

    await waitFor(() => expect(api.lookupBarcode).toHaveBeenCalledWith('8909999999999'));
    expect(await screen.findByLabelText('Quantity of Britannia Bread')).toHaveValue(1);
    expect(scan).toHaveValue('');
  });

  it('reports an unknown barcode instead of failing silently', async () => {
    const error = new Error('No product matches');
    error.status = 404;
    api.lookupBarcode.mockRejectedValue(error);
    renderWithRouter(<POS />);

    await userEvent.type(screen.getByLabelText('Scan barcode'), 'nope{Enter}');

    expect(await screen.findByText(/No product matches “nope”/i)).toBeInTheDocument();
  });

  it('clears the cart on demand', async () => {
    renderWithRouter(<POS />);
    await userEvent.click(await screen.findByRole('button', { name: /Amul Milk 1L/i }));
    await userEvent.click(screen.getByRole('button', { name: /^Clear$/ }));

    expect(screen.getByText(/Scan a barcode or tap a product/i)).toBeInTheDocument();
  });

  it('holds a sale and lets it be resumed', async () => {
    renderWithRouter(<POS />);
    await userEvent.click(await screen.findByRole('button', { name: /Amul Milk 1L/i }));
    await userEvent.click(screen.getByRole('button', { name: /^Hold$/ }));

    expect(screen.getByText(/Scan a barcode or tap a product/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /1 item · resume/i }));
    expect(screen.getByLabelText('Quantity of Amul Milk 1L')).toHaveValue(1);
  });

  it('shows an empty state when the catalogue has no products', async () => {
    mockCatalogue([]);
    renderWithRouter(<POS />);

    expect(await screen.findByText('No products yet')).toBeInTheDocument();
  });
});

describe('Checkout modal', () => {
  const cart = [
    {
      product_id: 1, name: 'Amul Milk 1L', sku: 'DRY-001', unit: 'piece',
      unit_price: 33, tax_rate: 5, stock: 40, quantity: 2,
    },
  ];
  const totals = { subtotal: 66, tax: 3.3, total: 69.3, units: 2 };

  beforeEach(() => vi.clearAllMocks());

  it('shows the payable amount', () => {
    renderWithRouter(
      <CheckoutModal open cart={cart} totals={totals} onClose={() => {}} onComplete={() => {}} />,
    );
    expect(screen.getByRole('button', { name: /Complete sale · ₹69.30/ })).toBeInTheDocument();
  });

  it('subtracts a discount from the total', async () => {
    renderWithRouter(
      <CheckoutModal open cart={cart} totals={totals} onClose={() => {}} onComplete={() => {}} />,
    );

    await userEvent.type(screen.getByLabelText(/discount/i), '9.30');
    expect(await screen.findByRole('button', { name: /Complete sale · ₹60.00/ })).toBeInTheDocument();
  });

  it('calculates the change to return', async () => {
    renderWithRouter(
      <CheckoutModal open cart={cart} totals={totals} onClose={() => {}} onComplete={() => {}} />,
    );

    await userEvent.type(screen.getByLabelText(/amount received/i), '100');
    expect(await screen.findByText('Change to return')).toBeInTheDocument();
    expect(screen.getByText('₹30.70')).toBeInTheDocument();
  });

  it('blocks completion when cash received is short', async () => {
    renderWithRouter(
      <CheckoutModal open cart={cart} totals={totals} onClose={() => {}} onComplete={() => {}} />,
    );

    await userEvent.type(screen.getByLabelText(/amount received/i), '10');

    expect(screen.getByText(/Less than the amount payable/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Complete sale/ })).toBeDisabled();
  });

  it('posts the cart and the customer details on completion', async () => {
    api.checkout.mockResolvedValue(makeSale());
    const onComplete = vi.fn();

    renderWithRouter(
      <CheckoutModal open cart={cart} totals={totals} onClose={() => {}} onComplete={onComplete} />,
    );

    await userEvent.type(screen.getByLabelText(/customer phone/i), '9876512345');
    await userEvent.click(screen.getByRole('button', { name: /Complete sale/ }));

    await waitFor(() =>
      expect(api.checkout).toHaveBeenCalledWith(
        expect.objectContaining({
          items: [{ product_id: 1, quantity: 2 }],
          payment_method: 'CASH',
          customer_phone: '9876512345',
        }),
      ),
    );
    expect(onComplete).toHaveBeenCalled();
  });

  it('surfaces a rejected checkout instead of pretending it worked', async () => {
    api.checkout.mockRejectedValue(new Error('Amul Milk 1L: only 1 in stock, 2 requested'));
    const onComplete = vi.fn();

    renderWithRouter(
      <CheckoutModal open cart={cart} totals={totals} onClose={() => {}} onComplete={onComplete} />,
    );
    await userEvent.click(screen.getByRole('button', { name: /Complete sale/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('only 1 in stock');
    expect(onComplete).not.toHaveBeenCalled();
  });

  it('switches payment method', async () => {
    api.checkout.mockResolvedValue(makeSale());
    renderWithRouter(
      <CheckoutModal open cart={cart} totals={totals} onClose={() => {}} onComplete={() => {}} />,
    );

    await userEvent.click(screen.getByRole('button', { name: /UPI/ }));
    // The cash-only "amount received" field disappears for non-cash tenders.
    expect(screen.queryByLabelText(/amount received/i)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Complete sale/ }));
    await waitFor(() =>
      expect(api.checkout).toHaveBeenCalledWith(
        expect.objectContaining({ payment_method: 'UPI' }),
      ),
    );
  });
});
