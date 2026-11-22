// Census of Agriculture, county by county: a dot per county sized by its number of farms. Only two census years
// exist, so the frames are steps through one comparison rather than invented years in between.
import { chapterCaptions, words, type Story, type StoryContext, type StoryEntry } from "./model";

export const censusStorySlug = "texas-farms-2017-2022";
const n = (v: number) => Math.round(v).toLocaleString("en-US");

export function buildCensusStory({ data, latest }: StoryContext): Story | null {
  const c = data.census;
  if (!c || latest.sources.census?.stale) return null;
  const [y0, y1] = c.years;
  const fips = Object.keys(c.counties).filter((f) => c.counties[f][0] != null && c.counties[f][1] != null);
  if (fips.length < 50) return null;
  const sum = (k: number) => fips.reduce((a, f) => a + (c.counties[f][k] ?? 0), 0);
  const farms = [sum(0), sum(1)], land = [sum(2), sum(3)];
  const avg = [land[0] / farms[0], land[1] / farms[1]];
  const name = (f: string) => latest.counties[f]?.name ?? f;
  const change = fips.map((f) => ({ f, d: c.counties[f][1]! - c.counties[f][0]! }));
  const losses = change.filter((x) => x.d < 0).sort((a, b) => a.d - b.d);
  const gains = change.filter((x) => x.d > 0).sort((a, b) => b.d - a.d);
  const list = (xs: typeof change) => xs.slice(0, 3).map((x) => `${name(x.f)} (${x.d > 0 ? "+" : "−"}${n(Math.abs(x.d))})`).join(", ");
  const diff = farms[1] - farms[0];

  const steps = [
    { year: 0 as const, highlight: "none" as const, label: String(y0),
      caption: `${y0}: the Census of Agriculture counts ${n(farms[0])} farms and ranches in Texas. Each dot is a county, sized by its number of farms.` },
    { year: 1 as const, highlight: "none" as const, label: String(y1),
      caption: `${y1}: ${n(farms[1])} farms, ${diff < 0 ? "down" : "up"} ${n(Math.abs(diff))} (${Math.abs(Math.round((diff / farms[0]) * 1000) / 10)}%). Outlines show each county’s ${y0} size.` },
    { year: 1 as const, highlight: "loss" as const, label: "Fewer farms",
      caption: `Farm numbers fell in ${losses.length} of ${fips.length} counties. The biggest drops: ${list(losses)}.` },
    { year: 1 as const, highlight: "gain" as const, label: "More farms",
      caption: gains.length ? `They rose in ${gains.length} counties, led by ${list(gains)}.` : "No county gained farms." },
    { year: 1 as const, highlight: "none" as const, label: "Bigger farms",
      caption: `Land in farms ${land[1] < land[0] ? "fell" : "rose"} ${Math.abs(Math.round(((land[1] - land[0]) / land[0]) * 1000) / 10)}%, ${Math.abs(land[1] - land[0]) / land[0] < Math.abs(diff) / farms[0] ? "less than" : "more than"} the number of farms, so the average farm went from ${n(avg[0])} to ${n(avg[1])} acres.` },
  ];
  const captions = chapterCaptions(steps.length, steps.map((s, frame) => ({ frame, caption: s.caption })));

  return {
    slug: censusStorySlug,
    topic: "Farms",
    period: `Census of Agriculture, ${y0} and ${y1}`,
    title: `Texas ${diff < 0 ? "lost" : "gained"} ${n(Math.abs(diff))} farms in ${words(y1 - y0)} years`,
    description: `County by county, how the number of Texas farms and ranches changed between the ${y0} and ${y1} Census of Agriculture, and what happened to the average farm’s size.`,
    metric: "Texas farms and ranches",
    frameLabel: "Step",
    series: [{ name: "Farms", unit: "count" }, { name: "Land in farms, acres", unit: "count" }, { name: "Average farm, acres", unit: "count" }],
    frames: steps.map((s, i) => ({ label: s.label, date: undefined, values: [farms[s.year], land[s.year], Math.round(avg[s.year])], caption: captions[i] })),
    chapters: steps.map((s, frame) => ({ frame, label: s.label })),
    takeaway: {
      title: `${diff < 0 ? "Fewer" : "More"}, ${avg[1] > avg[0] ? "bigger" : "smaller"} farms: ${n(avg[0])} → ${n(avg[1])} acres on average`,
      text: `Texas counted ${n(farms[0])} farms in ${y0} and ${n(farms[1])} in ${y1}. ${losses.length} counties lost farms and ${gains.length} gained them. The next census is in 2027.`,
    },
    source: "census",
    method: "County figures from the USDA NASS Census of Agriculture; statewide totals add up the counties. Average farm size is land in farms divided by farms. Dot area is proportional to farms.",
    visual: { kind: "census", fips, farms: fips.map((f) => [c.counties[f][0], c.counties[f][1]] as const), years: [y0, y1], steps: steps.map(({ year, highlight }) => ({ year, highlight })) },
    frameMs: 3000,
    highlights: [{ label: String(y0), value: n(farms[0]) }, { label: String(y1), value: n(farms[1]) }],
    related: { href: "", label: "County cards on the Texas map" },
  };
}

export const censusStory: StoryEntry = {
  slug: censusStorySlug,
  fallback: { title: "Texas farms, 2017 to 2022", topic: "Farms", description: "This comparison returns when Census of Agriculture figures are available.", related: { href: "", label: "Texas overview" } },
  build: buildCensusStory,
  featured: () => false,
};
