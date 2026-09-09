/**
 * API client.
 *
 * One place knows about the base URL, the bearer token and the active store
 * header. Components call named functions and never assemble a URL themselves —
 * that is what keeps request logic out of the React tree.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const TOKEN_KEY = 'kiranaiq.token';
const STORE_KEY = 'kiranaiq.store';

let onUnauthorized = null;

/** Called when the API rejects our token, so the app can sign the user out. */
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

export const auth = {
  token: () => localStorage.getItem(TOKEN_KEY),
  setToken: (token) => localStorage.setItem(TOKEN_KEY, token),
  clearToken: () => localStorage.removeItem(TOKEN_KEY),
  storeId: () => localStorage.getItem(STORE_KEY),
  setStoreId: (id) => localStorage.setItem(STORE_KEY, String(id)),
  clearStoreId: () => localStorage.removeItem(STORE_KEY),
};

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

function headers(extra = {}) {
  const result = { ...extra };
  const token = auth.token();
  const storeId = auth.storeId();
  if (token) result.Authorization = `Bearer ${token}`;
  if (storeId) result['X-Store-Id'] = storeId;
  return result;
}

/**
 * FastAPI reports validation problems as a list of objects under `detail`.
 * Flatten it into one readable sentence rather than showing raw JSON.
 */
function readDetail(body, fallback) {
  const detail = body?.detail;
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : null;
        return field ? `${field}: ${item.msg}` : item.msg;
      })
      .join('; ');
  }
  return fallback;
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers: headers({
        ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...options.headers,
      }),
    });
  } catch (cause) {
    // fetch only rejects when the request never reached the server.
    throw new ApiError('Could not reach the server. Check your connection.', 0, null);
  }

  if (response.status === 204) return null;

  const isJson = (response.headers.get('content-type') || '').includes('application/json');
  const body = isJson ? await response.json().catch(() => null) : await response.text();

  if (!response.ok) {
    if (response.status === 401 && onUnauthorized) onUnauthorized();
    throw new ApiError(readDetail(body, response.statusText), response.status, body);
  }
  return body;
}

const query = (params = {}) => {
  const search = new URLSearchParams(
    Object.entries(params).filter(
      ([, value]) => value !== undefined && value !== null && value !== '',
    ),
  ).toString();
  return search ? `?${search}` : '';
};

const get = (path, params) => request(`${path}${query(params)}`);
const post = (path, body) => request(path, { method: 'POST', body: JSON.stringify(body ?? {}) });
const patch = (path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body ?? {}) });
const del = (path) => request(path, { method: 'DELETE' });

/** Downloads a CSV through the authenticated client and hands it to the browser. */
async function download(path, params, filename) {
  const response = await fetch(`${BASE_URL}${path}${query(params)}`, { headers: headers() });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(readDetail(body, 'Download failed'), response.status, body);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// --- System ----------------------------------------------------------------

export const getHealth = () => get('/health');

// --- Auth ------------------------------------------------------------------

export const register = (payload) => post('/auth/register', payload);
export const login = (payload) => post('/auth/login', payload);
export const getMe = () => get('/auth/me');
export const updateProfile = (payload) => patch('/auth/me', payload);
export const changePassword = (payload) => post('/auth/change-password', payload);
export const forgotPassword = (email) => post('/auth/forgot-password', { email });

// --- Stores ----------------------------------------------------------------

export const listStores = () => get('/stores');
export const createStore = (payload) => post('/stores', payload);
export const getCurrentStore = () => get('/stores/current');
export const updateStore = (id, payload) => patch(`/stores/${id}`, payload);
export const setOnboardingStep = (id, step) => post(`/stores/${id}/onboarding`, { step });
export const getStoreSettings = () => get('/stores/current/settings');
export const updateStoreSettings = (payload) => patch('/stores/current/settings', payload);
export const listMembers = (id) => get(`/stores/${id}/members`);
export const addMember = (id, payload) => post(`/stores/${id}/members`, payload);
export const updateMemberRole = (id, userId, role) =>
  patch(`/stores/${id}/members/${userId}`, { role });
export const removeMember = (id, userId) => del(`/stores/${id}/members/${userId}`);

// --- Catalogue -------------------------------------------------------------

export const listProducts = (params) => get('/products', params);
export const getProduct = (id) => get(`/products/${id}`);
export const createProduct = (payload) => post('/products', payload);
export const updateProduct = (id, payload) => patch(`/products/${id}`, payload);
export const archiveProduct = (id) => del(`/products/${id}`);
export const getProductCategories = () => get('/products/categories');
export const getBrands = () => get('/products/brands');
export const getCatalogueStats = () => get('/products/stats');
export const lookupBarcode = (code) => get(`/products/barcode/${encodeURIComponent(code)}`);
export const exportProducts = () => download('/products/export', {}, 'products.csv');
export const importProducts = (file) => {
  const form = new FormData();
  form.append('file', file);
  return request('/products/import', { method: 'POST', body: form });
};

export const listCategories = () => get('/categories');
export const createCategory = (payload) => post('/categories', payload);
export const updateCategory = (id, payload) => patch(`/categories/${id}`, payload);
export const deleteCategory = (id) => del(`/categories/${id}`);

// --- POS and sales ---------------------------------------------------------

export const checkout = (payload) => post('/pos/checkout', payload);
export const listSales = (params) => get('/sales', params);
export const getSale = (id) => get(`/sales/${id}`);
export const cancelSale = (id, reason) => post(`/sales/${id}/cancel`, { reason });

// --- Inventory -------------------------------------------------------------

export const getStockPosition = (params) => get('/inventory', params);
export const listMovements = (params) => get('/inventory/movements', params);
export const createAdjustment = (payload) => post('/inventory/adjustments', payload);
export const getRecommendations = (params) => get('/inventory/recommendations', params);
export const getInventorySummary = () => get('/inventory/summary');
export const getProductRecommendation = (id) => get(`/inventory/${id}`);

// --- Purchasing ------------------------------------------------------------

export const listSuppliers = (params) => get('/suppliers', params);
export const getSupplier = (id) => get(`/suppliers/${id}`);
export const createSupplier = (payload) => post('/suppliers', payload);
export const updateSupplier = (id, payload) => patch(`/suppliers/${id}`, payload);
export const archiveSupplier = (id) => del(`/suppliers/${id}`);

export const listPurchaseOrders = (params) => get('/purchase-orders', params);
export const getPurchaseOrder = (id) => get(`/purchase-orders/${id}`);
export const createPurchaseOrder = (payload) => post('/purchase-orders', payload);
export const setPurchaseStatus = (id, status) => patch(`/purchase-orders/${id}/status`, { status });
export const receivePurchaseOrder = (id, items) => post(`/purchase-orders/${id}/receive`, { items });
export const getReorderSuggestions = () => get('/purchase-orders/suggestions');
export const createOrderFromRecommendations = (payload) =>
  post('/purchase-orders/from-recommendations', payload);

// --- Customers and expenses ------------------------------------------------

export const listCustomers = (params) => get('/customers', params);
export const getCustomer = (id) => get(`/customers/${id}`);
export const createCustomer = (payload) => post('/customers', payload);
export const updateCustomer = (id, payload) => patch(`/customers/${id}`, payload);
export const deleteCustomer = (id) => del(`/customers/${id}`);

export const listExpenses = (params) => get('/expenses', params);
export const createExpense = (payload) => post('/expenses', payload);
export const updateExpense = (id, payload) => patch(`/expenses/${id}`, payload);
export const deleteExpense = (id) => del(`/expenses/${id}`);

// --- Intelligence ----------------------------------------------------------

export const getForecast = (id, days = 7, historyDays = 60) =>
  get(`/forecast/${id}`, { days, history_days: historyDays });
export const getModelStatus = () => get('/model');
export const trainModel = () => post('/train');

export const getOverview = (anomalyLimit = 5) => get('/analytics/overview', { anomaly_limit: anomalyLimit });
export const getAnomalies = (limit) => get('/analytics/anomalies', { limit });
export const getTopProducts = (days = 30, limit = 10) => get('/analytics/top-products', { days, limit });
export const getSlowMoving = (days = 30, limit = 10) => get('/analytics/slow-moving', { days, limit });
export const getDemandTrend = (historyDays = 30, forecastDays = 7) =>
  get('/analytics/demand-trend', { history_days: historyDays, forecast_days: forecastDays });
export const getCategoryTrends = (days = 30) => get('/analytics/category-trends', { days });

// --- Business analytics ----------------------------------------------------

export const getDashboard = () => get('/dashboard');
export const getBriefing = () => get('/briefing');
export const getSalesAnalytics = (params) => get('/analytics/sales', params);
export const getProductAnalytics = (params) => get('/analytics/products', params);
export const getInventoryAnalytics = (params) => get('/analytics/inventory', params);
export const getCategoryAnalytics = (days = 30) => get('/analytics/categories', { days });
export const getProfitAnalytics = (params) => get('/analytics/profit', params);

// --- Notifications, search, reports ----------------------------------------

export const listNotifications = (params) => get('/notifications', params);
export const refreshNotifications = () => post('/notifications/refresh');
export const markNotificationRead = (id, isRead = true) =>
  patch(`/notifications/${id}/read`, { is_read: isRead });
export const markAllNotificationsRead = () => post('/notifications/read-all');

export const search = (q, limit = 5) => get('/search', { q, limit });

export const listReports = () => get('/reports');
export const downloadReport = (report, params) =>
  download(`/reports/${report}`, params, `${report}.csv`);
