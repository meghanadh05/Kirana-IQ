import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

import Button from './Button.jsx';
import Icon from './Icon.jsx';

/**
 * A dialog rendered into a portal.
 *
 * Escape closes it, focus moves inside on open, and background scrolling is
 * locked — the three things that make a modal usable rather than merely visible.
 */
export default function Modal({
  open,
  onClose,
  title,
  subtitle,
  size,
  footer,
  children,
  closeOnBackdrop = true,
}) {
  const panel = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

    function onKeyDown(event) {
      if (event.key === 'Escape') onClose?.();
    }
    document.addEventListener('keydown', onKeyDown);

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const focusTarget = panel.current?.querySelector(
      'input:not([type=hidden]), select, textarea, button',
    );
    focusTarget?.focus();

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (closeOnBackdrop && event.target === event.currentTarget) onClose?.();
      }}
    >
      <div
        ref={panel}
        className={`modal${size === 'wide' ? ' modal--wide' : ''}${size === 'narrow' ? ' modal--narrow' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="modal__header">
          <div>
            <div className="modal__title">{title}</div>
            {subtitle ? <div className="modal__subtitle">{subtitle}</div> : null}
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
            <Icon name="close" size={15} />
          </Button>
        </div>
        <div className="modal__body">{children}</div>
        {footer ? <div className="modal__footer">{footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
}

/** A confirmation dialog for actions that are awkward to undo. */
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Confirm',
  destructive = false,
  loading = false,
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="narrow"
      footer={
        <>
          <Button onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            variant={destructive ? 'danger' : 'primary'}
            onClick={onConfirm}
            loading={loading}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="u-small u-muted">{message}</p>
    </Modal>
  );
}
