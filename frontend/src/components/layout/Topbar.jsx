import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import Icon from '../ui/Icon.jsx';
import { useAuth } from '../../context/AuthContext.jsx';
import { initials } from '../../lib/format.js';

export default function Topbar({ onOpenSearch, onOpenNotifications, unread, onToggleSidebar }) {
  const { user, store, stores, selectStore, signOut } = useAuth();
  const navigate = useNavigate();
  const [menu, setMenu] = useState(null);
  const bar = useRef(null);

  // Any click outside the bar closes whichever menu is open.
  useEffect(() => {
    function onClick(event) {
      if (bar.current && !bar.current.contains(event.target)) setMenu(null);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform);

  return (
    <header className="topbar" ref={bar}>
      <button
        type="button"
        className="icon-button topbar__menu"
        onClick={onToggleSidebar}
        aria-label="Toggle navigation"
      >
        <Icon name="menu" size={18} />
      </button>

      <div className="menu-anchor">
        <button
          type="button"
          className="store-switch"
          onClick={() => setMenu(menu === 'store' ? null : 'store')}
          aria-haspopup="menu"
          aria-expanded={menu === 'store'}
        >
          <Icon name="store" size={15} className="u-subtle" />
          <span className="store-switch__name">{store?.name || 'No store'}</span>
          <Icon name="chevronDown" size={13} className="u-subtle" />
        </button>

        {menu === 'store' ? (
          <div className="menu menu--left" role="menu">
            <div className="menu__header u-xs u-muted">Your stores</div>
            {stores.map((candidate) => (
              <button
                key={candidate.id}
                type="button"
                className={`menu__item${candidate.id === store?.id ? ' menu__item--active' : ''}`}
                onClick={() => {
                  selectStore(candidate.id);
                  setMenu(null);
                  // A full reload is the honest way to drop every cached
                  // response belonging to the store we just left.
                  window.location.reload();
                }}
              >
                <Icon name="store" size={14} />
                <span className="u-grow u-truncate">{candidate.name}</span>
                <span className="u-xs u-subtle">{candidate.role}</span>
              </button>
            ))}
            <div className="menu__divider" />
            <Link className="menu__item" to="/onboarding" onClick={() => setMenu(null)}>
              <Icon name="plus" size={14} />
              Create a store
            </Link>
          </div>
        ) : null}
      </div>

      <div className="u-grow" style={{ display: 'flex', justifyContent: 'center' }}>
        <button type="button" className="search-trigger" onClick={onOpenSearch}>
          <Icon name="search" size={14} />
          <span>Search products, invoices, suppliers…</span>
          <kbd className="search-trigger__hint">{isMac ? '⌘' : 'Ctrl'} K</kbd>
        </button>
      </div>

      <button
        type="button"
        className="icon-button"
        onClick={onOpenNotifications}
        aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}
      >
        <Icon name="alerts" size={17} />
        {unread > 0 ? (
          <span className="icon-button__badge">{unread > 9 ? '9+' : unread}</span>
        ) : null}
      </button>

      <div className="menu-anchor">
        <button
          type="button"
          className="icon-button"
          style={{ width: 'auto', padding: '0 2px' }}
          onClick={() => setMenu(menu === 'user' ? null : 'user')}
          aria-haspopup="menu"
          aria-expanded={menu === 'user'}
          aria-label="Account menu"
        >
          <span className="avatar">{initials(user?.full_name)}</span>
        </button>

        {menu === 'user' ? (
          <div className="menu" role="menu">
            <div className="menu__header">
              <div className="u-small u-strong">{user?.full_name}</div>
              <div className="u-xs u-muted">{user?.email}</div>
            </div>
            <Link className="menu__item" to="/app/settings" onClick={() => setMenu(null)}>
              <Icon name="user" size={14} />
              Profile and settings
            </Link>
            <div className="menu__divider" />
            <button
              type="button"
              className="menu__item menu__item--danger"
              onClick={() => {
                signOut();
                navigate('/login');
              }}
            >
              <Icon name="logout" size={14} />
              Sign out
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
