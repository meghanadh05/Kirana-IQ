import { useState } from 'react';
import { Link } from 'react-router-dom';

import PageHeader from '../../components/layout/PageHeader.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Icon from '../../components/ui/Icon.jsx';
import Badge from '../../components/ui/Badge.jsx';
import { AsyncSection, EmptyState } from '../../components/ui/States.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';
import { relativeTime, titleCase } from '../../lib/format.js';

const TONE = {
  CRITICAL: 'danger',
  STOCK: 'warn',
  PURCHASE: 'info',
  ANOMALY: 'accent',
  SYSTEM: 'neutral',
};

const ICONS = {
  CRITICAL: 'warning',
  STOCK: 'package',
  PURCHASE: 'purchases',
  ANOMALY: 'trending',
  SYSTEM: 'info',
};

export default function Alerts() {
  const toast = useToast();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const notifications = useApi(
    () => api.listNotifications({ unread_only: unreadOnly || undefined, limit: 100 }),
    [unreadOnly],
  );

  async function refresh() {
    setRefreshing(true);
    try {
      const result = await api.refreshNotifications();
      toast.success(`Checked stock, forecasts and open orders — ${result.unread} unread`);
      notifications.reload();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setRefreshing(false);
    }
  }

  const rows = notifications.data?.items || [];

  return (
    <div className="page">
      <PageHeader
        title="Alerts"
        subtitle="Stock warnings, demand anomalies and pending deliveries in one place."
        actions={
          <>
            <Button
              onClick={async () => {
                await api.markAllNotificationsRead();
                notifications.reload();
              }}
              disabled={!notifications.data?.unread}
            >
              Mark all read
            </Button>
            <Button variant="primary" icon="refresh" loading={refreshing} onClick={refresh}>
              Check now
            </Button>
          </>
        }
      />

      <Card flush>
        <div className="toolbar">
          <div className="segment">
            <button
              type="button"
              className={`segment__option${!unreadOnly ? ' segment__option--active' : ''}`}
              onClick={() => setUnreadOnly(false)}
            >
              All
            </button>
            <button
              type="button"
              className={`segment__option${unreadOnly ? ' segment__option--active' : ''}`}
              onClick={() => setUnreadOnly(true)}
            >
              Unread {notifications.data?.unread ? `(${notifications.data.unread})` : ''}
            </button>
          </div>
        </div>

        <AsyncSection
          loading={notifications.loading}
          error={notifications.error}
          onRetry={notifications.reload}
          isEmpty={rows.length === 0}
          empty={
            <EmptyState
              icon="check"
              title={unreadOnly ? 'Nothing unread' : 'No alerts'}
              message="Kirana-IQ raises an alert when a product is running out, demand moves unexpectedly, or a delivery is due."
              actions={
                <Button icon="refresh" loading={refreshing} onClick={refresh}>
                  Check now
                </Button>
              }
            />
          }
        >
          <ul>
            {rows.map((row) => (
              <li
                key={row.id}
                style={{
                  display: 'flex',
                  gap: 'var(--s4)',
                  padding: 'var(--s4) var(--s5)',
                  borderBottom: '1px solid var(--grey-100)',
                  background: row.is_read ? 'transparent' : 'var(--accent-50)',
                }}
              >
                <Icon
                  name={ICONS[row.type] || 'info'}
                  size={17}
                  style={{ flexShrink: 0, marginTop: 2, color: 'var(--grey-500)' }}
                />
                <div className="u-grow">
                  <div className="u-row">
                    <Badge tone={TONE[row.type] || 'neutral'}>{titleCase(row.type)}</Badge>
                    <span className="u-small u-strong">{row.title}</span>
                  </div>
                  <p className="u-small u-muted" style={{ marginTop: 3 }}>
                    {row.message}
                  </p>
                  <div className="u-row" style={{ marginTop: 'var(--s2)' }}>
                    <span className="u-xs u-subtle">{relativeTime(row.created_at)}</span>
                    {row.link ? (
                      <Link className="u-xs" to={row.link.replace(/^\//, '/app/')}>
                        Take action
                      </Link>
                    ) : null}
                    {!row.is_read ? (
                      <button
                        type="button"
                        className="u-xs"
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--text-muted)',
                          padding: 0,
                        }}
                        onClick={async () => {
                          await api.markNotificationRead(row.id);
                          notifications.reload();
                        }}
                      >
                        Mark read
                      </button>
                    ) : null}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </AsyncSection>
      </Card>
    </div>
  );
}
