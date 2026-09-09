import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import * as api from '../services/api.js';

const AuthContext = createContext(null);

/**
 * Holds the signed-in user, their stores, and which store is active.
 *
 * The token lives in localStorage so a refresh keeps the session; the user
 * record is always re-fetched from /auth/me rather than trusted from storage,
 * so a deactivated account stops working immediately.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [stores, setStores] = useState([]);
  const [storeId, setStoreIdState] = useState(() => {
    const stored = api.auth.storeId();
    return stored ? Number(stored) : null;
  });
  const [loading, setLoading] = useState(Boolean(api.auth.token()));

  const signOut = useCallback(() => {
    api.auth.clearToken();
    api.auth.clearStoreId();
    setUser(null);
    setStores([]);
    setStoreIdState(null);
  }, []);

  // An expired or revoked token anywhere in the app ends the session.
  useEffect(() => {
    api.setUnauthorizedHandler(signOut);
    return () => api.setUnauthorizedHandler(null);
  }, [signOut]);

  const applySession = useCallback((session) => {
    setUser(session.user);
    setStores(session.stores || []);

    // Keep the active store only if it is still one the user belongs to.
    const ids = (session.stores || []).map((store) => store.id);
    const stored = api.auth.storeId() ? Number(api.auth.storeId()) : null;
    const next = ids.includes(stored) ? stored : ids[0] ?? null;

    if (next) {
      api.auth.setStoreId(next);
    } else {
      api.auth.clearStoreId();
    }
    setStoreIdState(next);
    return session;
  }, []);

  useEffect(() => {
    if (!api.auth.token()) {
      setLoading(false);
      return;
    }
    api
      .getMe()
      .then(applySession)
      .catch(() => signOut())
      .finally(() => setLoading(false));
  }, [applySession, signOut]);

  const signIn = useCallback(
    async (credentials) => {
      const session = await api.login(credentials);
      api.auth.setToken(session.access_token);
      return applySession(session);
    },
    [applySession],
  );

  const signUp = useCallback(
    async (payload) => {
      const session = await api.register(payload);
      api.auth.setToken(session.access_token);
      return applySession(session);
    },
    [applySession],
  );

  const refreshSession = useCallback(
    () => api.getMe().then(applySession),
    [applySession],
  );

  const selectStore = useCallback((id) => {
    api.auth.setStoreId(id);
    setStoreIdState(id);
  }, []);

  const store = useMemo(
    () => stores.find((candidate) => candidate.id === storeId) || null,
    [stores, storeId],
  );

  const value = useMemo(
    () => ({
      user,
      stores,
      store,
      storeId,
      loading,
      role: store?.role ?? null,
      isAuthenticated: Boolean(user),
      signIn,
      signUp,
      signOut,
      selectStore,
      refreshSession,
      setUser,
    }),
    [user, stores, store, storeId, loading, signIn, signUp, signOut, selectStore, refreshSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside an AuthProvider');
  return context;
}

const RANK = { CASHIER: 1, MANAGER: 2, OWNER: 3 };

/** Mirrors the backend's role ladder. Presentation only — the API still decides. */
export function useCan(minimumRole) {
  const { role } = useAuth();
  if (!role) return false;
  return (RANK[role] || 0) >= (RANK[minimumRole] || 0);
}
