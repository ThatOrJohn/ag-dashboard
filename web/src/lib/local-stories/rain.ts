// An archived story: five weeks of daily rain in three districts, saved with its captions so the comparison
// stays available after the dashboard's weather strip rolls forward.
import { day, inches } from "../format";
import { chapterCaptions, type Story, type StoryEntry } from "../stories/model";

export const rainStorySlug = "five-weeks-of-rain";
const START = "2026-10-11";
const series = [
  { name: "Edwards Plateau", slug: "edwards-plateau", unit: "inches" as const },
  { name: "Northern Low Plains", slug: "northern-low-plains", unit: "inches" as const },
  { name: "Blacklands", slug: "blacklands", unit: "inches" as const },
];
// Observed daily district rain_in from weather.days (district area-weighted nClimGrid), Oct. 11–Nov. 14, 2026,
// in `series` order. Saved from the Nov. 21, 2026 build.
const DAILY: readonly (readonly [number, number, number])[] = [
  [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0.74, 0], [0.07, 2.11, 0.04], [0.76, 0.92, 0.09], [0, 0, 0],
  [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0],
  [0, 0, 0], [0, 0.03, 0], [0.06, 0.23, 0], [0, 0, 0], [0.01, 0, 0], [1.65, 0.25, 0.1], [0.73, 0.66, 0.1],
  [0.01, 0.01, 0], [0, 0.02, 0], [0.17, 0.05, 0.36], [0, 0, 0.02], [0, 0, 0], [0, 0, 0], [0, 0, 0],
  [0.77, 0, 0.21], [0.97, 0, 0.04], [0.26, 0, 0.01], [0.01, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0],
];

function dateAt(i: number): string {
  const d = new Date(START + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + i);
  return d.toISOString().slice(0, 10);
}

const CHAPTERS = [
  { frame: 0, label: "Week one", caption: "Week one, Oct. 11–17: the Northern Low Plains gets 3.77 inches, more than four times the Edwards Plateau’s 0.83." },
  { frame: 4, label: "Downpour", caption: "Oct. 15: 2.11 inches falls on the Northern Low Plains in a single day, the wettest day for any of the three districts in these five weeks." },
  { frame: 7, label: "A dry week", caption: "Week two, Oct. 18–24: not a hundredth of an inch shows up in any of the three districts’ daily averages." },
  { frame: 19, label: "Plateau catches up", caption: "Oct. 30–31: the Edwards Plateau gets 2.38 inches in two days and starts to close the gap." },
  { frame: 28, label: "Final week", caption: "Week five, Nov. 8–14: another two inches on the Edwards Plateau puts it ahead. The Blacklands finishes below one inch." },
];

export function buildRainStory(): Story {
  const totals = [0, 0, 0];
  const captions = chapterCaptions(DAILY.length, CHAPTERS);
  const frames = DAILY.map((today, i) => {
    today.forEach((v, s) => { totals[s] = Math.round((totals[s] + v) * 100) / 100; });
    const date = dateAt(i);
    return { date, label: day(date), values: [...totals], caption: captions[i] };
  });
  const final = frames.at(-1)!.values as number[];
  return {
    slug: rainStorySlug,
    topic: "Rain",
    period: "Oct. 11 – Nov. 14, 2026",
    title: "Five weeks of rain, two very different starts",
    description: "The Northern Low Plains built an early lead, the Edwards Plateau caught up late, and the Blacklands finished below one inch.",
    metric: "Rain since Oct. 11",
    frameLabel: "Day",
    series,
    frames,
    chapters: [...CHAPTERS.map(({ frame, label }) => ({ frame, label })), { frame: frames.length - 1, label: "Final totals" }],
    takeaway: {
      title: "Similar totals can hide very different weeks",
      text: "The Northern Low Plains got about three-quarters of its five-week total in week one. The Edwards Plateau got less than one-sixth of its total that week, yet finished with more rain.",
    },
    source: "nclimgrid",
    method: "Daily figures are my own district averages of NOAA nClimGrid county rain, weighted by county land area. Totals add up those daily averages to the nearest hundredth of an inch.",
    visual: { kind: "rain", daily: DAILY, scaleMax: 6 },
    frameMs: 420,
    highlights: series.map(({ name }, i) => ({ label: name, value: inches(final[i]) })),
  };
}

export const rainStory: StoryEntry = {
  slug: rainStorySlug,
  fallback: { title: "Five weeks of rain", topic: "Rain", description: "", related: { href: "", label: "Texas overview" } },
  build: buildRainStory,
  featured: () => false,
};
