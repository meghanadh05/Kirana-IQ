import { Link } from 'react-router-dom';

import Icon from '../../components/ui/Icon.jsx';

const POINTS = [
  'Barcode billing that updates stock as you sell',
  'A stock ledger where every unit is accounted for',
  'Demand forecasts trained on your own sales',
  'Reorder advice that becomes a purchase order in one click',
];

/** The two-column frame shared by sign-in, sign-up and password reset. */
export default function AuthShell({ title, lead, children, footer }) {
  return (
    <div className="auth">
      <div className="auth__panel">
        <div className="auth__form">
          <Link to="/" className="marketing__brand" style={{ marginBottom: 'var(--s8)' }}>
            <span className="sidebar__mark">K</span>
            Kirana-IQ
          </Link>
          <h1 className="auth__title">{title}</h1>
          {lead ? <p className="auth__lead">{lead}</p> : null}
          {children}
          {footer ? <div className="auth__footer">{footer}</div> : null}
        </div>
      </div>

      <aside className="auth__aside">
        <h2 className="auth__aside-title">
          Intelligent POS &amp; inventory management for modern retail.
        </h2>
        <div className="auth__aside-list">
          {POINTS.map((point) => (
            <div className="auth__aside-item" key={point}>
              <Icon name="check" size={15} />
              <span>{point}</span>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
