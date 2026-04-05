import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import SearchBox from "../SearchBox.vue";

// ── Mocks ─────────────────────────────────────────────────────────────────

const mockPush = vi.fn();

vi.mock("vue-router", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/lang", () => ({
  lang: {
    header: { searchPlaceholder: "Search…", noResults: "No results" },
    nav: { series: "Series", movies: "Movies" },
    series: { episode: "episode", episodes: "episodes" },
  },
}));

function makeStore(seriesNames: string[], movieTitles: { id: number; title: string; year?: number }[]) {
  return {
    series: seriesNames.map(name => ({
      series_name: name,
      episode_count: 1,
      subtitled_count: 0,
      first_season: 1,
      last_season: 1,
      poster_url: null,
    })),
    movies: movieTitles.map(m => ({
      id: m.id,
      title: m.title,
      year: m.year ?? null,
      file_path: "",
      has_source_srt: false,
      source_srt_label: null,
      has_target_srt: false,
      target_srt_path: null,
      file_size: null,
      duration: null,
      poster_url: null,
    })),
    fetchSeries: vi.fn(),
    fetchMovies: vi.fn(),
  };
}

vi.mock("@/stores/library", () => ({
  useLibraryStore: () => currentStore,
}));

let currentStore: ReturnType<typeof makeStore>;

// ── Helpers ───────────────────────────────────────────────────────────────

function mountSearchBox() {
  return mount(SearchBox, {
    global: { plugins: [createPinia()] },
    attachTo: document.body,
  });
}

async function typeQuery(wrapper: ReturnType<typeof mount>, value: string) {
  const input = wrapper.find("input");
  await input.setValue(value);
}

// ── Tests ─────────────────────────────────────────────────────────────────

describe("SearchBox", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    mockPush.mockClear();
    currentStore = makeStore(
      ["Breaking Bad", "Better Call Saul", "The Wire"],
      [
        { id: 1, title: "Inception", year: 2010 },
        { id: 2, title: "Interstellar", year: 2014 },
        { id: 3, title: "The Dark Knight", year: 2008 },
      ]
    );
  });

  it("does not show dropdown when query is empty", async () => {
    const w = mountSearchBox();
    expect(w.find(".search-dropdown").exists()).toBe(false);
  });

  it("shows matching series result", async () => {
    const w = mountSearchBox();
    await typeQuery(w, "breaking");
    const items = w.findAll(".search-dropdown__item");
    expect(items.length).toBe(1);
    expect(items[0].text()).toContain("Breaking Bad");
  });

  it("shows matching movie results", async () => {
    const w = mountSearchBox();
    await typeQuery(w, "inter");
    const items = w.findAll(".search-dropdown__item");
    expect(items.length).toBe(1);
    expect(items[0].text()).toContain("Interstellar");
  });

  it("matches case-insensitively", async () => {
    const w = mountSearchBox();
    await typeQuery(w, "BREAKING");
    const items = w.findAll(".search-dropdown__item");
    expect(items.length).toBe(1);
    expect(items[0].text()).toContain("Breaking Bad");
  });

  it("shows 'No results' when nothing matches", async () => {
    const w = mountSearchBox();
    await typeQuery(w, "xyznotfound");
    expect(w.find(".search-dropdown__empty").exists()).toBe(true);
    expect(w.find(".search-dropdown__empty").text()).toBe("No results");
  });

  it("limits series results to 5", async () => {
    currentStore = makeStore(
      ["Show A", "Show AA", "Show AAA", "Show AAAA", "Show AAAAA", "Show AAAAAA", "Show AAAAAAA", "Show AAAAAAAA"],
      []
    );
    const w = mountSearchBox();
    await typeQuery(w, "show");
    const items = w.findAll(".search-dropdown__item");
    expect(items.length).toBe(5);
  });

  it("limits movie results to 5", async () => {
    currentStore = makeStore(
      [],
      Array.from({ length: 8 }, (_, i) => ({ id: i + 1, title: `Movie ${i + 1}` }))
    );
    const w = mountSearchBox();
    await typeQuery(w, "movie");
    const items = w.findAll(".search-dropdown__item");
    expect(items.length).toBe(5);
  });

  it("navigates to series on click", async () => {
    const w = mountSearchBox();
    await typeQuery(w, "breaking");
    const item = w.find(".search-dropdown__item");
    await item.trigger("mousedown");
    expect(mockPush).toHaveBeenCalledWith("/series/Breaking%20Bad");
  });

  it("navigates to movie on click", async () => {
    const w = mountSearchBox();
    await typeQuery(w, "inception");
    const item = w.find(".search-dropdown__item");
    await item.trigger("mousedown");
    expect(mockPush).toHaveBeenCalledWith("/movies/1");
  });

  it("clears query and hides dropdown on Escape", async () => {
    const w = mountSearchBox();
    await typeQuery(w, "breaking");
    expect(w.find(".search-dropdown").exists()).toBe(true);
    await w.find("input").trigger("keydown.escape");
    expect(w.find(".search-dropdown").exists()).toBe(false);
    expect((w.find("input").element as HTMLInputElement).value).toBe("");
  });
});
