// Two years of weekly Drought Monitor maps, county by county. The chapters are found in the data on each
// build (the least and most drought, the fastest spread), so the story keeps up as new maps arrive.
import { day } from "../format";
import { chapterCaptions, type StoryContext, type StoryEntry, type StoryFrame } from "./model";

export const droughtStorySlug = "two-years-of-drought";
export const droughtStoryTitle = "Two years of Texas drought, week by week";
/** Weeks over which the fastest spread is measured, and the smallest rise worth a chapter. */
const SPREAD_WEEKS = 6;
const SPREAD_MIN_POINTS = 15;
/** A rise or fall of at least this many points between turning points gets a chapter. */
const SWING_POINTS = 25;
/** Chapters closer than this many weeks to an earlier-listed one are dropped. */
const CHAPTER_GAP = 3;

/** Alternating lows and highs where the series reverses by at least `swing` points. */
export function turningPoints(v: readonly number[], swing: number): { i: number; kind: "low" | "high" }[] {
  const out: { i: number; kind: "low" | "high" }[] = [];
  let lo = 0, hi = 0, dir: "up" | "down" | null = null;
  for (let i = 1; i < v.length; i++) {
    if (v[i] > v[hi]) hi = i;
    if (v[i] < v[lo]) lo = i;
    if (dir !== "up" && v[i] - v[lo] >= swing) {
      if (dir === "down" || out.length || lo > 0) out.push({ i: lo, kind: "low" });
      dir = "up"; hi = i;
    } else if (dir !== "down" && v[hi] - v[i] >= swing) {
      if (dir === "up" || out.length || hi > 0) out.push({ i: hi, kind: "high" });
      dir = "down"; lo = i;
    }
  }
  return out.filter(({ i }) => i > 0 && i < v.length - 1);
}

const pct = (v: number) => Math.round(v) + "%";
export const severeCounties = (map: string) => [...map].filter((c) => c === "3" || c === "4").length;

export function buildDroughtStory({ data, latest }: StoryContext) {
  const weeks = data.drought?.weeks.filter((w) => w.state) ?? [];
  if (!data.drought || weeks.length < SPREAD_WEEKS * 2 || latest.sources.usdm?.stale) return null;
  const first = weeks[0], last = weeks.at(-1)!;
  const d1 = weeks.map((w) => w.state!.d1);
  const label = (i: number) => day(weeks[i].date);
  const lo = d1.indexOf(Math.min(...d1));
  const hi = d1.indexOf(Math.max(...d1));
  let spread = -1, rise = 0;
  for (let i = SPREAD_WEEKS; i < d1.length; i++) {
    if (d1[i] - d1[i - SPREAD_WEEKS] > rise) { rise = d1[i] - d1[i - SPREAD_WEEKS]; spread = i - SPREAD_WEEKS; }
  }
  const lastIndex = weeks.length - 1;
  const counties = data.drought.counties.length;

  const chapters: { frame: number; label: string; caption: string }[] = [
    { frame: 0, label: "Start", caption: `${label(0)}: ${pct(d1[0])} of Texas is in moderate drought or worse. Watch each county change color as the weekly maps go by.` },
    { frame: lo, label: "Least drought", caption: `${label(lo)}: drought shrinks to ${pct(d1[lo])} of Texas, the least on any map in these two years.` },
    { frame: hi, label: "Most drought", caption: `${label(hi)}: drought covers ${pct(d1[hi])} of Texas, the most in these two years. ${severeCounties(weeks[hi].map)} counties are mostly in extreme or exceptional drought.` },
    { frame: lastIndex, label: "Latest map", caption: `${label(lastIndex)}, the latest map: ${pct(d1[lastIndex])} of Texas is in drought, ${d1[lastIndex] < d1[hi] ? `down from ${pct(d1[hi])} at the peak` : "the peak so far"}.` },
  ];
  if (spread >= 0 && rise >= SPREAD_MIN_POINTS) {
    chapters.push({ frame: spread, label: "Fastest spread",
      caption: `Watch the next ${SPREAD_WEEKS} weeks: from ${label(spread)}, drought spreads from ${pct(d1[spread])} to ${pct(d1[spread + SPREAD_WEEKS])} of Texas, the fastest on these maps.` });
  }
  const month = (i: number) => day(weeks[i].date).replace(/ \d+,/, "");
  for (const { i, kind } of turningPoints(d1, SWING_POINTS)) {
    chapters.push(kind === "high"
      ? { frame: i, label: `${month(i)} high`, caption: `${label(i)}: drought builds to ${pct(d1[i])} of Texas before easing.` }
      : { frame: i, label: `${month(i)} low`, caption: `${label(i)}: drought eases to ${pct(d1[i])} of Texas before building again.` });
  }
  // Earlier-listed chapters win when two land within a few weeks (start and latest are never dropped).
  const kept: typeof chapters = [];
  for (const c of chapters) if (!kept.some((o) => Math.abs(o.frame - c.frame) < CHAPTER_GAP)) kept.push(c);
  const unique = kept.sort((a, b) => a.frame - b.frame);
  const captions = chapterCaptions(weeks.length, unique);
  const frames: StoryFrame[] = weeks.map((w, i) => ({
    date: w.date, label: label(i), caption: captions[i],
    values: [w.state!.d1, w.state!.d3, severeCounties(w.map)],
  }));

  return {
    slug: droughtStorySlug,
    topic: "Drought",
    period: `${day(first.date)} – ${day(last.date)}`,
    title: droughtStoryTitle,
    description: `${weeks.length} weekly U.S. Drought Monitor maps of all ${counties} Texas counties, from ${pct(d1[0])} of the state in drought to ${pct(d1[hi])} at the peak and ${pct(d1[lastIndex])} now.`,
    metric: "Texas land in moderate drought or worse",
    frameLabel: "Map week",
    series: [
      { name: "Moderate or worse (D1–D4)", unit: "percent" as const },
      { name: "Extreme or worse (D3–D4)", unit: "percent" as const },
      { name: "Counties mostly D3–D4", unit: "count" as const },
    ],
    frames,
    chapters: unique.map(({ frame, label }) => ({ frame, label })),
    takeaway: {
      title: rise >= SPREAD_MIN_POINTS
        ? `Drought can cover most of Texas within ${SPREAD_WEEKS} weeks`
        : "Texas drought shifts from week to week",
      text: `In these two years, the share of Texas in drought ran from ${pct(d1[lo])} (${label(lo)}) to ${pct(d1[hi])} (${label(hi)}).`
        + (rise >= SPREAD_MIN_POINTS ? ` The fastest spread added ${Math.round(rise)} percentage points in ${SPREAD_WEEKS} weeks.` : ""),
    },
    source: "usdm" as const,
    method: "Each county is colored by the worst category covering at least half its land, as on the dashboard's maps. Statewide percentages are the Drought Monitor's own Texas figures.",
    visual: { kind: "drought" as const, fips: data.drought.counties, maps: weeks.map((w) => w.map) },
    frameMs: 260,
    highlights: [
      { label: "Least", value: pct(d1[lo]) },
      { label: "Most", value: pct(d1[hi]) },
      { label: "Now", value: pct(d1[lastIndex]) },
    ],
    related: { href: "", label: "Texas drought map this week" },
  };
}

export const droughtStory: StoryEntry = {
  slug: droughtStorySlug,
  fallback: {
    title: droughtStoryTitle,
    topic: "Drought",
    description: "This replay of the weekly Drought Monitor maps returns when the newest map is current.",
    related: { href: "", label: "Texas overview" },
  },
  build: buildDroughtStory,
  featured: () => true,
};
