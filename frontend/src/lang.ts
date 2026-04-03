export const LANGUAGE_NAMES: Record<string, string> = {
  fr: "French",
  es: "Spanish",
  de: "German",
  it: "Italian",
  pt: "Portuguese",
  en: "English",
  ja: "Japanese",
  ko: "Korean",
  zh: "Chinese",
  ru: "Russian",
  ar: "Arabic",
  nl: "Dutch",
  pl: "Polish",
  sv: "Swedish",
  tr: "Turkish",
};

export const lang = {
  app: {
    name: "Translatarr",
  },

  nav: {
    series: "Series",
    movies: "Movies",
    history: "History",
    settings: "Settings",
    general: "General",
    sonarr: "Sonarr",
    radarr: "Radarr",
    jellyfin: "Jellyfin",
    system: "System",
    tasks: "Tasks",
    logs: "Logs",
    status: "Status",
  },

  header: {
    scanLibrary: "Scan Library",
    scanning: "Scanning...",
    searchPlaceholder: "Search…",
    noResults: "No results",
  },

  folderPicker: {
    title: "Select Folder",
    up: "Up",
    root: "Root",
    loading: "Loading…",
    noSubdirectories: "No subdirectories",
    cancel: "Cancel",
    select: "Select",
  },

  confirm: {
    deleteSubtitle: (name: string) => `Are you sure you want to delete the subtitle for "${name}"?`,
    deleteSeasonSubtitles: (series: string, season: number) =>
      `Are you sure you want to delete all subtitles for Season ${season} of "${series}"?`,
    deleteSeriesSubtitles: (series: string) =>
      `Are you sure you want to delete all subtitles for "${series}"?`,
  },

  actions: {
    generateSubtitles: "Generate Subtitles",
    generate: "Generate",
    generateTitle: "Generate subtitle",
    deleteSubtitle: "Delete Subtitle",
    delete: "Delete",
    deleteTitle: "Delete subtitle",
    cancel: "Cancel",
    refresh: "Refresh",
    saveSettings: "Save",
    saving: "Saving...",
    saved: "Saved!",
    clearDisplay: "Clear display",
  },

  badges: {
    subtitled: "Subtitled",
    missing: "Missing",
    found: "Found",
    none: "None",
    yes: "Yes",
    no: "No",
    live: "Live",
    disconnected: "Disconnected",
    available: "Available",
    notFound: "Not found",
    installed: "Installed",
    notInstalled: "Not installed",
  },

  history: {
    filters: {
      all: "All",
      translated: "Translated",
      transcribed: "Transcribed",
      failed: "Failed",
    },
    table: {
      date: "Date",
      file: "File",
      action: "Action",
      detail: "Detail",
    },
    empty: "No history yet",
    prev: "Prev",
    next: "Next",
  },

  movies: {
    loading: "Loading…",
    empty: {
      title: "No movies found",
      text: "Configure the movies path in Settings and run a scan.",
    },
  },

  series: {
    loading: "Loading…",
    generateAllMissing: "Generate All Missing",
    deleteAllSubtitles: "Delete All Subtitles",
    generateSeason: "Generate Season",
    deleteSeasonSubtitles: "Delete Season Subtitles",
    queuing: "Queuing…",
    deleting: "Deleting…",
    season: "Season",
    episode: "episode",
    episodes: "episodes",
    subtitled: "subtitled",
    noEpisodes: "No episodes found",
    status: {
      ended: "Ended",
      continuing: "Continuing",
      upcoming: "Upcoming",
    },
    table: {
      episode: "Episode",
      title: "Title",
      sourceSrt: "Subtitles",
      actions: "Actions",
    },
    empty: {
      title: "No series found",
      text: "Configure the series path in Settings and run a scan.",
    },
  },

  settings: {
    targetLanguage: "Target Language",
    whisperModel: "Whisper Model",
    concurrentWorkers: "Concurrent Workers",
    workersHelp: "Requires a restart to take effect.",
    seriesPath: "Series Path",
    seriesPathHelp: "Directory containing your TV series (Sonarr-style structure)",
    seriesPathPlaceholder: "/tv",
    moviesPath: "Movies Path",
    moviesPathHelp: "Directory containing your movies (Radarr-style structure)",
    moviesPathPlaceholder: "/movies",
    scanInterval: "Scan Interval (minutes)",
    scanIntervalHelp: "Set to 0 to disable automatic scanning",
    generateAutomatically: "Generate subtitles automatically",
    generateAfterScanHelp: "Queue subtitle generation for all media without subtitles at the end of every scan. Disabled by default.",
    // Integration pages (Sonarr / Radarr / Jellyfin)
    enabled: "Enable integration",
    host: "Host",
    port: "Port",
    httpTimeout: "HTTP Timeout (seconds)",
    apiKey: "API Key",
    testConnection: "Test Connection",
    testFailed: "Failed",
    testRequiredHint: "Test the connection before saving",
  },

  systemLogs: {
    waitingForOutput: "Waiting for log output…",
  },

  systemStatus: {
    version: "Version",
    python: "Python",
    uptime: "Uptime",
    ffmpeg: "ffmpeg",
    whisper: "Whisper",
    loading: "Loading status…",
    updateAvailable: (v: string) => `Update available: v${v}`,
  },

  systemTasks: {
    task: "task",
    tasks: "tasks",
    noTasks: {
      title: "No tasks yet",
      text: "Tasks appear here when subtitles are generated or a scan runs.",
    },
    table: {
      type: "Type",
      status: "Status",
      progress: "Progress",
      detail: "Detail",
      created: "Created",
      actions: "Actions",
    },
    types: {
      subtitle: "Subtitle",
      scan: "Scan",
    },
    completedProgress: "100%",
    noValue: "—",
  },
};
