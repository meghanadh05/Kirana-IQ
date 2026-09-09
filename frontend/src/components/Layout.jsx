import { NavLink, Outlet } from 'react-router-dom';

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/products', label: 'Products' },
  { to: '/forecast', label: 'Forecast' },
  { to: '/inventory', label: 'Inventory' },
  { to: '/analytics', label: 'Analytics' },
];

export default function Layout() {
  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__brand">
          Kirana<span>IQ</span>
        </div>
        <nav className="topbar__nav">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? 'navlink navlink--active' : 'navlink')}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
