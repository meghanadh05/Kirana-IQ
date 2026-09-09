/** Labelled form controls. One markup shape for every input in the app. */

let sequence = 0;
const nextId = () => {
  sequence += 1;
  return `field-${sequence}`;
};

export function Field({ label, hint, error, optional = false, children, id, className = '' }) {
  const fieldId = id || nextId();
  return (
    <div className={`field ${className}`}>
      {label ? (
        <label className="field__label" htmlFor={fieldId}>
          {label}
          {optional ? <span className="field__optional"> (optional)</span> : null}
        </label>
      ) : null}
      {typeof children === 'function' ? children(fieldId) : children}
      {error ? (
        <span className="field__error">{error}</span>
      ) : hint ? (
        <span className="field__hint">{hint}</span>
      ) : null}
    </div>
  );
}

export function TextField({ label, hint, error, optional, className, ...rest }) {
  return (
    <Field label={label} hint={hint} error={error} optional={optional} className={className}>
      {(id) => (
        <input
          id={id}
          className={`input${error ? ' input--invalid' : ''}`}
          aria-invalid={error ? 'true' : undefined}
          {...rest}
        />
      )}
    </Field>
  );
}

export function SelectField({ label, hint, error, optional, options = [], className, ...rest }) {
  return (
    <Field label={label} hint={hint} error={error} optional={optional} className={className}>
      {(id) => (
        <select id={id} className={`select${error ? ' select--invalid' : ''}`} {...rest}>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  );
}

export function TextAreaField({ label, hint, error, optional, className, ...rest }) {
  return (
    <Field label={label} hint={hint} error={error} optional={optional} className={className}>
      {(id) => <textarea id={id} className="textarea" {...rest} />}
    </Field>
  );
}
