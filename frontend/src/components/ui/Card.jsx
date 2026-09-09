/** A titled panel. Used for every grouped block in the app. */
export default function Card({ title, subtitle, actions, footer, flush = false, children, className = '' }) {
  return (
    <section className={`card ${className}`}>
      {title || actions ? (
        <header className="card__header">
          <div>
            <h3 className="card__title">{title}</h3>
            {subtitle ? <p className="card__subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="u-row">{actions}</div> : null}
        </header>
      ) : null}
      <div className={`card__body${flush ? ' card__body--flush' : ''}`}>{children}</div>
      {footer ? <div className="card__footer">{footer}</div> : null}
    </section>
  );
}
