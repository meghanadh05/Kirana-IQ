import { Route, Routes } from 'react-router-dom';

import Layout from './components/Layout.jsx';
import Analytics from './pages/Analytics.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Forecast from './pages/Forecast.jsx';
import Inventory from './pages/Inventory.jsx';
import Products from './pages/Products.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="products" element={<Products />} />
        <Route path="forecast" element={<Forecast />} />
        <Route path="inventory" element={<Inventory />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="*" element={<Dashboard />} />
      </Route>
    </Routes>
  );
}
