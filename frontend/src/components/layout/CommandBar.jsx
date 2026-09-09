import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';

import Icon from '../ui/Icon.jsx';
import { search as searchApi } from '../../services/api.js';
import { useDebounce } from '../../hooks/useDebounce.js';

/**
 * The ⌘K command bar.
 *
 * Below three characters it offers navigation shortcuts; above that it searches
 * the store. Arrow keys and Enter drive it, so it never needs the mouse.
 */
const SHORTCUTS = [
  { label: 'Open POS', sublabel: 'Ring up a sale', link: '/app/pos', icon: 'pos' },
  { label: 'Products', sublabel: 'Catalogue', link: '/app/products', icon: 'products' },
  { label: 'Sales', sublabel: 'Invoice history', link: '/app/sales', icon: 'sales' },
  { label: 'Inventory', sublabel: 'Stock levels', link: '/app/inventory', icon: 'inventory' },
  { label: 'Purchase Orders', sublabel: 'Reorder stock', link: '/app/purchases', icon: 'purchases' },
  { label: 'Forecasting', sublabel: 'Demand and reorder advice', link: '/app/forecasting', icon: 'forecast' },
  { label: 'Reports', sublabel: 'Download CSVs', link: '/app/reports', icon: 'reports' },
  { label: 'Settings', sublabel: 'Store configuration', link: '/app/settings', icon: 'settings' },
];

const GROUP_ICONS = {
  products: 'products',
  sales: 'sales',
  suppliers: 'suppliers',
  customers: 'customers',
};

export default function CommandBar({ open, onClose }) {
  const [term, setTerm] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);
  const navigate = useNavigate();
  const input = useRef(null);
  const debounced = useDebounce(term, 220);

  useEffect(() => {
    if (open) {
      setTerm('');
      setResults(null);
      setActive(0);
      // The autofocus has to wait for the portal to mount.
      requestAnimationFrame(() => input.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    if (!open || debounced.trim().length < 3) {
      setResults(null);
      return undefined;
    }

    let active = true;
    setLoading(true);
    searchApi(debounced.trim())
      .then((data) => active && setResults(data))
      .catch(() => active && setResults(null))
      .finally(() => active && setLoading(false));

    return () => {
      active = false;
    };
  }, [debounced, open]);

  const items = useMemo(() => {
    if (!results) {
      const query = term.trim().toLowerCase();
      return SHORTCUTS.filter(
        (shortcut) => !query || shortcut.label.toLowerCase().includes(query),
      ).map((shortcut) => ({ ...shortcut, group: 'Go to' }));
    }

    const groups = [
      ['Products', results.products],
      ['Invoices', results.sales],
      ['Suppliers', results.suppliers],
      ['Customers', results.customers],
    ];

    return groups.flatMap(([name, rows]) =>
      (rows || []).map((row) => ({
        label: row.label,
        sublabel: row.sublabel,
        link: row.link.replace(/^\//, '/app/'),
        icon: GROUP_ICONS[name.toLowerCase()] || 'search',
        group: name,
      })),
    );
  }, [results, term]);

  useEffect(() => setActive(0), [items.length]);

  if (!open) return null;

  const go = (item) => {
    onClose();
    navigate(item.link);
  };

  function onKeyDown(event) {
    if (event.key === 'Escape') return onClose();
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActive((current) => (current + 1) % Math.max(items.length, 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActive((current) => (current - 1 + items.length) % Math.max(items.length, 1));
    } else if (event.key === 'Enter' && items[active]) {
      event.preventDefault();
      go(items[active]);
    }
    return undefined;
  }

  let lastGroup = null;

  return createPortal(
    <div
      className="modal-backdrop"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-label="Search" onKeyDown={onKeyDown}>
        <div className="u-row" style={{ padding: 'var(--s3) var(--s4)', borderBottom: '1px solid var(--border)' }}>
          <Icon name="search" size={16} className="u-subtle" />
          <input
            ref={input}
            className="input"
            style={{ border: 'none', boxShadow: 'none', height: 32, padding: 0 }}
            placeholder="Search products, invoices, suppliers, customers…"
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            aria-label="Search"
          />
          {loading ? <span className="u-xs u-subtle">Searching…</span> : null}
        </div>

        <div style={{ maxHeight: 380, overflowY: 'auto', padding: 'var(--s1)' }}>
          {items.length === 0 ? (
            <div className="u-center u-muted u-small" style={{ padding: 'var(--s8)' }}>
              {term.trim().length < 3
                ? 'Type at least 3 characters to search'
                : `Nothing matches “${term.trim()}”`}
            </div>
          ) : (
            items.map((item, index) => {
              const showGroup = item.group !== lastGroup;
              lastGroup = item.group;
              return (
                <div key={`${item.link}-${index}`}>
                  {showGroup ? (
                    <div className="sidebar__group-label" style={{ padding: 'var(--s2) var(--s3) var(--s1)' }}>
                      {item.group}
                    </div>
                  ) : null}
                  <button
                    type="button"
                    className={`menu__item${index === active ? ' menu__item--active' : ''}`}
                    onMouseEnter={() => setActive(index)}
                    onClick={() => go(item)}
                  >
                    <Icon name={item.icon} size={14} />
                    <span className="u-grow u-truncate">{item.label}</span>
                    <span className="u-xs u-subtle u-truncate" style={{ maxWidth: '45%' }}>
                      {item.sublabel}
                    </span>
                  </button>
                </div>
              );
            })
          )}
        </div>

        <div className="modal__footer" style={{ justifyContent: 'flex-start', gap: 'var(--s4)' }}>
          <span className="u-xs u-subtle">↑↓ navigate</span>
          <span className="u-xs u-subtle">↵ open</span>
          <span className="u-xs u-subtle">esc close</span>
        </div>
      </div>
    </div>,
    document.body,
  );
}
