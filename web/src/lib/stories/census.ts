// Census of Agriculture, county by county: a dot per county sized by its number of farms. Only two census years
// exist, so the frames are steps through one comparison rather than invented years in between.
import { stateName } from "../geo";
import { chapterCaptions, words, type Story, type StoryContext, type StoryEntry } from "./model";

export const censusStorySlug = "farms-over-time";
const n = (v: number) => Math.round(v).toLocaleString("en-US");

export function buildCensusStory({ area, data, sources, counties, overview }: StoryContext): Story | null {
  if (!data.census || sources.census?.stale) return null;
  const records = area.level === "us" ? data.census.states : data.census.counties;
  if (!records) return null;
  const [y0, y1] = data.census.years;
  const unit = area.level === "us" ? "state" : "county";
  const units = area.level === "us" ? "states" : "counties";
  const fips = Object.keys(records).filter((f) => records[f][0] != null && records[f][1] != null);
  if (!fips.length) return null;
  const sum = (k: number) => fips.reduce((a, f) => a + (records[f][k] ?? 0), 0);
  const farms = [sum(0), sum(1)], land = [sum(2), sum(3)];
  if (farms.some((v) => v <= 0)) return null;
  const landComplete = (k: number) => fips.every((f) => records[f][k] != null);
  const avg = [landComplete(2) ? land[0] / farms[0] : null, landComplete(3) ? land[1] / farms[1] : null];
  const name = (f: string) => area.level === "us" ? stateName(f) : counties[f]?.name ?? f;
  const change = fips.map((f) => ({ f, d: records[f][1]! - records[f][0]! }));
  const losses = change.filter((x) => x.d < 0).sort((a, b) => a.d - b.d);
  const gains = change.filter((x) => x.d > 0).sort((a, b) => b.d - a.d);
  const list = (xs: typeof change) => xs.slice(0, 3).map((x) => `${name(x.f)} (${x.d > 0 ? "+" : "−"}${n(Math.abs(x.d))})`).join(", ");
  const diff = farms[1] - farms[0];

  const steps = [
    { year: 0 as const, highlight: "none" as const, label: String(y0),
      caption: `${y0}: the Census of Agriculture counts ${n(farms[0])} farms and ranches in ${area.phrase} across the ${fips.length} ${units} reporting in both years. Each dot is a ${unit}, sized by its number of farms.` },
    { year: 1 as const, highlight: "none" as const, label: String(y1),
      caption: `${y1}: ${n(farms[1])} farms, ${diff < 0 ? "down" : "up"} ${n(Math.abs(diff))} (${Math.abs(Math.round((diff / farms[0]) * 1000) / 10)}%). Outlines show each ${unit}’s ${y0} size.` },
    { year: 1 as const, highlight: "loss" as const, label: "Fewer farms",
      caption: losses.length ? `Farm numbers fell in ${losses.length} of ${fips.length} ${units}. The biggest drops: ${list(losses)}.` : `No ${unit} lost farms.` },
    { year: 1 as const, highlight: "gain" as const, label: "More farms",
      caption: gains.length ? `They rose in ${gains.length} ${units}, led by ${list(gains)}.` : `No ${unit} gained farms.` },
    { year: 1 as const, highlight: "none" as const, label: "Farm size",
      caption: avg[0] != null && avg[1] != null
        ? `Average farm size went from ${n(avg[0])} to ${n(avg[1])} acres.`
        : "Some land in farms figures are unpublished, so average farm size is unavailable for at least one year." },
  ];
  const captions = chapterCaptions(steps.length, steps.map((s, frame) => ({ frame, caption: s.caption })));

  return {
    slug: censusStorySlug,
    topic: "Farms",
    period: `Census of Agriculture, ${y0} and ${y1}`,
    title: diff === 0 ? `Farm counts held steady in ${area.phrase}`
      : `${n(Math.abs(diff))} ${diff < 0 ? "fewer" : "more"} farms in ${area.phrase} over ${words(y1 - y0)} years`,
    description: `How farm numbers and average farm size changed in ${area.phrase} between the ${y0} and ${y1} Census of Agriculture.`,
    metric: `Farms and ranches in ${area.phrase}`,
    frameLabel: "Step",
    series: [{ name: "Farms", unit: "count" }, { name: "Land in farms, acres", unit: "count" }, { name: "Average farm, acres", unit: "count" }],
    frames: steps.map((s, i) => ({ label: s.label, date: undefined, values: [farms[s.year], landComplete(s.year + 2) ? land[s.year] : null, avg[s.year]], caption: captions[i] })),
    chapters: steps.map((s, frame) => ({ frame, label: s.label })),
    takeaway: {
      title: avg[0] != null && avg[1] != null
        ? `Average farm size: ${n(avg[0])} → ${n(avg[1])} acres` : "How farm counts changed",
      text: `Across the ${units} reporting in both years, farms numbered ${n(farms[0])} in ${y0} and ${n(farms[1])} in ${y1}. ${losses.length} ${units} lost farms and ${gains.length} gained them.`,
    },
    source: "census",
    method: `Totals add up USDA NASS Census of Agriculture figures for ${units} reporting in both years. Average farm size is land in farms divided by farms. Dot area is proportional to farms.`,
    visual: { kind: "census", fips, farms: fips.map((f) => [records[f][0], records[f][1]] as const), years: [y0, y1], steps: steps.map(({ year, highlight }) => ({ year, highlight })) },
    frameMs: 3000,
    highlights: [{ label: String(y0), value: n(farms[0]) }, { label: String(y1), value: n(farms[1]) }],
    related: overview,
  };
}

export const censusStory: StoryEntry = {
  slug: censusStorySlug,
  fallback: ({ area, overview }) => ({ title: `Farms in ${area.phrase}`, topic: "Farms", description: "This comparison returns when Census of Agriculture figures are available.", related: overview }),
  build: buildCensusStory,
  featured: () => false,
};
