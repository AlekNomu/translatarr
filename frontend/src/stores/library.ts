import { defineStore } from "pinia";
import { ref } from "vue";
import { seriesApi, moviesApi } from "@/api";

export interface SeriesSummary {
  series_name: string;
  episode_count: number;
  subtitled_count: number;
  first_season: number | null;
  last_season: number | null;
}

export interface Episode {
  id: number;
  title: string;
  season: number | null;
  episode: number | null;
  file_path: string;
  has_source_srt: boolean;
  has_target_srt: boolean;
  target_srt_path: string | null;
  file_size: number | null;
  duration: number | null;
}

export interface Movie {
  id: number;
  title: string;
  year: number | null;
  file_path: string;
  has_source_srt: boolean;
  has_target_srt: boolean;
  target_srt_path: string | null;
  file_size: number | null;
  duration: number | null;
}

export const useLibraryStore = defineStore("library", () => {
  const series = ref<SeriesSummary[]>([]);
  const movies = ref<Movie[]>([]);

  async function fetchSeries() {
    const { data } = await seriesApi.list();
    series.value = data;
  }

  async function fetchMovies() {
    const { data } = await moviesApi.list();
    movies.value = data;
  }

  return { series, movies, fetchSeries, fetchMovies };
});
