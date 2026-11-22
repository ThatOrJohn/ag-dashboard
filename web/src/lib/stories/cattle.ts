// A year of feeder steer prices at the statewide weekly auction summary, with the herd on offer each week.
import { day } from "../format";
import { turningPoints } from "./drought";
import { chapterCaptions, yearStarts, type Story, type StoryContext, type StoryEntry } from "./model";

export const cattleStorySlug = "a-year-of-calf-prices";
const SWING = 50;   // $/cwt between turning points worth a chapter
const usd = (v: number) => "$" + v.toFixed(2);
/** Rough value of one 550 lb steer at a $/cwt price (a hundredweight is 100 lb). */
export const perHead = (cwt: number) => Math.round((cwt * 5.5) / 10) * 10;

export function buildCattleStory({ data, latest }: StoryContext): Story | null {
  const weeks = (data.cattle?.weeks ?? []).filter((w) => w.s500 != null);
  if (weeks.length < 12 || latest.sources.ams?.stale) return null;
  const p = weeks.map((w) => w.s500!);
  const label = (i: number) => day(weeks[i].date);
  const last = weeks.length - 1;
  const hi = p.indexOf(Math.max(...p));
  const lo = p.indexOf(Math.min(...p));
  const chapters: { frame: number; label: string; caption: string }[] = [
    { frame: 0, label: "Start", caption: `${label(0)}: 500–599 lb feeder steers bring ${usd(p[0])} per hundredweight, about $${perHead(p[0]).toLocaleString("en-US")} for a 550 lb calf. Each cow icon stands for 25 head sold in that class that week.` },
    { frame: hi, label: "Top price", caption: `${label(hi)}: ${usd(p[hi])} per hundredweight, the highest week in this run, about $${perHead(p[hi]).toLocaleString("en-US")} a calf.` },
    { frame: lo, label: "Lowest", caption: `${label(lo)}: ${usd(p[lo])}, the lowest week in this run.` },
    { frame: last, label: "Latest sale", caption: `${label(last)}: ${usd(p[last])}, ${p[last] >= p[0] ? "up" : "down"} ${usd(Math.abs(p[last] - p[0]))} from the first week shown.` },
  ];
  for (const { i, kind } of turningPoints(p, SWING)) {
    if (chapters.some((c) => Math.abs(c.frame - i) < 3)) continue;
    chapters.push({ frame: i, label: kind === "high" ? `${label(i)} high` : `${label(i)} low`,
      caption: `${label(i)}: prices turn ${kind === "high" ? "down" : "up"} from ${usd(p[i])}.` });
  }
  const kept = chapters.filter((c, i) => chapters.findIndex((o) => o.frame === c.frame) === i).sort((a, b) => a.frame - b.frame);
  const captions = chapterCaptions(weeks.length, kept);
  const all = weeks.flatMap((w) => [w.s500, w.s700].filter((x): x is number => x != null));
  const yMin = Math.floor(Math.min(...all) / 50) * 50, yMax = Math.ceil(Math.max(...all) / 50) * 50;
  const ticks = Array.from({ length: (yMax - yMin) / 50 + 1 }, (_, k) => yMin + k * 50)
    .filter((t, k, a) => k === 0 || k === a.length - 1 || (yMax - yMin) / 50 <= 4).map((t) => ({ value: t, label: "$" + t }));

  return {
    slug: cattleStorySlug,
    topic: "Cattle",
    period: `${day(weeks[0].date)} – ${day(weeks[last].date)}`,
    title: "A year of Texas calf prices",
    description: `${weeks.length} weekly sales of feeder steers across Texas auctions, from ${usd(p[lo])} to ${usd(p[hi])} per hundredweight for 500–599 lb calves.`,
    metric: "Feeder steers, Texas weekly auction summary",
    frameLabel: "Sale week",
    series: [
      { name: "500–599 lb, $/cwt", unit: "usd_cwt" }, { name: "700–799 lb, $/cwt", unit: "usd_cwt" },
      { name: "500–599 lb, head", unit: "head" }, { name: "700–799 lb, head", unit: "head" },
    ],
    frames: weeks.map((w, i) => ({ date: w.date, label: label(i), values: [w.s500, w.s700, w.h500, w.h700], caption: captions[i] })),
    chapters: kept.map(({ frame, label }) => ({ frame, label })),
    takeaway: {
      title: `A 550 lb calf swung by about $${(perHead(p[hi]) - perHead(p[lo])).toLocaleString("en-US")} in value over these ${weeks.length} weeks`,
      text: `At ${usd(p[hi])} per hundredweight (${label(hi)}), a 550 lb steer was worth about $${perHead(p[hi]).toLocaleString("en-US")}; at ${usd(p[lo])} (${label(lo)}), about $${perHead(p[lo]).toLocaleString("en-US")}. Per-calf values are my rough conversion, not reported prices.`,
    },
    source: "ams",
    method: "Weighted average prices for Medium and Large No. 1 feeder steers from USDA AMS’s Texas Weekly Cattle Auction Summary, with the head sold in each class. Per-calf values multiply the price by 5.5 hundredweight.",
    visual: { kind: "cattle" },
    timeline: {
      series: [{ index: 0, label: "500–599 lb", mark: "line", tone: "orange" }, { index: 1, label: "700–799 lb", mark: "line", tone: "ink" }],
      min: yMin, max: yMax, ticks,
      periods: yearStarts(weeks.map((w) => w.date)),
      note: "$ per hundredweight",
    },
    frameMs: 420,
    highlights: [{ label: "Latest, 500–599 lb", value: usd(p[last]) }, { label: "Year’s high", value: usd(p[hi]) }],
    related: { href: "for/cattle-hay/", label: "Cattle & Hay dashboard" },
  };
}

export const cattleStory: StoryEntry = {
  slug: cattleStorySlug,
  fallback: { title: "A year of Texas calf prices", topic: "Cattle", description: "This replay returns when the weekly auction summary is current.", related: { href: "for/cattle-hay/", label: "Cattle & Hay dashboard" } },
  build: buildCattleStory,
  featured: () => false,
};
