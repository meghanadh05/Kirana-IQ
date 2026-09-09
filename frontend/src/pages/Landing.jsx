import { Link } from 'react-router-dom';

import Button from '../components/ui/Button.jsx';
import Icon from '../components/ui/Icon.jsx';

/**
 * The public landing page.
 *
 * Every claim here is one the product can actually demonstrate. There are no
 * customer counts or testimonials, because there are no customers yet — a
 * fabricated "trusted by 10,000 stores" would be the fastest way to lose the
 * first one.
 */

const FEATURES = [
  {
    icon: 'pos',
    title: 'Fast billing',
    text: 'Scan a barcode or search by name, take cash, UPI or card, and print a receipt. Stock drops the moment the sale is saved.',
  },
  {
    icon: 'inventory',
    title: 'Inventory you can explain',
    text: 'Every unit is accounted for by a movement — a sale, a delivery, a damage write-off. Stock levels are never a mystery.',
  },
  {
    icon: 'forecast',
    title: 'Demand forecasting',
    text: 'A model trained on your own sales predicts the next 7, 14 or 30 days per product, including weekend and festival patterns.',
  },
  {
    icon: 'purchases',
    title: 'Reorder recommendations',
    text: 'Forecast demand, supplier lead time and demand volatility become one number: how much to order, and why.',
  },
  {
    icon: 'analytics',
    title: 'Business analytics',
    text: 'Revenue, gross margin, best sellers, dead stock and stock turnover — measured, not estimated.',
  },
  {
    icon: 'suppliers',
    title: 'Supplier purchasing',
    text: 'Turn a recommendation into a purchase order in one click, then receive the delivery and watch stock rise.',
  },
];

const FLOW = [
  { title: 'Sell', text: 'Bill customers at the counter. Every sale is recorded per product, per day.' },
  { title: 'Learn', text: 'That history becomes the training data for your store’s demand model.' },
  { title: 'Forecast', text: 'Predict what each product will sell before the supplier can deliver.' },
  { title: 'Reorder', text: 'Order the right quantity, from the right supplier, at the right time.' },
];

export default function Landing() {
  return (
    <div className="marketing">
      <header className="marketing__nav">
        <div className="marketing__brand">
          <span className="sidebar__mark">K</span>
          Kirana-IQ
        </div>
        <nav className="marketing__nav-links">
          <a href="#features">Features</a>
          <a href="#how">How it works</a>
          <a href="#forecasting">Forecasting</a>
        </nav>
        <div className="marketing__nav-actions">
          <Link to="/login">
            <Button variant="ghost">Sign in</Button>
          </Link>
          <Link to="/register">
            <Button variant="primary">Start free</Button>
          </Link>
        </div>
      </header>

      <section className="hero">
        <h1 className="hero__title">Run your kirana smarter.</h1>
        <p className="hero__lead">
          Forecast demand, prevent stockouts, manage inventory, and bill customers — from one
          retail platform built for small stores.
        </p>
        <div className="hero__actions">
          <Link to="/register">
            <Button variant="primary" size="lg" icon="arrowRight">
              Start free
            </Button>
          </Link>
          <Link to="/login">
            <Button size="lg">View the demo store</Button>
          </Link>
        </div>
        <p className="hero__note">No card required. The demo store comes loaded with a year of sales.</p>

        <ProductPreview />
      </section>

      <section className="section section--tint" id="features">
        <div className="section__inner">
          <span className="section__eyebrow">What you get</span>
          <h2 className="section__title">A complete counter-to-cash-flow system</h2>
          <p className="section__lead">
            Billing, stock, purchasing and analytics in one place — with a forecasting engine
            wired into the parts where it changes a decision.
          </p>

          <div className="feature-grid">
            {FEATURES.map((feature) => (
              <article className="feature" key={feature.title}>
                <div className="feature__icon">
                  <Icon name={feature.icon} size={17} />
                </div>
                <h3 className="feature__title">{feature.title}</h3>
                <p className="feature__text">{feature.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section" id="how">
        <div className="section__inner">
          <span className="section__eyebrow">How it works</span>
          <h2 className="section__title">Selling is what makes the forecast work</h2>
          <p className="section__lead">
            The model has no separate data-entry step. It learns from the invoices you were
            already going to create.
          </p>

          <div className="flow">
            {FLOW.map((step, index) => (
              <div className="flow__step" key={step.title}>
                <span className="flow__index">{index + 1}</span>
                <h3 className="flow__title">{step.title}</h3>
                <p className="flow__text">{step.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section section--tint" id="forecasting">
        <div className="section__inner">
          <div className="grid grid--2" style={{ alignItems: 'center' }}>
            <div>
              <span className="section__eyebrow">Under the hood</span>
              <h2 className="section__title">A forecast you can interrogate</h2>
              <p className="section__lead">
                Gradient-boosted trees over lag, rolling-window, calendar and festival features,
                evaluated chronologically against a moving-average baseline. Recommendations are
                sized with a safety-stock formula, not a guess.
              </p>
              <ul className="u-col u-mt6" style={{ gap: 'var(--s3)' }}>
                {[
                  'Trained per store, on your own sales history',
                  'Leakage-safe features: a prediction only sees the past',
                  'Reported accuracy comes from a held-out test window',
                  'Every recommendation states its reasoning in plain language',
                ].map((line) => (
                  <li key={line} className="u-row u-small">
                    <Icon name="check" size={15} style={{ color: 'var(--success-500)', flexShrink: 0 }} />
                    {line}
                  </li>
                ))}
              </ul>
            </div>

            <div className="card">
              <div className="card__header">
                <div>
                  <div className="card__title">Reorder recommendation</div>
                  <div className="card__subtitle">Example output for one product</div>
                </div>
              </div>
              <div className="card__body u-col" style={{ gap: 'var(--s4)' }}>
                <div className="u-row-between">
                  <div>
                    <div className="u-strong">Dove Soap 100g</div>
                    <div className="u-xs u-muted">PRC-004 · Personal Care</div>
                  </div>
                  <span className="badge badge--danger badge--dot">Critical</span>
                </div>
                <div className="grid grid--3" style={{ gap: 'var(--s3)' }}>
                  {[
                    ['Current stock', '7'],
                    ['Expected demand', '87'],
                    ['Recommended order', '95'],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <div className="u-xs u-muted">{label}</div>
                      <div className="u-strong" style={{ fontSize: 'var(--text-lg)' }}>{value}</div>
                    </div>
                  ))}
                </div>
                <p className="u-small u-muted">
                  Only 0.6 days of stock left and the supplier takes 6 days. This product will very
                  likely run out before replenishment arrives.
                </p>
                <Button variant="primary" icon="purchases">
                  Create purchase order
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section__inner u-center">
          <h2 className="section__title">Set up your store in a few minutes</h2>
          <p className="section__lead" style={{ margin: 'var(--s3) auto 0' }}>
            Add products or import a CSV, enter your opening stock, and start billing.
            The forecasting unlocks once you have a month of sales.
          </p>
          <div className="hero__actions">
            <Link to="/register">
              <Button variant="primary" size="lg">Create your store</Button>
            </Link>
          </div>
        </div>
      </section>

      <footer className="marketing__footer">
        <div className="marketing__footer-inner">
          <div className="u-row">
            <span className="sidebar__mark">K</span>
            <span>Kirana-IQ — intelligent POS &amp; inventory management</span>
          </div>
          <div className="u-row u-gap4">
            <Link to="/login">Sign in</Link>
            <Link to="/register">Start free</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

/** A mock of the overview screen. Static by design — it is a picture, not a demo. */
function ProductPreview() {
  return (
    <div className="preview">
      <div className="preview__chrome">
        <span className="preview__dot" />
        <span className="preview__dot" />
        <span className="preview__dot" />
        <span className="preview__label">Overview — Kirana-IQ</span>
      </div>
      <div className="preview__body">
        <div className="preview__rail">
          {[
            ['overview', 'Overview', true],
            ['pos', 'POS', false],
            ['products', 'Products', false],
            ['inventory', 'Inventory', false],
            ['purchases', 'Purchases', false],
            ['forecast', 'Forecasting', false],
          ].map(([icon, label, active]) => (
            <div
              key={label}
              className={`preview__rail-item${active ? ' preview__rail-item--active' : ''}`}
            >
              <Icon name={icon} size={12} />
              {label}
            </div>
          ))}
        </div>

        <div className="preview__pane">
          <div className="grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--s2)' }}>
            {[
              ["Today's revenue", '₹12,840'],
              ['Orders', '38'],
              ['Low stock', '6'],
              ['Inventory value', '₹6.0L'],
            ].map(([label, value]) => (
              <div key={label} className="stat" style={{ padding: 'var(--s3)' }}>
                <span className="stat__label" style={{ fontSize: 9 }}>{label}</span>
                <span className="stat__value" style={{ fontSize: 'var(--text-md)' }}>{value}</span>
              </div>
            ))}
          </div>

          <div className="card" style={{ flex: 1 }}>
            <div className="card__header" style={{ padding: 'var(--s3) var(--s4)' }}>
              <div className="card__title" style={{ fontSize: 'var(--text-sm)' }}>Revenue, last 7 days</div>
            </div>
            <div className="card__body" style={{ padding: 'var(--s3) var(--s4)' }}>
              <svg viewBox="0 0 300 70" style={{ width: '100%', height: 70 }} aria-hidden="true">
                <path
                  d="M0,52 L50,44 L100,50 L150,30 L200,36 L250,18 L300,24"
                  fill="none" stroke="var(--accent-500)" strokeWidth="2"
                  strokeLinecap="round" strokeLinejoin="round"
                />
                <path
                  d="M0,52 L50,44 L100,50 L150,30 L200,36 L250,18 L300,24 L300,70 L0,70 Z"
                  fill="var(--accent-500)" opacity="0.09"
                />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
