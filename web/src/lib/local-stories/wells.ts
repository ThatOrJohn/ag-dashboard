// Ogallala monitoring wells, one winter reading a year. Each well joins the story when its record starts.
import { chapterCaptions, words, type Story, type StoryContext, type StoryEntry } from "../stories/model";

export const wellsStorySlug = "ogallala-wells";
const ft = (v: number) => Math.round(v) + " feet";

export function buildWellsStory({ data, sources }: StoryContext): Story | null {
  const wells = (data.wells ?? []).filter((w) => w.winters.length >= 3);
  if (!wells.length || sources.twdb_groundwater?.stale) return null;
  const y0 = Math.min(...wells.map((w) => w.winters[0].year));
  const y1 = Math.max(...wells.map((w) => w.winters.at(-1)!.year));
  const years = Array.from({ length: y1 - y0 + 1 }, (_, i) => y0 + i);
  const at = (w: (typeof wells)[number], y: number) => w.winters.find((x) => x.year === y)?.depth_ft ?? null;
  const last = years.length - 1;
  const drops = wells.map((w) => ({ w, first: w.winters[0], last: w.winters.at(-1)!, drop: w.winters.at(-1)!.depth_ft - w.winters[0].depth_ft }));
  const biggest = [...drops].sort((a, b) => b.drop / (b.last.year - b.first.year) - a.drop / (a.last.year - a.first.year))[0];

  const chapters: { frame: number; label: string; caption: string }[] = [];
  for (const d of [...drops].sort((a, b) => a.first.year - b.first.year)) {
    const frame = d.first.year - y0;
    const existing = chapters.find((c) => c.frame === frame);
    const text = `${d.w.name}: water stands ${ft(d.first.depth_ft)} below the surface in the winter of ${d.first.year}.`;
    if (existing) existing.caption += " " + text;
    else chapters.push({ frame, label: frame === 0 ? String(d.first.year) : `${d.w.name.replace(" County well", "")} starts`, caption: text });
  }
  chapters.push({ frame: last, label: "Latest winter", caption: drops.map((d) =>
    `${d.w.name}: ${d.drop >= 0 ? "down" : "up"} ${ft(Math.abs(d.drop))} since ${d.first.year}.`).join(" ") });
  const captions = chapterCaptions(years.length, chapters);
  const maxDepth = Math.ceil(Math.max(...wells.flatMap((w) => w.winters.map((x) => x.depth_ft))) / 50) * 50 + 50;

  return {
    slug: wellsStorySlug,
    topic: "Water",
    period: `Winters ${y0}–${y1}`,
    title: "The Ogallala, one winter at a time",
    description: `Depth to water in ${words(wells.length)} High Plains monitoring wells. The ${biggest.w.name} has dropped ${ft(biggest.drop)} since ${biggest.first.year}.`,
    metric: "Depth to groundwater, winter reading",
    frameLabel: "Winter",
    series: wells.map((w) => ({ name: w.name, unit: "feet" as const })),
    frames: years.map((y, i) => ({ date: `${y}-02-01`, label: `Winter ${y}`, values: wells.map((w) => at(w, y)), caption: captions[i] })),
    chapters: chapters.sort((a, b) => a.frame - b.frame).map(({ frame, label }) => ({ frame, label })),
    takeaway: {
      title: drops.every((d) => d.drop > 0)
        ? `The water is deeper now in ${wells.length === 1 ? "this well" : `all ${words(wells.length)} wells`}`
        : "The wells have moved in different directions",
      text: drops.map((d) => `${d.w.name}: ${ft(d.first.depth_ft)} deep in ${d.first.year}, ${ft(d.last.depth_ft)} in ${d.last.year}.`).join(" ")
        + ` These are ${wells.length === 1 ? "one well" : `${words(wells.length)} wells`}, not the whole aquifer.`,
    },
    source: "twdb_groundwater",
    method: "Each value is the median of the Texas Water Development Board’s daily readings from January through March, before the irrigation season. Missing winters are left blank. Shafts share one depth scale.",
    visual: { kind: "wells", maxDepth, first: wells.map((w) => ({ year: w.winters[0].year, depth: w.winters[0].depth_ft })), links: wells.map((w) => w.url) },
    frameMs: 650,
    highlights: drops.slice(0, 3).map((d) => ({ label: `${d.w.name.replace(" County well", "")} since ${d.first.year}`, value: (d.drop >= 0 ? "−" : "+") + Math.round(Math.abs(d.drop)) + " ft" })),
    related: { href: "district/northern-high-plains/", label: "Northern High Plains conditions" },
  };
}

export const wellsStory: StoryEntry = {
  slug: wellsStorySlug,
  fallback: { title: "The Ogallala, one winter at a time", topic: "Water", description: "This replay returns when the well readings are current.", related: { href: "district/northern-high-plains/", label: "Northern High Plains conditions" } },
  build: buildWellsStory,
  featured: () => false,
};
