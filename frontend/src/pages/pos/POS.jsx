import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import CheckoutModal from './CheckoutModal.jsx';
import Button from '../../components/ui/Button.jsx';
import Icon from '../../components/ui/Icon.jsx';
import { AsyncSection, EmptyState } from '../../components/ui/States.jsx';
import { useApi } from '../../hooks/useApi.js';
import { useDebounce } from '../../hooks/useDebounce.js';
import { useHotkey } from '../../hooks/useHotkey.js';
import { useToast } from '../../context/ToastContext.jsx';
import * as api from '../../services/api.js';
import { currency } from '../../lib/format.js';

/**
 * The till.
 *
 * The scan field owns focus by default and takes it back after every action: a
 * keyboard-wedge barcode scanner types the code and presses Enter, so if focus
 * has wandered the scan is simply lost. That single behaviour is what makes the
 * screen usable at a real counter.
 */
export default function POS() {
  const toast = useToast();
  const navigate = useNavigate();
  const scanField = useRef(null);

  const [scan, setScan] = useState('');
  const [term, setTerm] = useState('');
  const [category, setCategory] = useState(null);
  const [cart, setCart] = useState([]);
  const [held, setHeld] = useState([]);
  const [checkoutOpen, setCheckoutOpen] = useState(false);

  const debouncedTerm = useDebounce(term, 200);

  const products = useApi(
    () =>
      api.listProducts({
        search: debouncedTerm || undefined,
        category: category || undefined,
        limit: 60,
        sort: 'name',
      }),
    [debouncedTerm, category],
  );
  const categories = useApi(() => api.getProductCategories(), []);

  const focusScan = useCallback(() => scanField.current?.focus(), []);
  useEffect(() => focusScan(), [focusScan]);

  useHotkey('mod+enter', () => cart.length > 0 && setCheckoutOpen(true), { allowInInput: true });
  useHotkey('mod+b', focusScan, { allowInInput: true });

  const addToCart = useCallback(
    (product, quantity = 1) => {
      if (!product.is_active) {
        toast.error(`${product.name} is archived and cannot be sold`);
        return;
      }

      setCart((current) => {
        const existing = current.find((line) => line.product_id === product.id);
        const nextQuantity = (existing?.quantity || 0) + quantity;

        // Blocked here as well as on the server: a cashier should find out
        // before the customer is waiting for a receipt.
        if (nextQuantity > product.current_stock) {
          toast.error(`Only ${product.current_stock} of ${product.name} in stock`);
          return current;
        }

        if (existing) {
          return current.map((line) =>
            line.product_id === product.id ? { ...line, quantity: nextQuantity } : line,
          );
        }
        return [
          ...current,
          {
            product_id: product.id,
            name: product.name,
            sku: product.sku,
            unit: product.unit,
            unit_price: Number(product.selling_price),
            tax_rate: Number(product.tax_rate),
            stock: product.current_stock,
            quantity,
          },
        ];
      });
    },
    [toast],
  );

  async function onScanSubmit(event) {
    event.preventDefault();
    const code = scan.trim();
    if (!code) return;

    try {
      const product = await api.lookupBarcode(code);
      addToCart(product);
      setScan('');
    } catch (error) {
      // Not a barcode or SKU — fall back to treating it as a search term.
      toast.error(error.status === 404 ? `No product matches “${code}”` : error.message);
      setTerm(code);
      setScan('');
    }
    focusScan();
  }

  const setQuantity = (productId, quantity) =>
    setCart((current) =>
      current
        .map((line) =>
          line.product_id === productId
            ? { ...line, quantity: Math.max(0, Math.min(quantity, line.stock)) }
            : line,
        )
        .filter((line) => line.quantity > 0),
    );

  const removeLine = (productId) =>
    setCart((current) => current.filter((line) => line.product_id !== productId));

  const totals = useMemo(() => {
    const subtotal = cart.reduce((sum, line) => sum + line.unit_price * line.quantity, 0);
    const tax = cart.reduce(
      (sum, line) => sum + (line.unit_price * line.quantity * line.tax_rate) / 100,
      0,
    );
    return { subtotal, tax, total: subtotal + tax, units: cart.reduce((sum, line) => sum + line.quantity, 0) };
  }, [cart]);

  function holdSale() {
    if (cart.length === 0) return;
    setHeld((current) => [...current, { id: Date.now(), lines: cart, at: new Date() }]);
    setCart([]);
    toast.success('Sale held');
    focusScan();
  }

  function resumeSale(saleId) {
    const sale = held.find((candidate) => candidate.id === saleId);
    if (!sale) return;
    setCart(sale.lines);
    setHeld((current) => current.filter((candidate) => candidate.id !== saleId));
    focusScan();
  }

  const productRows = products.data?.items || [];

  return (
    <div className="pos">
      <div className="pos__catalogue">
        <div className="pos__scan">
          {/* The scan field is its own form. A form with several inputs and no
              submit button does not submit on Enter, which is exactly the key a
              barcode scanner presses. */}
          <form className="pos__scan-field" onSubmit={onScanSubmit}>
            <Icon name="barcode" size={18} />
            <input
              ref={scanField}
              className="input"
              placeholder="Scan barcode or type a SKU, then press Enter"
              value={scan}
              onChange={(event) => setScan(event.target.value)}
              aria-label="Scan barcode"
              autoComplete="off"
            />
            <button type="submit" className="u-visually-hidden">
              Look up barcode
            </button>
          </form>

          <div className="search-input" style={{ flex: 1 }}>
            <Icon name="search" size={15} />
            <input
              className="input"
              style={{ height: 42 }}
              placeholder="Search products by name"
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              aria-label="Search products"
            />
          </div>
        </div>

        {categories.data?.length ? (
          <div className="pos__filters">
            <button
              type="button"
              className={`pos__chip${category === null ? ' pos__chip--active' : ''}`}
              onClick={() => setCategory(null)}
            >
              All
            </button>
            {categories.data.map((name) => (
              <button
                key={name}
                type="button"
                className={`pos__chip${category === name ? ' pos__chip--active' : ''}`}
                onClick={() => setCategory(category === name ? null : name)}
              >
                {name}
              </button>
            ))}
          </div>
        ) : null}

        <div className="pos__products">
          <AsyncSection
            loading={products.loading}
            error={products.error}
            onRetry={products.reload}
            isEmpty={productRows.length === 0}
            skeleton={
              <div className="pos__grid">
                {Array.from({ length: 12 }).map((_, index) => (
                  <div key={index} className="skeleton" style={{ height: 96 }} />
                ))}
              </div>
            }
            empty={
              <EmptyState
                inline
                icon="products"
                title={term || category ? 'No products match' : 'No products yet'}
                message={
                  term || category
                    ? 'Try a different search or clear the category filter.'
                    : 'Add your first product to start selling.'
                }
                actions={
                  term || category ? (
                    <Button
                      onClick={() => {
                        setTerm('');
                        setCategory(null);
                      }}
                    >
                      Clear filters
                    </Button>
                  ) : (
                    <Button variant="primary" icon="plus" onClick={() => navigate('/app/products')}>
                      Add a product
                    </Button>
                  )
                }
              />
            }
          >
            <div className="pos__grid">
              {productRows.map((product) => {
                const out = product.current_stock <= 0;
                const low = !out && product.current_stock <= product.reorder_level;
                return (
                  <button
                    key={product.id}
                    type="button"
                    className="pos-tile"
                    disabled={out}
                    onClick={() => {
                      addToCart(product);
                      focusScan();
                    }}
                    title={out ? 'Out of stock' : `Add ${product.name}`}
                  >
                    <span className="pos-tile__name">{product.name}</span>
                    <span className="pos-tile__meta">
                      <span className="pos-tile__price">{currency(product.selling_price)}</span>
                      <span
                        className={`pos-tile__stock${low ? ' pos-tile__stock--low' : ''}${out ? ' pos-tile__stock--out' : ''}`}
                      >
                        {out ? 'Out' : `${product.current_stock} ${product.unit}`}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </AsyncSection>
        </div>
      </div>

      <div className="cart">
        {held.length > 0 ? (
          <div className="held-bar">
            <span className="u-strong u-nowrap">Held:</span>
            {held.map((sale) => (
              <button
                key={sale.id}
                type="button"
                className="pos__chip"
                onClick={() => resumeSale(sale.id)}
              >
                {sale.lines.length} item{sale.lines.length === 1 ? '' : 's'} · resume
              </button>
            ))}
          </div>
        ) : null}

        <div className="cart__header">
          <div className="u-row">
            <Icon name="cart" size={16} />
            <span className="u-strong">Current sale</span>
            {cart.length > 0 ? (
              <span className="badge badge--accent">{totals.units}</span>
            ) : null}
          </div>
          {cart.length > 0 ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setCart([]);
                focusScan();
              }}
            >
              Clear
            </Button>
          ) : null}
        </div>

        <div className="cart__items">
          {cart.length === 0 ? (
            <div className="cart__empty">
              <Icon name="barcode" size={26} className="u-subtle" />
              <div>Scan a barcode or tap a product to begin.</div>
              <div className="u-xs u-subtle">The scan field stays focused for you.</div>
            </div>
          ) : (
            cart.map((line) => (
              <div className="cart-line" key={line.product_id}>
                <div className="cart-line__top">
                  <div className="u-grow">
                    <div className="cart-line__name">{line.name}</div>
                    <div className="cart-line__meta">
                      {line.sku} · {currency(line.unit_price)} each
                      {line.tax_rate > 0 ? ` · ${line.tax_rate}% tax` : ''}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="icon-button"
                    style={{ width: 24, height: 24 }}
                    onClick={() => removeLine(line.product_id)}
                    aria-label={`Remove ${line.name}`}
                  >
                    <Icon name="close" size={13} />
                  </button>
                </div>

                <div className="cart-line__bottom">
                  <div className="stepper">
                    <button
                      type="button"
                      onClick={() => setQuantity(line.product_id, line.quantity - 1)}
                      aria-label="Decrease quantity"
                    >
                      <Icon name="minus" size={13} />
                    </button>
                    <input
                      type="number"
                      className="stepper__value"
                      value={line.quantity}
                      min="1"
                      max={line.stock}
                      onChange={(event) =>
                        setQuantity(line.product_id, Number(event.target.value) || 0)
                      }
                      aria-label={`Quantity of ${line.name}`}
                    />
                    <button
                      type="button"
                      onClick={() => setQuantity(line.product_id, line.quantity + 1)}
                      disabled={line.quantity >= line.stock}
                      aria-label="Increase quantity"
                    >
                      <Icon name="plus" size={13} />
                    </button>
                  </div>
                  <span className="cart-line__total">
                    {currency(line.unit_price * line.quantity)}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="cart__summary">
          <div className="cart__row">
            <span>Subtotal</span>
            <span>{currency(totals.subtotal)}</span>
          </div>
          <div className="cart__row">
            <span>Tax</span>
            <span>{currency(totals.tax)}</span>
          </div>
          <div className="cart__row cart__row--total">
            <span>Total</span>
            <span>{currency(totals.total)}</span>
          </div>

          <div className="cart__actions">
            <Button onClick={holdSale} disabled={cart.length === 0}>
              Hold
            </Button>
            <Button
              variant="primary"
              className="u-grow"
              disabled={cart.length === 0}
              onClick={() => setCheckoutOpen(true)}
            >
              Checkout · {currency(totals.total)}
            </Button>
          </div>
        </div>
      </div>

      <CheckoutModal
        open={checkoutOpen}
        cart={cart}
        totals={totals}
        onClose={() => {
          setCheckoutOpen(false);
          focusScan();
        }}
        onComplete={(sale) => {
          setCheckoutOpen(false);
          setCart([]);
          products.reload();
          navigate(`/app/sales/${sale.id}?receipt=1`);
        }}
      />
    </div>
  );
}
