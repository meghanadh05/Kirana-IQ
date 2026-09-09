import Icon from './Icon.jsx';

const VARIANTS = {
  primary: 'btn--primary',
  secondary: 'btn--secondary',
  ghost: 'btn--ghost',
  danger: 'btn--danger',
  dangerGhost: 'btn--danger-ghost',
};

export default function Button({
  variant = 'secondary',
  size,
  icon,
  loading = false,
  block = false,
  children,
  className = '',
  disabled,
  type = 'button',
  ...rest
}) {
  const classes = [
    'btn',
    VARIANTS[variant] || VARIANTS.secondary,
    size === 'sm' && 'btn--sm',
    size === 'lg' && 'btn--lg',
    block && 'btn--block',
    !children && 'btn--icon',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button type={type} className={classes} disabled={disabled || loading} {...rest}>
      {loading ? <Spinner /> : icon ? <Icon name={icon} size={size === 'sm' ? 13 : 15} /> : null}
      {children}
    </button>
  );
}

function Spinner() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
      <circle
        cx="12" cy="12" r="9"
        fill="none" stroke="currentColor" strokeWidth="3" opacity="0.25"
      />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"
      >
        <animateTransform
          attributeName="transform" type="rotate"
          from="0 12 12" to="360 12 12" dur="0.7s" repeatCount="indefinite"
        />
      </path>
    </svg>
  );
}
