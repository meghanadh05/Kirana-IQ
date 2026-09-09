import { screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from './helpers.jsx';
import * as api from '../services/api.js';

/**
 * Every page, mounted once with plausible data.
 *
 * The behaviour tests cover the screens where logic lives; this catches the
 * other failure mode — a page that throws the moment it renders, which a build
 * cannot detect and which no amount of unit testing elsewhere would reveal.
 */
vi.mock('../services/api.js', async () => {
  const actual = await vi.importActual('../services/api.js');
  const stub = () => vi.fn();
  return {
    ...actual,
    setUnauthorizedHandler: vi.fn(),
    getMe: stub(),
    getDashboard: stub(),
    getBriefing: stub(),
    listProducts: stub(),
    getProduct: stub(),
    getProductCategories: stub(),
    getBrands: stub(),
    getCatalogueStats: stub(),
    listCategories: stub(),
    listSales: stub(),
    getSale: stub(),
    getStockPosition: stub(),
    listMovements: stub(),
    getRecommendations: stub(),
    getProductRecommendation: stub(),
    listSuppliers: stub(),
    getSupplier: stub(),
    listPurchaseOrders: stub(),
    getPurchaseOrder: stub(),
    getReorderSuggestions: stub(),
    listCustomers: stub(),
    getCustomer: stub(),
    listExpenses: stub(),
    listNotifications: stub(),
    listReports: stub(),
    getModelStatus: stub(),
    getForecast: stub(),
    getSalesAnalytics: stub(),
    getProductAnalytics: stub(),
    getInventoryAnalytics: stub(),
    getCategoryAnalytics: stub(),
    getProfitAnalytics: stub(),
    getStoreSettings: stub(),
    listMembers: stub(),
  };
});

import Landing from '../pages/Landing.jsx';
import Overview from '../pages/Overview.jsx';
import Settings from '../pages/Settings.jsx';
import Login from '../pages/auth/Login.jsx';
import Register from '../pages/auth/Register.jsx';
import ForgotPassword from '../pages/auth/ForgotPassword.jsx';
import Onboarding from '../pages/onboarding/Onboarding.jsx';
import Sales from '../pages/sales/Sales.jsx';
import Products from '../pages/catalog/Products.jsx';
import Categories from '../pages/catalog/Categories.jsx';
import Inventory from '../pages/inventory/Inventory.jsx';
import Movements from '../pages/inventory/Movements.jsx';
import Purchases from '../pages/purchasing/Purchases.jsx';
import Suppliers from '../pages/purchasing/Suppliers.jsx';
import NewPurchase from '../pages/purchasing/NewPurchase.jsx';
import Forecasting from '../pages/intelligence/Forecasting.jsx';
import Analytics from '../pages/intelligence/Analytics.jsx';
import Alerts from '../pages/intelligence/Alerts.jsx';
import Customers from '../pages/business/Customers.jsx';
import Expenses from '../pages/business/Expenses.jsx';
import Reports from '../pages/business/Reports.jsx';

const page = (items = []) => ({ items, total: items.length, limit: 25, offset: 0 });

const dashboard = {
  date: '2026-09-09',
  today: { revenue: 0, tax: 0, net_revenue: 0, cost_of_goods: 0, gross_profit: 0,
           gross_margin_pct: null, orders: 0, units: 0, average_order_value: 0 },
  yesterday_revenue: 0,
  week: { revenue: 0, tax: 0, net_revenue: 0, cost_of_goods: 0, gross_profit: 0,
          gross_margin_pct: null, orders: 0, units: 0 },
  inventory: { total_products: 0, low_stock: 0, out_of_stock: 0,
               inventory_cost_value: 0, inventory_retail_value: 0 },
  forecast_available: false,
  risk: null,
  reorders: [],
  anomalies: [],
  top_products: [],
  slow_movers: [],
  recent_sales: [],
  revenue_series: [],
};

const profit = {
  start_date: '2026-08-10', end_date: '2026-09-09', revenue: 0, tax: 0, net_revenue: 0,
  cost_of_goods: 0, gross_profit: 0, gross_margin_pct: null, orders: 0,
  recorded_expenses: 0, expense_breakdown: [], estimated_operating_profit: 0,
  note: 'Estimated operating profit is gross profit minus expenses recorded in Kirana-IQ.',
};

describe('page smoke tests', () => {
  beforeEach(() => {
    localStorage.setItem('kiranaiq.token', 'test-token');
    localStorage.setItem('kiranaiq.store', '1');

    api.getMe.mockResolvedValue({
      user: { id: 1, full_name: 'Test Owner', email: 'o@example.com', is_active: true },
      stores: [{ id: 1, name: 'Test Store', role: 'OWNER', onboarding_completed: true,
                 currency: 'INR', business_type: 'KIRANA', is_demo: false }],
    });
    api.getDashboard.mockResolvedValue(dashboard);
    api.getBriefing.mockResolvedValue({
      greeting: 'Good morning', user_name: 'Test Owner', attention_count: 0,
      headlines: [{ icon: 'revenue', text: 'No sales recorded yet today', link: '/sales' }],
      actions: [], today_revenue: 0, today_orders: 0,
    });
    api.listProducts.mockResolvedValue(page());
    api.getProductCategories.mockResolvedValue([]);
    api.getBrands.mockResolvedValue([]);
    api.getCatalogueStats.mockResolvedValue({
      total: 0, low_stock: 0, out_of_stock: 0,
      inventory_cost_value: '0', inventory_retail_value: '0',
    });
    api.listCategories.mockResolvedValue([]);
    api.listSales.mockResolvedValue(page());
    api.getStockPosition.mockResolvedValue({
      products: [], total_products: 0, out_of_stock: 0, low_stock: 0,
      inventory_cost_value: 0, inventory_retail_value: 0,
    });
    api.listMovements.mockResolvedValue(page());
    api.getRecommendations.mockResolvedValue([]);
    api.listSuppliers.mockResolvedValue([]);
    api.listPurchaseOrders.mockResolvedValue(page());
    api.getReorderSuggestions.mockResolvedValue({ groups: [], total_products: 0 });
    api.listCustomers.mockResolvedValue(page());
    api.listExpenses.mockResolvedValue({ ...page(), total_amount: 0, by_category: [] });
    api.listNotifications.mockResolvedValue({ items: [], unread: 0 });
    api.listReports.mockResolvedValue([
      { id: 'daily-sales', label: 'Daily sales', description: 'Revenue per day.' },
    ]);
    api.getModelStatus.mockResolvedValue({ trained: false, history_days: 0, last_run: null });
    api.getSalesAnalytics.mockResolvedValue({
      start_date: '2026-08-10', end_date: '2026-09-09', days: 30, revenue: 0, tax: 0,
      net_revenue: 0, cost_of_goods: 0, gross_profit: 0, gross_margin_pct: null,
      orders: 0, units: 0, discount: 0, average_order_value: 0,
      daily_average_revenue: 0, series: [], payment_split: [],
    });
    api.getProductAnalytics.mockResolvedValue({
      best_sellers: [], most_profitable: [], worst_sellers: [], no_sales: [],
    });
    api.getInventoryAnalytics.mockResolvedValue({
      inventory_cost_value: 0, inventory_retail_value: 0, total_products: 0, low_stock: 0,
      out_of_stock: 0, stock_turnover: null, cost_of_goods: 0, dead_stock: [],
      dead_stock_value: 0, overstock: [],
    });
    api.getCategoryAnalytics.mockResolvedValue([]);
    api.getProfitAnalytics.mockResolvedValue(profit);
    api.getStoreSettings.mockResolvedValue({
      store_id: 1, low_stock_threshold: 10, default_tax_rate: '0.00',
      default_lead_time_days: 3, invoice_prefix: 'INV', purchase_order_prefix: 'PO',
      financial_year_start_month: 4, timezone: 'Asia/Kolkata',
      critical_cover_days: '2.00', medium_cover_buffer_days: '3.00',
      overstock_cover_days: '30.00', safety_days: 3, service_level_z: '1.280',
    });
    api.listMembers.mockResolvedValue([
      { id: 1, store_id: 1, user_id: 1, role: 'OWNER', email: 'o@example.com',
        full_name: 'Test Owner', phone: null, created_at: '2026-01-01T00:00:00Z' },
    ]);
  });

  afterEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  const PAGES = [
    ['Landing', <Landing />, /Run your kirana smarter/i],
    ['Login', <Login />, /Sign in/i],
    ['Register', <Register />, /Create your account/i],
    ['Forgot password', <ForgotPassword />, /Reset your password/i],
    ['Onboarding', <Onboarding />, /Tell us about your store/i],
    ['Overview', <Overview />, /Today at a glance/i],
    ['Products', <Products />, /No products yet/i],
    ['Categories', <Categories />, /No categories yet/i],
    ['Sales', <Sales />, /No sales match these filters/i],
    ['Inventory', <Inventory />, /No products to track yet/i],
    ['Movements', <Movements />, /No movements recorded/i],
    ['Purchases', <Purchases />, /No purchase orders yet/i],
    ['New purchase', <NewPurchase />, /New purchase order/i],
    ['Suppliers', <Suppliers />, /No suppliers yet/i],
    ['Forecasting', <Forecasting />, /Forecast model/i],
    ['Analytics', <Analytics />, /Analytics/i],
    ['Alerts', <Alerts />, /No alerts/i],
    ['Customers', <Customers />, /No customers yet/i],
    ['Expenses', <Expenses />, /No expenses recorded/i],
    ['Reports', <Reports />, /Daily sales/i],
    ['Settings', <Settings />, /Store profile/i],
  ];

  it.each(PAGES)('%s renders without crashing', async (name, element, marker) => {
    renderWithProviders(element);
    await waitFor(() => expect(screen.getAllByText(marker).length).toBeGreaterThan(0));
  });
});
