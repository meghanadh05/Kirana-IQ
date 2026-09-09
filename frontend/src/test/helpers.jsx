import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

import { AuthProvider } from '../context/AuthContext.jsx';
import { ToastProvider } from '../context/ToastContext.jsx';

/**
 * Render a component inside the providers it expects.
 *
 * Tests drive real components through their real contexts and assert on what a
 * user would see; only the network layer is mocked.
 */
export function renderWithProviders(ui, { route = '/' } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <AuthProvider>{ui}</AuthProvider>
      </ToastProvider>
    </MemoryRouter>,
  );
}

/** Render without AuthProvider, for components that take their own props. */
export function renderWithRouter(ui, { route = '/' } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>{ui}</ToastProvider>
    </MemoryRouter>,
  );
}

export function makeProduct(overrides = {}) {
  return {
    id: 1,
    store_id: 1,
    sku: 'DRY-001',
    barcode: '8901234567890',
    name: 'Amul Taaza Milk 1L',
    description: null,
    category: 'Dairy',
    brand: 'Amul',
    unit: 'piece',
    selling_price: '33.00',
    cost_price: '27.00',
    tax_rate: '5.00',
    current_stock: 40,
    reorder_level: 10,
    lead_time_days: 2,
    supplier_id: null,
    is_active: true,
    created_at: '2026-09-01T10:00:00Z',
    updated_at: '2026-09-01T10:00:00Z',
    ...overrides,
  };
}

export function makeSale(overrides = {}) {
  return {
    id: 10,
    store_id: 1,
    invoice_number: 'INV-00042',
    customer_id: null,
    customer_name: null,
    customer_phone: null,
    subtotal: '66.00',
    discount: '0.00',
    tax: '3.30',
    total: '69.30',
    cost_total: '54.00',
    payment_method: 'CASH',
    amount_received: '100.00',
    change_due: '30.70',
    status: 'COMPLETED',
    notes: null,
    sale_date: '2026-09-09',
    created_at: '2026-09-09T12:00:00Z',
    created_by: 1,
    item_count: 1,
    unit_count: 2,
    gross_profit: 12,
    items: [
      {
        id: 1,
        product_id: 1,
        product_name: 'Amul Taaza Milk 1L',
        sku: 'DRY-001',
        quantity: 2,
        unit_price: '33.00',
        cost_price: '27.00',
        discount: '0.00',
        tax_rate: '5.00',
        tax_amount: '3.30',
        line_total: '66.00',
      },
    ],
    payments: [{ id: 1, method: 'CASH', amount: '69.30', reference: null }],
    ...overrides,
  };
}

/** Silence the act() noise React logs for state settled inside async effects. */
export function quietConsole() {
  const error = console.error;
  vi.spyOn(console, 'error').mockImplementation((...args) => {
    if (typeof args[0] === 'string' && args[0].includes('not wrapped in act')) return;
    error(...args);
  });
}
