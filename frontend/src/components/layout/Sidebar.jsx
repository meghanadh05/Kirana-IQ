import { NavLink } from 'react-router-dom';

import Icon from '../ui/Icon.jsx';
import { useAuth } from '../../context/AuthContext.jsx';

/**
 * Navigation, grouped by what the shopkeeper is trying to do rather than by
 * which table the data lives in.
 *
 * `minimumRole` hides links a role cannot use. That is presentation only — the
 * API enforces the same rule, so a hand-typed URL gets a 403 either way.
 */
const GROUPS = [
  {
    items: [{ to: '/app', label: 'Overview', icon: 'overview', end: true }],
  },
  {
    label: 'Sell',
    items: [
      { to: '/app/pos', label: 'POS', icon: 'pos' },
      { to: '/app/sales', label: 'Sales', icon: 'sales' },
    ],
  },
  {
    label: 'Catalogue',
    items: [
      { to: '/app/products', label: 'Products', icon: 'products' },
      { to: '/app/categories', label: 'Categories', icon: 'categories', minimumRole: 'MANAGER' },
    ],
  },
  {
    label: 'Inventory',
    items: [
      { to: '/app/inventory', label: 'Inventory', icon: 'inventory' },
      { to: '/app/purchases', label: 'Purchase Orders', icon: 'purchases', minimumRole: 'MANAGER' },
      { to: '/app/suppliers', label: 'Suppliers', icon: 'suppliers', minimumRole: 'MANAGER' },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { to: '/app/forecasting', label: 'Forecasting', icon: 'forecast', minimumRole: 'MANAGER' },
      { to: '/app/analytics', label: 'Analytics', icon: 'analytics', minimumRole: 'MANAGER' },
      { to: '/app/alerts', label: 'Alerts', icon: 'alerts' },
    ],
  },
  {
    label: 'Business',
    items: [
      { to: '/app/customers', label: 'Customers', icon: 'customers' },
      { to: '/app/expenses', label: 'Expenses', icon: 'expenses', minimumRole: 'MANAGER' },
      { to: '/app/reports', label: 'Reports', icon: 'reports', minimumRole: 'MANAGER' },
    ],
  },
];

const RANK = { CASHIER: 1, MANAGER: 2, OWNER: 3 };

export default function Sidebar({ open, onNavigate, alertCount = 0 }) {
  const { role } = useAuth();
  const allowed = (item) => !item.minimumRole || (RANK[role] || 0) >= RANK[item.minimumRole];

  return (
    <aside className={`sidebar${open ? ' sidebar--open' : ''}`}>
      <div className="sidebar__brand">
        <span className="sidebar__mark">K</span>
        Kirana-IQ
      </div>

      <nav className="sidebar__nav" aria-label="Main">
        {GROUPS.map((group, index) => {
          const items = group.items.filter(allowed);
          if (items.length === 0) return null;

          return (
            <div className="sidebar__group" key={group.label || index}>
              {group.label ? <div className="sidebar__group-label">{group.label}</div> : null}
              {items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    `sidebar__link${isActive ? ' sidebar__link--active' : ''}`
                  }
                >
                  <Icon name={item.icon} size={15} />
                  {item.label}
                  {item.to === '/app/alerts' && alertCount > 0 ? (
                    <span className="sidebar__count">{alertCount}</span>
                  ) : null}
                </NavLink>
              ))}
            </div>
          );
        })}
      </nav>

      <div className="sidebar__footer">
        <NavLink
          to="/app/settings"
          onClick={onNavigate}
          className={({ isActive }) => `sidebar__link${isActive ? ' sidebar__link--active' : ''}`}
        >
          <Icon name="settings" size={15} />
          Settings
        </NavLink>
      </div>
    </aside>
  );
}
