// The Brazos at Richmond, month by month. Each month is compared with the median for that calendar month over
// the whole record, so a dry August is judged against other Augusts.
import { day } from "../format";
import { chapterCaptions, monthLabel, yearStarts, type Story, type StoryContext, type StoryEntry } from "./model";

export const riverStorySlug = "brazos-at-richmond";
/** Months below this fraction of their calendar month's median count as low flow. */
const LOW = 0.5;

const cfs = (v: number) => Math.round(v).toLocaleString("en-US") + " cubic feet per second";
const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
};

export function buildRiverStory({ data, latest }: StoryContext): Story | null {
  const site = data.river?.[0];
  if (!site || site.months.length < 120 || latest.sources.usgs_streamflow?.stale) return null;
  const months = site.months;
  const v = months.map((m) => m.cfs);
  const cal = months.map((m) => Number(m.month.slice(5, 7)));
  const medians = Array.from({ length: 13 }, (_, mo) => (mo ? median(v.filter((_, i) => cal[i] === mo)) : 0));
  const typical = cal.map((mo) => Math.round(medians[mo]));
  const label = (i: number) => monthLabel(months[i].month);
  const last = months.length - 1;
  const hi = v.indexOf(Math.max(...v));
  const lo = v.indexOf(Math.min(...v));
  // Longest run of months below half their typical flow.
  let run = { start: -1, len: 0 }, cur = 0;
  v.forEach((x, i) => {
    cur = x < typical[i] * LOW ? cur + 1 : 0;
    if (cur > run.len) run = { start: i - cur + 1, len: cur };
  });

  const chapters: { frame: number; label: string; caption: string }[] = [
    { frame: 0, label: months[0].month.slice(0, 4), caption: `${label(0)}: the Brazos at Richmond averages ${cfs(v[0])}. The river widens with the flow, and each step is one month.` },
    { frame: hi, label: "Highest", caption: `${label(hi)}: ${cfs(v[hi])}, the highest monthly average since ${months[0].month.slice(0, 4)}, about ${Math.round(v[hi] / typical[hi])} times the usual for that month.` },
    { frame: lo, label: "Lowest", caption: `${label(lo)}: ${cfs(v[lo])}, the lowest monthly average on this record.` },
    { frame: last, label: "Latest", caption: `${label(last)} so far: ${cfs(v[last])}, against a typical ${cfs(typical[last])} for that month.` },
  ];
  if (run.len >= 6 && !chapters.some((c) => Math.abs(c.frame - run.start) < 6)) {
    chapters.push({ frame: run.start, label: "Long low",
      caption: `From ${label(run.start)}, the river runs below half its usual flow for ${run.len} months in a row, the longest stretch on this record.` });
  }
  chapters.sort((a, b) => a.frame - b.frame);
  const captions = chapterCaptions(months.length, chapters);
  const dates = months.map((m) => m.month + "-01");

  return {
    slug: riverStorySlug,
    topic: "Water",
    period: `${months[0].month.slice(0, 4)}–${months[last].month.slice(0, 4)}`,
    title: "The Brazos at Richmond, flood and drought",
    description: `${months.length} months of flow at Richmond, southwest of Houston, from ${cfs(v[lo])} to ${cfs(v[hi])}.`,
    metric: "Brazos River at Richmond, monthly average flow",
    frameLabel: "Month",
    series: [{ name: "Average flow", unit: "cfs" }, { name: "Typical for the month", unit: "cfs" }],
    frames: months.map((m, i) => ({ date: dates[i], label: label(i), values: [v[i], typical[i]], caption: captions[i] })),
    chapters: chapters.map(({ frame, label }) => ({ frame, label })),
    takeaway: {
      title: `The river’s busiest month carried ${Math.round(v[hi] / v[lo])} times the water of its quietest`,
      text: `${label(hi)} averaged ${cfs(v[hi])}; ${label(lo)} averaged ${cfs(v[lo])}.`
        + (run.len >= 6 ? ` The longest low stretch ran ${run.len} months from ${label(run.start)}.` : ""),
    },
    source: "usgs_streamflow",
    method: `Monthly averages of USGS daily mean flow at gauge 08114000. “Typical” is the median for that calendar month across the record. The latest month runs through ${day(site.through)}.`
      + (site.provisional_from ? ` Flows since ${day(site.provisional_from)} are provisional and may be revised.` : "") + " The chart uses a log scale so dry months stay visible.",
    visual: { kind: "river", typical, maxFlow: Math.max(...v) },
    timeline: {
      series: [{ index: 0, label: "Monthly average flow", mark: "line", tone: "green" }, { index: 1, label: "Typical for the month", mark: "line", tone: "ink" }],
      min: 100, max: 100_000, log: true,
      ticks: [{ value: 100, label: "100" }, { value: 1000, label: "1k" }, { value: 10_000, label: "10k" }, { value: 100_000, label: "100k" }],
      periods: yearStarts(dates, 5),
      note: "Cubic feet per second, log scale",
    },
    tableFrames: months.flatMap((m, i) => (m.month.endsWith("-01") || chapters.some((c) => c.frame === i) || i === last ? [i] : [])),
    frameMs: 70,
    highlights: [
      { label: `Highest, ${monthLabel(months[hi].month)}`, value: Math.round(v[hi]).toLocaleString("en-US") + " cfs" },
      { label: `Lowest, ${monthLabel(months[lo].month)}`, value: Math.round(v[lo]).toLocaleString("en-US") + " cfs" },
    ],
    related: { href: "district/upper-coast/", label: "Upper Coast conditions" },
  };
}

export const riverStory: StoryEntry = {
  slug: riverStorySlug,
  fallback: { title: "The Brazos at Richmond", topic: "Water", description: "This replay returns when the gauge readings are current.", related: { href: "district/upper-coast/", label: "Upper Coast conditions" } },
  build: buildRiverStory,
  featured: () => false,
};
