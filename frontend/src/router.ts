import { createRouter, createWebHistory } from "vue-router";

import SeriesIndex from "./pages/SeriesIndex.vue";
import SeriesDetail from "./pages/SeriesDetail.vue";
import MoviesIndex from "./pages/MoviesIndex.vue";
import MovieDetail from "./pages/MovieDetail.vue";
import History from "./pages/History.vue";
import SettingsGeneral from "./pages/SettingsGeneral.vue";
import SettingsSonarr from "./pages/SettingsSonarr.vue";
import SettingsRadarr from "./pages/SettingsRadarr.vue";
import SettingsJellyfin from "./pages/SettingsJellyfin.vue";
import SystemLogs from "./pages/SystemLogs.vue";
import SystemStatus from "./pages/SystemStatus.vue";
import SystemTasks from "./pages/SystemTasks.vue";

const routes = [
  { path: "/", redirect: "/series" },
  { path: "/series", component: SeriesIndex },
  { path: "/series/:name", component: SeriesDetail, props: true },
  { path: "/movies", component: MoviesIndex },
  { path: "/movies/:id", component: MovieDetail, props: true },
  { path: "/history", component: History },
  { path: "/settings/general",  component: SettingsGeneral },
  { path: "/settings/sonarr",   component: SettingsSonarr },
  { path: "/settings/radarr",   component: SettingsRadarr },
  { path: "/settings/jellyfin", component: SettingsJellyfin },
  { path: "/system/logs", component: SystemLogs },
  { path: "/system/status", component: SystemStatus },
  { path: "/system/tasks", component: SystemTasks },
];

export default createRouter({
  history: createWebHistory(),
  routes,
});
