import { Link } from 'react-router-dom';

import Icon from '../ui/Icon.jsx';

export default function PageHeader({ title, subtitle, actions, breadcrumb }) {
  return (
    <div className="page__header">
      <div>
        {breadcrumb ? (
          <nav className="breadcrumb" aria-label="Breadcrumb">
            {breadcrumb.map((crumb, index) => (
              <span key={crumb.label} className="u-row" style={{ gap: 4 }}>
                {index > 0 ? <Icon name="chevronRight" size={11} /> : null}
                {crumb.to ? <Link to={crumb.to}>{crumb.label}</Link> : <span>{crumb.label}</span>}
              </span>
            ))}
          </nav>
        ) : null}
        <h1 className="page__title">{title}</h1>
        {subtitle ? <p className="page__subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="page__actions">{actions}</div> : null}
    </div>
  );
}
