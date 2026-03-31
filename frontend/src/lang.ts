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

  actions: {
    generateSubtitles: "Generate Subtitles",
    generate: "Generate",
    deleteSubtitle: "Delete Subtitle",
    delete: "Delete",
    cancel: "Cancel",
    refresh: "Refresh",
    saveSettings: "Save Settings",
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
    sourceSrt: "Source SRT:",
    targetSrt: "Target SRT:",
    empty: {
      title: "No movies found",
      text: "Configure the movies path in Settings and run a scan.",
    },
  },

  series: {
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
    table: {
      episode: "Episode",
      title: "Title",
      sourceSrt: "Source SRT",
      targetSrt: "Target SRT",
      actions: "Actions",
    },
    empty: {
      title: "No series found",
      text: "Configure the series path in Settings and run a scan.",
    },
  },

  settings: {
    targetLanguage: "Target Language",
    languages: {
      fr: "French (fr)",
      es: "Spanish (es)",
      de: "German (de)",
      it: "Italian (it)",
      pt: "Portuguese (pt)",
    },
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
    generateAfterScan: "Generate subtitles after scan",
    generateAfterScanHelp: "Queue subtitle generation for all media without subtitles at the end of every scan. Disabled by default.",
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
