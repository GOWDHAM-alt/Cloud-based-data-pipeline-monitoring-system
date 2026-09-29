const BASE = import.meta.env.VITE_API_URL || "http://localhost:8001";

async function get(path) {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const getSummary = () => get("/api/v1/summary");
export const getRuns = (limit = 50) => get(`/api/v1/runs?limit=${limit}`);
export const getRun = (id) => get(`/api/v1/runs/${id}`);
export const getAlerts = (limit = 50) => get(`/api/v1/alerts?limit=${limit}`);
export const getInfra = (limit = 10) => get(`/api/v1/metrics/infra?limit=${limit}`);
export const getTrends = (limit = 30) => get(`/api/v1/trends?limit=${limit}`);