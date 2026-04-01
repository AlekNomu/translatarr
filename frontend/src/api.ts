import axios from "axios";

const api = axios.create({ baseURL: "/api" });

export const seriesApi = {
  list: () => api.get("/series"),
  detail: (name: string) => api.get(`/series/${encodeURIComponent(name)}`),
  generate: (name: string) => api.post(`/series/${encodeURIComponent(name)}/generate`),
  generateSeason: (name: string, season: number) =>
    api.post(`/series/${encodeURIComponent(name)}/seasons/${season}/generate`),
  generateEpisode: (name: string, id: number) =>
    api.post(`/series/${encodeURIComponent(name)}/episodes/${id}/generate`),
  deleteSubtitle: (name: string) =>
    api.delete(`/series/${encodeURIComponent(name)}/subtitle`),
  deleteSeasonSubtitle: (name: string, season: number) =>
    api.delete(`/series/${encodeURIComponent(name)}/seasons/${season}/subtitle`),
  deleteEpisodeSubtitle: (name: string, id: number) =>
    api.delete(`/series/${encodeURIComponent(name)}/episodes/${id}/subtitle`),
};

export const moviesApi = {
  list: () => api.get("/movies"),
  detail: (id: number) => api.get(`/movies/${id}`),
  generate: (id: number) => api.post(`/movies/${id}/generate`),
  deleteSubtitle: (id: number) => api.delete(`/movies/${id}/subtitle`),
};

export const historyApi = {
  list: (params?: { page?: number; per_page?: number; action?: string }) =>
    api.get("/history", { params }),
};

export const settingsApi = {
  get: () => api.get("/settings"),
  update: (data: Record<string, string>) => api.put("/settings", data),
  testConnection: (
    service: "sonarr" | "radarr" | "jellyfin",
    config: Record<string, string>,
  ) => api.post(`/settings/${service}/test`, config),
};

export const systemApi = {
  status: () => api.get("/system/status"),
  recentLogs: () => api.get("/system/logs/recent"),
};

export const tasksApi = {
  scan: () => api.post("/tasks/scan"),
  list: () => api.get("/tasks"),
  get: (id: string) => api.get(`/tasks/${id}`),
  cancel: (id: string) => api.delete(`/tasks/${id}`),
};

export default api;
