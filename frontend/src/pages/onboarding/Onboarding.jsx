import { useRef, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';

import Button from '../../components/ui/Button.jsx';
import Icon from '../../components/ui/Icon.jsx';
import { SelectField, TextField } from '../../components/ui/Field.jsx';
import { useAuth } from '../../context/AuthContext.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import * as api from '../../services/api.js';

/**
 * Store setup wizard.
 *
 * Runs after sign-up instead of dropping the user into an empty dashboard. Each
 * step saves as it completes, so a closed tab does not lose the work.
 */
const STEPS = ['Store', 'Preferences', 'Products', 'Done'];

const BUSINESS_TYPES = [
  { value: 'KIRANA', label: 'Kirana' },
  { value: 'GROCERY', label: 'Grocery' },
  { value: 'MINI_SUPERMARKET', label: 'Mini supermarket' },
  { value: 'PHARMACY', label: 'Pharmacy' },
  { value: 'CONVENIENCE_STORE', label: 'Convenience store' },
  { value: 'OTHER', label: 'Other' },
];

const UNITS = ['piece', 'kg', 'gram', 'litre', 'ml', 'packet', 'box'];

export default function Onboarding() {
  const { user, stores, store, selectStore, refreshSession, isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  // Resume where an interrupted setup left off.
  const [step, setStep] = useState(() =>
    store && !store.onboarding_completed ? store.onboarding_step : 1,
  );
  const [storeId, setStoreId] = useState(store && !store.onboarding_completed ? store.id : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  if (!loading && !isAuthenticated) return <Navigate to="/login" replace />;
  // A finished store means there is nothing left to set up.
  if (!loading && store?.onboarding_completed && !storeId) return <Navigate to="/app" replace />;

  return (
    <div className="onboarding">
      <div className="onboarding__inner">
        <div className="marketing__brand">
          <span className="sidebar__mark">K</span>
          Kirana-IQ
        </div>

        <div className="onboarding__steps" aria-label="Setup progress">
          {STEPS.map((label, index) => {
            const position = index + 1;
            const state = position < step ? 'done' : position === step ? 'active' : 'todo';
            return (
              <div className={`onboarding__step onboarding__step--${state}`} key={label}>
                <div className="onboarding__step-bar" />
                <div className="onboarding__step-label">
                  {position}. {label}
                </div>
              </div>
            );
          })}
        </div>

        {error ? (
          <div className="alert alert--error" role="alert" style={{ marginBottom: 'var(--s4)' }}>
            {error}
          </div>
        ) : null}

        {step === 1 ? (
          <StoreStep
            defaultOwner={user?.full_name}
            defaultPhone={user?.phone}
            defaultEmail={user?.email}
            existingId={storeId}
            busy={busy}
            onSubmit={async (values) => {
              setBusy(true);
              setError(null);
              try {
                let id = storeId;
                if (id) {
                  await api.updateStore(id, values);
                } else {
                  const created = await api.createStore(values);
                  id = created.id;
                  setStoreId(id);
                  selectStore(id);
                }
                await api.setOnboardingStep(id, 2);
                await refreshSession();
                setStep(2);
              } catch (err) {
                setError(err.message);
              } finally {
                setBusy(false);
              }
            }}
          />
        ) : null}

        {step === 2 ? (
          <PreferencesStep
            busy={busy}
            onBack={() => setStep(1)}
            onSubmit={async (values) => {
              setBusy(true);
              setError(null);
              try {
                await api.updateStoreSettings(values);
                await api.setOnboardingStep(storeId, 3);
                setStep(3);
              } catch (err) {
                setError(err.message);
              } finally {
                setBusy(false);
              }
            }}
          />
        ) : null}

        {step === 3 ? (
          <ProductsStep
            busy={busy}
            onBack={() => setStep(2)}
            onDone={async () => {
              setBusy(true);
              try {
                await api.setOnboardingStep(storeId, 4);
                await refreshSession();
                setStep(4);
              } catch (err) {
                setError(err.message);
              } finally {
                setBusy(false);
              }
            }}
            onError={(message) => toast.error(message)}
            onSuccess={(message) => toast.success(message)}
          />
        ) : null}

        {step === 4 ? <DoneStep onNavigate={navigate} /> : null}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------- steps

function StoreStep({ defaultOwner, defaultPhone, defaultEmail, existingId, busy, onSubmit }) {
  const [form, setForm] = useState({
    name: '',
    owner_name: defaultOwner || '',
    phone: defaultPhone || '',
    email: defaultEmail || '',
    address: '',
    city: '',
    state: '',
    pin_code: '',
    gst_number: '',
    currency: 'INR',
    business_type: 'KIRANA',
  });

  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  return (
    <form
      className="card"
      onSubmit={(event) => {
        event.preventDefault();
        // Empty optional strings become null, so the API stores absence not "".
        const cleaned = Object.fromEntries(
          Object.entries(form).map(([key, value]) => [key, value === '' ? null : value]),
        );
        onSubmit({ ...cleaned, name: form.name, currency: form.currency });
      }}
    >
      <div className="card__header">
        <div>
          <h2 className="card__title">Tell us about your store</h2>
          <p className="card__subtitle">This appears on your receipts and invoices.</p>
        </div>
      </div>

      <div className="card__body">
        <div className="form-grid">
          <TextField
            label="Store name"
            required
            autoFocus
            className="form-grid__full"
            placeholder="e.g. Sri Balaji Kirana Store"
            value={form.name}
            onChange={set('name')}
          />
          <TextField label="Owner name" value={form.owner_name} onChange={set('owner_name')} />
          <TextField label="Phone" type="tel" value={form.phone} onChange={set('phone')} />
          <TextField label="Email" type="email" optional value={form.email} onChange={set('email')} />
          <SelectField
            label="Business type"
            options={BUSINESS_TYPES}
            value={form.business_type}
            onChange={set('business_type')}
          />
          <TextField
            label="Address"
            optional
            className="form-grid__full"
            value={form.address}
            onChange={set('address')}
          />
          <TextField label="City" value={form.city} onChange={set('city')} />
          <TextField label="State" value={form.state} onChange={set('state')} />
          <TextField
            label="PIN code"
            inputMode="numeric"
            value={form.pin_code}
            onChange={set('pin_code')}
          />
          <TextField
            label="GST number"
            optional
            hint="Printed on invoices when set."
            value={form.gst_number}
            onChange={set('gst_number')}
          />
        </div>
      </div>

      <div className="modal__footer">
        <Button type="submit" variant="primary" loading={busy}>
          {existingId ? 'Save and continue' : 'Create store'}
        </Button>
      </div>
    </form>
  );
}

function PreferencesStep({ busy, onBack, onSubmit }) {
  const [form, setForm] = useState({
    low_stock_threshold: 10,
    default_tax_rate: '0',
    default_lead_time_days: 3,
    invoice_prefix: 'INV',
    financial_year_start_month: 4,
    timezone: 'Asia/Kolkata',
  });

  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  return (
    <form
      className="card"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({
          ...form,
          low_stock_threshold: Number(form.low_stock_threshold),
          default_lead_time_days: Number(form.default_lead_time_days),
          financial_year_start_month: Number(form.financial_year_start_month),
        });
      }}
    >
      <div className="card__header">
        <div>
          <h2 className="card__title">Set your defaults</h2>
          <p className="card__subtitle">
            All of these can be changed later, and per product where it matters.
          </p>
        </div>
      </div>

      <div className="card__body">
        <div className="form-grid">
          <TextField
            label="Low-stock threshold"
            type="number" min="0"
            hint="Default reorder level for new products."
            value={form.low_stock_threshold}
            onChange={set('low_stock_threshold')}
          />
          <TextField
            label="Default tax rate (%)"
            type="number" min="0" max="100" step="0.01"
            hint="Applied to new products unless overridden."
            value={form.default_tax_rate}
            onChange={set('default_tax_rate')}
          />
          <TextField
            label="Supplier lead time (days)"
            type="number" min="0"
            hint="How long a typical delivery takes. Used in reorder advice."
            value={form.default_lead_time_days}
            onChange={set('default_lead_time_days')}
          />
          <TextField
            label="Invoice prefix"
            maxLength={12}
            hint="Invoices are numbered PREFIX-00001."
            value={form.invoice_prefix}
            onChange={set('invoice_prefix')}
          />
          <SelectField
            label="Financial year starts"
            value={form.financial_year_start_month}
            onChange={set('financial_year_start_month')}
            options={[
              { value: 4, label: 'April (India)' },
              { value: 1, label: 'January' },
              { value: 7, label: 'July' },
              { value: 10, label: 'October' },
            ]}
          />
          <SelectField
            label="Timezone"
            value={form.timezone}
            onChange={set('timezone')}
            options={[
              { value: 'Asia/Kolkata', label: 'Asia/Kolkata (IST)' },
              { value: 'Asia/Dubai', label: 'Asia/Dubai' },
              { value: 'UTC', label: 'UTC' },
            ]}
          />
        </div>
      </div>

      <div className="modal__footer">
        <Button onClick={onBack} disabled={busy}>Back</Button>
        <Button type="submit" variant="primary" loading={busy}>Continue</Button>
      </div>
    </form>
  );
}

function ProductsStep({ busy, onBack, onDone, onError, onSuccess }) {
  const [mode, setMode] = useState(null);
  const [added, setAdded] = useState(0);
  const [importing, setImporting] = useState(false);
  const fileInput = useRef(null);

  const [product, setProduct] = useState({
    sku: '', name: '', category: '', selling_price: '', cost_price: '',
    current_stock: '', reorder_level: '', unit: 'piece',
  });

  const set = (key) => (event) => setProduct({ ...product, [key]: event.target.value });

  async function addProduct(event) {
    event.preventDefault();
    try {
      await api.createProduct({
        sku: product.sku,
        name: product.name,
        category: product.category || 'Uncategorised',
        unit: product.unit,
        selling_price: product.selling_price || '0',
        cost_price: product.cost_price || '0',
        current_stock: Number(product.current_stock || 0),
        reorder_level: Number(product.reorder_level || 0),
      });
      setAdded((count) => count + 1);
      onSuccess(`${product.name} added`);
      setProduct({
        ...product, sku: '', name: '', selling_price: '', cost_price: '', current_stock: '',
      });
    } catch (err) {
      onError(err.message);
    }
  }

  async function importCsv(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    setImporting(true);
    try {
      const result = await api.importProducts(file);
      setAdded((count) => count + result.created + result.updated);
      if (result.failed) {
        onError(`${result.created} imported, ${result.failed} row(s) had problems.`);
      } else {
        onSuccess(`${result.created} products imported`);
      }
    } catch (err) {
      onError(err.message);
    } finally {
      setImporting(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  }

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2 className="card__title">Add your products</h2>
          <p className="card__subtitle">
            {added > 0
              ? `${added} product${added === 1 ? '' : 's'} added so far.`
              : 'Add a few by hand, import a CSV, or skip and do it later.'}
          </p>
        </div>
      </div>

      <div className="card__body u-col u-gap4">
        {mode === null ? (
          <div className="choice-grid">
            <button type="button" className="choice" onClick={() => setMode('manual')}>
              <Icon name="plus" size={16} />
              <div style={{ marginTop: 6 }}>Add manually</div>
              <span className="choice__hint">Type in your first few products</span>
            </button>
            <button type="button" className="choice" onClick={() => fileInput.current?.click()}>
              <Icon name="upload" size={16} />
              <div style={{ marginTop: 6 }}>Import CSV</div>
              <span className="choice__hint">Bring an existing catalogue</span>
            </button>
            <button type="button" className="choice" onClick={onDone}>
              <Icon name="arrowRight" size={16} />
              <div style={{ marginTop: 6 }}>Skip for now</div>
              <span className="choice__hint">Add products later</span>
            </button>
          </div>
        ) : null}

        <input
          ref={fileInput}
          type="file"
          accept=".csv,text/csv"
          onChange={importCsv}
          className="u-visually-hidden"
        />

        {importing ? <div className="alert alert--info">Importing your catalogue…</div> : null}

        {mode === 'manual' ? (
          <form onSubmit={addProduct} className="u-col u-gap4">
            <div className="form-grid">
              <TextField label="SKU" required value={product.sku} onChange={set('sku')} placeholder="DRY-001" />
              <TextField label="Name" required value={product.name} onChange={set('name')} placeholder="Amul Milk 1L" />
              <TextField label="Category" required value={product.category} onChange={set('category')} placeholder="Dairy" />
              <SelectField
                label="Unit"
                value={product.unit}
                onChange={set('unit')}
                options={UNITS.map((unit) => ({ value: unit, label: unit }))}
              />
              <TextField label="Selling price" type="number" min="0" step="0.01" required value={product.selling_price} onChange={set('selling_price')} />
              <TextField label="Cost price" type="number" min="0" step="0.01" value={product.cost_price} onChange={set('cost_price')} />
              <TextField label="Opening stock" type="number" min="0" value={product.current_stock} onChange={set('current_stock')} />
              <TextField label="Reorder level" type="number" min="0" value={product.reorder_level} onChange={set('reorder_level')} />
            </div>
            <div className="u-row">
              <Button type="submit" variant="primary" icon="plus">Add product</Button>
              <Button onClick={() => setMode(null)}>Choose another way</Button>
            </div>
          </form>
        ) : null}

        <div className="alert alert--info">
          <Icon name="info" size={15} style={{ flexShrink: 0 }} />
          <span>
            Forecasting needs at least 31 days of sales per product. Until then Kirana-IQ still
            tracks stock, sales and reorder levels.
          </span>
        </div>
      </div>

      <div className="modal__footer">
        <Button onClick={onBack} disabled={busy}>Back</Button>
        <Button variant="primary" onClick={onDone} loading={busy}>
          {added > 0 ? 'Finish setup' : 'Skip and finish'}
        </Button>
      </div>
    </div>
  );
}

function DoneStep({ onNavigate }) {
  return (
    <div className="card">
      <div className="card__body u-center u-col" style={{ gap: 'var(--s4)', padding: 'var(--s10)' }}>
        <div
          className="state__icon"
          style={{ background: 'var(--success-100)', color: 'var(--success-600)', margin: '0 auto' }}
        >
          <Icon name="check" size={22} />
        </div>
        <h2 style={{ fontSize: 'var(--text-xl)' }}>Your store is ready</h2>
        <p className="u-muted u-small" style={{ maxWidth: '46ch', margin: '0 auto' }}>
          Start billing at the counter and your sales history builds itself. Once there is enough
          of it, forecasting and reorder recommendations switch on.
        </p>
        <div className="u-row" style={{ justifyContent: 'center', marginTop: 'var(--s3)' }}>
          <Button variant="primary" size="lg" icon="pos" onClick={() => onNavigate('/app/pos')}>
            Open POS
          </Button>
          <Button size="lg" onClick={() => onNavigate('/app')}>
            View dashboard
          </Button>
        </div>
      </div>
    </div>
  );
}
