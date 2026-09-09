import { Navigate, Route, Routes } from 'react-router-dom';

import AppLayout from './components/layout/AppLayout.jsx';
import { AuthProvider } from './context/AuthContext.jsx';
import { ToastProvider } from './context/ToastContext.jsx';

import Landing from './pages/Landing.jsx';
import Overview from './pages/Overview.jsx';
import Settings from './pages/Settings.jsx';

import ForgotPassword from './pages/auth/ForgotPassword.jsx';
import Login from './pages/auth/Login.jsx';
import Register from './pages/auth/Register.jsx';
import Onboarding from './pages/onboarding/Onboarding.jsx';

import POS from './pages/pos/POS.jsx';
import SaleDetail from './pages/sales/SaleDetail.jsx';
import Sales from './pages/sales/Sales.jsx';

import Categories from './pages/catalog/Categories.jsx';
import ProductDetail from './pages/catalog/ProductDetail.jsx';
import Products from './pages/catalog/Products.jsx';

import Inventory from './pages/inventory/Inventory.jsx';
import Movements from './pages/inventory/Movements.jsx';

import NewPurchase from './pages/purchasing/NewPurchase.jsx';
import PurchaseDetail from './pages/purchasing/PurchaseDetail.jsx';
import Purchases from './pages/purchasing/Purchases.jsx';
import SupplierDetail from './pages/purchasing/SupplierDetail.jsx';
import Suppliers from './pages/purchasing/Suppliers.jsx';

import Alerts from './pages/intelligence/Alerts.jsx';
import Analytics from './pages/intelligence/Analytics.jsx';
import Forecasting from './pages/intelligence/Forecasting.jsx';

import CustomerDetail from './pages/business/CustomerDetail.jsx';
import Customers from './pages/business/Customers.jsx';
import Expenses from './pages/business/Expenses.jsx';
import Reports from './pages/business/Reports.jsx';

/**
 * Routes.
 *
 * Public pages sit at the root; everything behind sign-in lives under /app, so
 * the guard is one place (AppLayout) rather than a check on every screen.
 * `/purchases/new` is declared before `/purchases/:id` so "new" is not read as
 * an order id.
 */
export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/onboarding" element={<Onboarding />} />

          <Route path="/app" element={<AppLayout />}>
            <Route index element={<Overview />} />

            <Route path="pos" element={<POS />} />
            <Route path="sales" element={<Sales />} />
            <Route path="sales/:id" element={<SaleDetail />} />

            <Route path="products" element={<Products />} />
            <Route path="products/:id" element={<ProductDetail />} />
            <Route path="categories" element={<Categories />} />

            <Route path="inventory" element={<Inventory />} />
            <Route path="inventory/movements" element={<Movements />} />

            <Route path="purchases" element={<Purchases />} />
            <Route path="purchases/new" element={<NewPurchase />} />
            <Route path="purchases/:id" element={<PurchaseDetail />} />
            <Route path="suppliers" element={<Suppliers />} />
            <Route path="suppliers/:id" element={<SupplierDetail />} />

            <Route path="forecasting" element={<Forecasting />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="alerts" element={<Alerts />} />

            <Route path="customers" element={<Customers />} />
            <Route path="customers/:id" element={<CustomerDetail />} />
            <Route path="expenses" element={<Expenses />} />
            <Route path="reports" element={<Reports />} />

            <Route path="settings" element={<Settings />} />

            <Route path="*" element={<Navigate to="/app" replace />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </ToastProvider>
  );
}
