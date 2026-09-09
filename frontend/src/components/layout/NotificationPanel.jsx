import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';

import Button from '../ui/Button.jsx';
import Icon from '../ui/Icon.jsx';
import { EmptyState } from '../ui/States.jsx';
import { relativeTime } from '../../lib/format.js';

const TONE = {
  CRITICAL: { icon: 'warning', color: 'var(--danger-600)', background: 'var(--danger-50)' },
  STOCK: { icon: 'package', color: 'var(--warn-600)', background: 'var(--warn-50)' },
  PURCHASE: { icon: 'purchases', color: 'var(--info-500)', background: 'var(--info-50)' },
  ANOMALY: { icon: 'trending', color: 'var(--accent-600)', background: 'var(--accent-50)' },
  SYSTEM: { icon: 'info', color: 'var(--grey-500)', background: 'var(--grey-100)' },
};

export default function NotificationPanel({
  open,
  onClose,
  notifications = [],
  unread = 0,
  loading,
  onMarkRead,
  onMarkAllRead,
  onRefresh,
  refreshing,
}) {
  if (!open) return null;

  return createPortal(
    <div
      className="modal-backdrop"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-label="Notifications">
        <div className="modal__header">
          <div>
            <div className="modal__title">Notifications</div>
            <div className="modal__subtitle">
              {unread > 0 ? `${unread} unread` : 'You are up to date'}
            </div>
          </div>
          <div className="u-row">
            <Button size="sm" icon="refresh" onClick={onRefresh} loading={refreshing}>
              Refresh
            </Button>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
              <Icon name="close" size={15} />
            </Button>
          </div>
        </div>

        <div style={{ maxHeight: 440, overflowY: 'auto' }}>
          {loading ? (
            <div className="u-col" style={{ padding: 'var(--s5)', gap: 'var(--s3)' }}>
              {[0, 1, 2].map((index) => (
                <div key={index} className="skeleton" style={{ height: 46 }} />
              ))}
            </div>
          ) : notifications.length === 0 ? (
            <EmptyState
              inline
              icon="check"
              title="Nothing needs your attention"
              message="Stock warnings, demand anomalies and pending deliveries appear here."
              actions={
                <Button size="sm" icon="refresh" onClick={onRefresh} loading={refreshing}>
                  Check now
                </Button>
              }
            />
          ) : (
            notifications.map((notification) => {
              const tone = TONE[notification.type] || TONE.SYSTEM;
              return (
                <div
                  key={notification.id}
                  style={{
                    display: 'flex',
                    gap: 'var(--s3)',
                    padding: 'var(--s4) var(--s5)',
                    borderBottom: '1px solid var(--grey-100)',
                    background: notification.is_read ? 'transparent' : 'var(--accent-50)',
                  }}
                >
                  <span
                    style={{
                      display: 'grid',
                      placeItems: 'center',
                      width: 28,
                      height: 28,
                      flexShrink: 0,
                      borderRadius: 'var(--radius)',
                      background: tone.background,
                      color: tone.color,
                    }}
                  >
                    <Icon name={tone.icon} size={14} />
                  </span>
                  <div className="u-grow">
                    <div className="u-small u-strong">{notification.title}</div>
                    <p className="u-xs u-muted" style={{ marginTop: 2 }}>
                      {notification.message}
                    </p>
                    <div className="u-row" style={{ marginTop: 'var(--s2)' }}>
                      <span className="u-xs u-subtle">{relativeTime(notification.created_at)}</span>
                      {notification.link ? (
                        <Link
                          className="u-xs"
                          to={notification.link.replace(/^\//, '/app/')}
                          onClick={onClose}
                        >
                          View
                        </Link>
                      ) : null}
                      {!notification.is_read ? (
                        <button
                          type="button"
                          className="u-xs"
                          style={{ background: 'none', border: 'none', color: 'var(--text-muted)', padding: 0 }}
                          onClick={() => onMarkRead(notification.id)}
                        >
                          Mark read
                        </button>
                      ) : null}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {notifications.length > 0 && unread > 0 ? (
          <div className="modal__footer">
            <Button size="sm" onClick={onMarkAllRead}>
              Mark all as read
            </Button>
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}
