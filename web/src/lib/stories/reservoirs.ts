// Texas reservoir storage month by month since 1950. Chapters are found in the data: the lowest month, the low
// points of later droughts, the big refills, and the latest month.
import { day } from "../format";
import { turningPoints } from "./drought";
import { chapterCaptions, monthLabel, yearStarts, type Story, type StoryContext, type StoryEntry } from "./model";

export const reservoirStorySlug = "texas-reservoirs-since-1950";
const SWING = 25;          // points between turning points worth a chapter
const GAP = 72;            // months: a chapter this close to an earlier-listed one is dropped

const pct = (v: number) => Math.round(v) + "%";

export function buildReservoirStory({ data, latest }: StoryContext): Story | null {
  const months = data.reservoirs?.months ?? [];
  if (months.length < 120 || latest.sources.twdb_reservoirs?.stale) return null;
  const v = months.map((m) => m.pct);
  const label = (i: number) => monthLabel(months[i].month);
  const last = months.length - 1;
  const lo = v.indexOf(Math.min(...v));
  const hi = v.indexOf(Math.max(...v));
  // The lowest month since the first decade, so a recent drought gets its own chapter beside the record.
  const laterFrom = months.findIndex((m) => Number(m.month.slice(0, 4)) >= Number(months[lo].month.slice(0, 4)) + 30);
  const later = laterFrom > 0 ? v.slice(laterFrom) : [];
  const recentLow = later.length ? laterFrom + later.indexOf(Math.min(...later)) : -1;

  const chapters: { frame: number; label: string; caption: string }[] = [
    { frame: 0, label: "1950", caption: `${label(0)}: Texas reservoirs hold ${pct(v[0])} of their capacity. Each step is one month.` },
    { frame: last, label: "Latest", caption: `${label(last)}: ${pct(v[last])} full.` },
    { frame: lo, label: "Lowest", caption: `${label(lo)}: storage falls to ${pct(v[lo])}, the lowest month since 1950.` },
  ];
  if (recentLow > 0) {
    chapters.push({ frame: recentLow, label: `${months[recentLow].month.slice(0, 4)} low`,
      caption: `${label(recentLow)}: storage drops to ${pct(v[recentLow])}, the lowest since ${months[lo].month.slice(0, 4)}.` });
  }
  chapters.push({ frame: hi, label: "Fullest", caption: `${label(hi)}: reservoirs reach ${pct(v[hi])}, the fullest month on record here.` });
  for (const { i, kind } of turningPoints(v, SWING)) {
    chapters.push(kind === "low"
      ? { frame: i, label: `${months[i].month.slice(0, 4)} low`, caption: `${label(i)}: storage bottoms out at ${pct(v[i])} before the lakes refill.` }
      : { frame: i, label: `${months[i].month.slice(0, 4)} refill`, caption: `${label(i)}: storage climbs back to ${pct(v[i])}.` });
  }
  const kept: typeof chapters = [];
  for (const c of chapters) if (!kept.some((o) => Math.abs(o.frame - c.frame) < GAP)) kept.push(c);
  kept.sort((a, b) => a.frame - b.frame);
  const captions = chapterCaptions(months.length, kept);
  const dates = months.map((m) => m.month + "-01");
  const chapterFrames = kept.map((c) => c.frame);
  const tableFrames = months.flatMap((m, i) => (m.month.endsWith("-01") || chapterFrames.includes(i) || i === last ? [i] : []));

  return {
    slug: reservoirStorySlug,
    topic: "Water",
    period: `${months[0].month.slice(0, 4)}–${months[last].month.slice(0, 4)}`,
    title: "Texas reservoirs, month by month since 1950",
    description: `${months.length} months of statewide reservoir storage, from the 1950s drought of record (${pct(v[lo])} full) to ${pct(v[last])} now.`,
    metric: "Texas reservoir storage, percent of capacity",
    frameLabel: "Month",
    series: [{ name: "Percent full", unit: "percent" }],
    frames: months.map((m, i) => ({ date: dates[i], label: label(i), values: [v[i]], caption: captions[i] })),
    chapters: kept.map(({ frame, label }) => ({ frame, label })),
    takeaway: {
      title: `Storage has ranged from ${pct(v[lo])} to ${pct(v[hi])} full since 1950`,
      text: `The lowest month was ${label(lo)}.` + (recentLow > 0 ? ` The deepest drop since then came in ${label(recentLow)}, at ${pct(v[recentLow])}.` : "")
        + ` The latest figure, through ${day(data.reservoirs!.through)}, is ${pct(v[last])}.`,
    },
    source: "twdb_reservoirs",
    method: "Monthly averages of the Texas Water Development Board’s daily statewide storage, as a share of conservation capacity. The story starts in 1950 because earlier figures mostly reflect reservoirs still being built and filled. In the drawing, the water’s cross-section area is proportional to percent full. The table lists each January and every chapter.",
    visual: { kind: "reservoir" },
    timeline: {
      series: [{ index: 0, label: "Percent full", mark: "area", tone: "green" }],
      min: 0, max: 100,
      ticks: [{ value: 0, label: "0%" }, { value: 50, label: "50%" }, { value: 100, label: "100%" }],
      periods: yearStarts(dates, 10),
      note: "Statewide storage, monthly",
    },
    tableFrames,
    frameMs: 45,
    highlights: [
      { label: `Lowest, ${monthLabel(months[lo].month)}`, value: pct(v[lo]) },
      { label: "Now", value: pct(v[last]) },
    ],
    related: { href: "", label: "Texas overview" },
  };
}

export const reservoirStory: StoryEntry = {
  slug: reservoirStorySlug,
  fallback: { title: "Texas reservoirs since 1950", topic: "Water", description: "This replay returns when the statewide reservoir figures are current.", related: { href: "", label: "Texas overview" } },
  build: buildReservoirStory,
  featured: () => false,
};
