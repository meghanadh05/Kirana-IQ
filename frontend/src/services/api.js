const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!response.ok) {
    // FastAPI reports problems in `detail`; fall back to the status text.
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* response had no JSON body */
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

const query = (params) => {
  const search = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')
  ).toString();
  return search ? `?${search}` : '';
};

export const getHealth = () => request('/health');
export const getModel = () => request('/model');
export const trainModel = () => request('/train', { method: 'POST' });

export const getProducts = (params = {}) => request(`/products${query(params)}`);
export const getCategories = () => request('/products/categories');
export const getProduct = (id) => request(`/products/${id}`);

export const getForecast = (id, days = 7, historyDays = 60) =>
  request(`/forecast/${id}${query({ days, history_days: historyDays })}`);

export const getRecommendations = (params = {}) => request(`/inventory/recommendations${query(params)}`);
export const getInventorySummary = () => request('/inventory/summary');

export const getOverview = (anomalyLimit = 5) => request(`/analytics/overview${query({ anomaly_limit: anomalyLimit })}`);
export const getAnomalies = (limit) => request(`/analytics/anomalies${query({ limit })}`);
export const getTopProducts = (days = 30, limit = 10) => request(`/analytics/top-products${query({ days, limit })}`);
export const getSlowMoving = (days = 30, limit = 10) => request(`/analytics/slow-moving${query({ days, limit })}`);
export const getDemandTrend = (historyDays = 30, forecastDays = 7) =>
  request(`/analytics/demand-trend${query({ history_days: historyDays, forecast_days: forecastDays })}`);
export const getCategoryTrends = (days = 30) => request(`/analytics/category-trends${query({ days })}`);
