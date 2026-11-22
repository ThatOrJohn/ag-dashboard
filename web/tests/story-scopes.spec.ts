import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { countyPaths, statePaths, stateName } from "../src/lib/geo";
import { buildAreaStories, districtStoryData, type StoryContext } from "../src/lib/stories";
import type { Source } from "../src/lib/types";

const source: Source = { name: "Fixture", url: null, license: null, as_of: "2026-11-22", fetched_at: null, stale: false };
const fips = ["40017", "40027", "40109"];
const weeks = Array.from({ length: 104 }, (_, i) => ({
  date: new Date(Date.UTC(2024, 10, 26 + i * 7)).toISOString().slice(0, 10),
  map: i < 50 ? "0?3" : "143",
  state: { d1: i < 50 ? 20 : 80, d3: i < 50 ? 10 : 45 },
}));
const oklahoma: StoryContext = {
  area: { level: "state", id: "ok", name: "Oklahoma", phrase: "Oklahoma", stateFips: "40" },
  asof: "2026-11-22",
  sources: { usdm: source, nass: source, census: source },
  counties: {
    "40017": { name: "Canadian", district: "central" },
    "40027": { name: "Cleveland", district: "central" },
    "40109": { name: "Oklahoma", district: "central" },
  },
  data: {
    drought: { counties: fips, weeks },
    cotton: { seasons: [
      { year: 2025, reports: [{ date: "2025-09-14", pct: 12 }, { date: "2025-10-19", pct: 54 }] },
      { year: 2026, reports: [{ date: "2026-09-13", pct: 9 }, { date: "2026-11-15", pct: 82 }] },
    ] },
    census: { years: [2017, 2022], counties: {
      "40017": [60, 55, 1200, 1130], "40027": [40, 45, 810, 920], "40109": [25, 41, 500, 800],
    } },
  },
  overview: { href: "stories/#ok", label: "Oklahoma stories" },
};

test("template story files contain no literal state names", () => {
  const directory = path.resolve("src/lib/stories");
  const names = statePaths(520, 500).shapes.map(({ fips }) => stateName(fips));
  const stateNames = new RegExp(`\\b(${names.join("|")})\\b`);
  for (const file of fs.readdirSync(directory).filter((name) => name.endsWith(".ts"))) {
    expect(fs.readFileSync(path.join(directory, file), "utf8"), file).not.toMatch(stateNames);
  }
});

test("the Oklahoma fixture builds every template from three counties and state harvest reports", () => {
  const stories = buildAreaStories(oklahoma, true);
  expect(stories.map(({ path }) => path)).toEqual([
    "ok/two-years-of-drought", "ok/cotton-harvest-pace", "ok/farms-over-time",
  ]);
  for (const { story, fallback, image } of stories) {
    expect(story?.title).toContain("Oklahoma");
    expect(fallback.title).toContain("Oklahoma");
    expect(image).toMatch(/^story-ok-/);
  }
  const visual = stories[0].story?.visual;
  if (visual?.kind !== "drought") throw new Error("expected a drought replay");
  expect(visual.fips).toEqual(fips);
  expect(countyPaths("40", new Set(fips), 520, 500, () => "").shapes.map((s) => s.fips).sort()).toEqual(fips);
  expect(stories[2].story?.frames[0].values).toEqual([125, 2510, 2510 / 125]);
});

test("district stories use only their county roster and land-weighted coverage", () => {
  const data = districtStoryData(oklahoma.data, {
    counties: [{ fips: fips[2], ...oklahoma.counties[fips[2]] }],
    drought_history: weeks.map(({ date }) => ({ date, d1: 95, d3: 75 })),
  });
  const district: StoryContext = {
    ...oklahoma, data,
    area: { level: "district", id: "central", name: "Central", phrase: "the Central district", stateId: "ok", stateFips: "40" },
  };
  const [drought, census] = buildAreaStories(district, false);
  expect(drought.path).toBe("ok/central/two-years-of-drought");
  expect(drought.story?.title).toContain("the Central district");
  expect(drought.story?.visual).toMatchObject({ fips: [fips[2]], maps: weeks.map(() => "3") });
  expect(drought.story?.frames[0].values).toEqual([95, 75, 1]);
  expect(census.story?.frames[0].values).toEqual([25, 500, 20]);
});

test("national maps use state FIPS and national coverage", () => {
  const states = ["02", "15", "40"];
  const national: StoryContext = {
    ...oklahoma,
    area: { level: "us", id: "us", name: "United States", phrase: "the United States" },
    data: {
      cotton: oklahoma.data.cotton,
      drought: { states, weeks: weeks.map(({ date, map }) => ({ date, map, coverage: { d1: 34, d3: 5 } })) },
      census: { years: [2017, 2022], states: { "40": [125, 141, 2510, 2850] } },
    },
  };
  const [drought, cotton, census] = buildAreaStories(national, true);
  expect(drought.path).toBe("us/two-years-of-drought");
  expect(drought.story?.visual).toMatchObject({ fips: states });
  expect(drought.story?.frames[0].values).toEqual([34, 5, 1]);
  expect(cotton.story?.title).toContain("the United States");
  expect(census.story?.visual).toMatchObject({ fips: ["40"] });
  expect(statePaths(520, 500).shapes.map((s) => s.fips)).toEqual(expect.arrayContaining(states));
});
