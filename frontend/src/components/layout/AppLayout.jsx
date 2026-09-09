import { useCallback, useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import CommandBar from './CommandBar.jsx';
import NotificationPanel from './NotificationPanel.jsx';
import Sidebar from './Sidebar.jsx';
import Topbar from './Topbar.jsx';
import { Loading } from '../ui/States.jsx';
import { useAuth } from '../../context/AuthContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import { useHotkey } from '../../hooks/useHotkey.js';
import * as api from '../../services/api.js';
import { setCurrency } from '../../lib/format.js';

/**
 * The signed-in shell.
 *
 * Also the gate: no session sends you to sign-in, and a store that has not
 * finished onboarding sends you back into the wizard rather than into an empty
 * dashboard.
 */
export default function AppLayout() {
  const { isAuthenticated, loading, store, stores } = useAuth();
  const location = useLocation();

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const notifications = useApi(
    () => api.listNotifications({ limit: 30 }),
    [store?.id],
    { enabled: Boolean(store) },
  );

  useHotkey('mod+k', () => setSearchOpen(true), { allowInInput: true });

  // Close the mobile drawer whenever navigation happens.
  useEffect(() => setSidebarOpen(false), [location.pathname]);

  useEffect(() => {
    if (store?.currency) setCurrency(store.currency);
  }, [store?.currency]);

  const refreshNotifications = useCallback(async () => {
    setRefreshing(true);
    try {
      await api.refreshNotifications();
      notifications.reload();
    } finally {
      setRefreshing(false);
    }
  }, [notifications]);

  const markRead = useCallback(
    async (id) => {
      await api.markNotificationRead(id);
      notifications.reload();
    },
    [notifications],
  );

  const markAllRead = useCallback(async () => {
    await api.markAllNotificationsRead();
    notifications.reload();
  }, [notifications]);

  if (loading) {
    return (
      <div style={{ display: 'grid', placeItems: 'center', minHeight: '100vh' }}>
        <Loading label="Loading your store" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  // No store, or an unfinished one: the wizard, not a dashboard with nothing in it.
  if (stores.length === 0 || (store && !store.onboarding_completed)) {
    return <Navigate to="/onboarding" replace />;
  }

  const unread = notifications.data?.unread ?? 0;

  return (
    <div className="shell">
      <Sidebar open={sidebarOpen} onNavigate={() => setSidebarOpen(false)} alertCount={unread} />
      {sidebarOpen ? (
        <div className="sidebar-scrim" onClick={() => setSidebarOpen(false)} aria-hidden="true" />
      ) : null}

      <div className="main">
        <Topbar
          unread={unread}
          onOpenSearch={() => setSearchOpen(true)}
          onOpenNotifications={() => setNotificationsOpen(true)}
          onToggleSidebar={() => setSidebarOpen((open) => !open)}
        />
        <Outlet />
      </div>

      <CommandBar open={searchOpen} onClose={() => setSearchOpen(false)} />
      <NotificationPanel
        open={notificationsOpen}
        onClose={() => setNotificationsOpen(false)}
        notifications={notifications.data?.items || []}
        unread={unread}
        loading={notifications.loading}
        refreshing={refreshing}
        onRefresh={refreshNotifications}
        onMarkRead={markRead}
        onMarkAllRead={markAllRead}
      />
    </div>
  );
}
