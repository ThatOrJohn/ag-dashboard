// Every Texas cotton harvest in the store, raced side by side on the calendar. Each lane is a season; at each
// step it shows that season's newest USDA report on or before the same calendar day.
import { day } from "../format";
import type { Latest } from "../types";
import { chapterCaptions, type Story, type StoryContext, type StoryEntry } from "./model";

export const cottonStorySlug = "texas-cotton-harvest-pace";
const cottonDashboard = { href: "for/cotton/", label: "Cotton dashboard" };
/** Calendar steps: weekly from Aug. 31 through Nov. 30. */
const STEPS = Array.from({ length: 14 }, (_, i) => {
  const d = new Date(Date.UTC(2001, 7, 31 + i * 7));
  return [d.getUTCMonth() + 1, d.getUTCDate()] as const;
});
/** A lane holding at a report older than this says so. */
const GAP_DAYS = 10;
/** A gap between reports this long gets its own chapter. */
const MISSING_DAYS = 21;

const iso = (y: number, [m, d]: readonly [number, number]) => `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
const WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];
const count = (n: number) => WORDS[n] ?? String(n);
const daysBetween = (a: string, b: string) => Math.round((Date.parse(b) - Date.parse(a)) / 86_400_000);

export interface CottonHeadline { pct: number; baseline: number; lastYear: number | null; weekEnding: string; gap: number; ahead: boolean }

/** The statewide harvest compared with its five-year average, when a fresh in-season report shows a real gap. */
export function cottonHeadline(latest: Latest): CottonHeadline | null {
  const progress = latest.texas.crops.cotton?.progress;
  if (latest.sources.nass?.stale !== false || progress?.status !== "fresh" || !progress.week_ending) return null;
  const harvest = progress.stages?.find(({ stage }) => stage === "harvested");
  if (!harvest || harvest.avg_5yr == null) return null;
  const { pct, avg_5yr: baseline, last_year: lastYear } = harvest;
  const valid = (v: number | null): v is number => v != null && Number.isFinite(v) && v >= 0 && v <= 100;
  if (!valid(pct) || !valid(baseline) || pct < 20 || pct > 95 || Math.abs(pct - baseline) < 5) return null;
  return { pct, baseline, lastYear: valid(lastYear) ? lastYear : null, weekEnding: progress.week_ending,
           gap: Math.abs(pct - baseline), ahead: pct > baseline };
}

export function buildCottonStory({ data, latest }: StoryContext): Story | null {
  const seasons = [...(data.cotton?.seasons ?? [])].filter((s) => s.reports.length).sort((a, b) => b.year - a.year);
  if (seasons.length < 2 || latest.sources.nass?.stale) return null;
  const headline = cottonHeadline(latest);
  const thisYear = Number(latest.asof.slice(0, 4));
  const current = seasons.findIndex((s) => s.year === thisYear);

  const lanes = STEPS.map((step) => seasons.map((s) => {
    const on = iso(s.year, step);
    const report = s.reports.filter((r) => r.date <= on).at(-1) ?? null;
    let note: string | null = null;
    if (!report) note = "No report yet";
    else if (daysBetween(report.date, on) > GAP_DAYS) {
      note = s.year === thisYear && report === s.reports.at(-1) ? `Latest report ${day(report.date, report.date)}` : `No report since ${day(report.date, report.date)}`;
    }
    return { pct: report?.pct ?? null, note };
  }));
  const label = (i: number) => day(iso(2001, STEPS[i]), "2001");
  const valuesAt = (i: number) => lanes[i].map((l) => l.pct);
  const leader = (i: number) => {
    const v = valuesAt(i);
    const best = Math.max(...v.map((x) => x ?? -1));
    return best < 0 ? null : { year: seasons[v.indexOf(best)].year, pct: best };
  };
  const at = (i: number) => {
    const lead = leader(i);
    const cur = current >= 0 ? lanes[i][current] : null;
    if (!lead) return `By ${label(i)}, no season has a report yet.`;
    if (cur?.pct === lead.pct && !cur.note) return `By ${label(i)}, this season is as far along as any, at ${lead.pct}% harvested.`;
    const mine = cur?.pct != null && !cur.note ? ` This season is at ${cur.pct}%.` : "";
    return `By ${label(i)}, the ${lead.year} season is furthest along at ${lead.pct}% harvested.${mine}`;
  };

  const chapters: { frame: number; label: string; caption: string }[] = [
    { frame: 0, label: "Late August", caption: at(0) + ((leader(0)?.pct ?? 0) < 50 ? " Most of the crop is still in the field." : "") },
    { frame: 5, label: "Early October", caption: at(5) },
    { frame: 9, label: "Early November", caption: at(9) },
  ];
  // A long silence in a past season's reports gets its own chapter, so a frozen lane is explained.
  for (const s of seasons) {
    if (s.year === thisYear) continue;
    for (let r = 1; r < s.reports.length; r++) {
      const [a, b] = [s.reports[r - 1], s.reports[r]];
      if (daysBetween(a.date, b.date) < MISSING_DAYS) continue;
      const frame = STEPS.findIndex((step) => daysBetween(a.date, iso(s.year, step)) > GAP_DAYS);
      if (frame > 0 && !chapters.some((c) => c.frame === frame)) {
        chapters.push({ frame, label: `${s.year} gap`, caption: `USDA published no Texas cotton progress between ${day(a.date, a.date)} and ${day(b.date)}, so the ${s.year} lane holds at ${a.pct}% until reports resume.` });
      }
    }
  }
  const last = STEPS.length - 1;
  chapters.push({ frame: last, label: "End of November", caption: headline
    ? `Latest report, ${day(headline.weekEnding)}: Texas is ${headline.pct}% harvested, ${headline.gap} points ${headline.ahead ? "ahead of" : "behind"} the five-year average of ${headline.baseline}%.`
    : at(last) });
  chapters.sort((a, b) => a.frame - b.frame);
  const captions = chapterCaptions(STEPS.length, chapters);
  const frames = STEPS.map((step, i) => ({ label: label(i), values: valuesAt(i), caption: captions[i] }));

  const latestCurrent = current >= 0 ? seasons[current].reports.at(-1)! : null;
  return {
    slug: cottonStorySlug,
    topic: "Cotton",
    period: `${seasons.at(-1)!.year}–${seasons[0].year} seasons`,
    title: headline ? `Texas cotton harvest is ${headline.ahead ? "ahead of" : "behind"} its usual pace` : `${count(seasons.length)[0].toUpperCase() + count(seasons.length).slice(1)} Texas cotton harvests, side by side`,
    description: headline
      ? `Texas reported ${headline.pct}% of cotton harvested by ${day(headline.weekEnding)}, ${headline.gap} percentage points ${headline.ahead ? "ahead of" : "behind"} the five-year average. Race this season against the last ${count(seasons.length - 1)}.`
      : `Race the last ${count(seasons.length)} Texas cotton harvests against each other, week by week, from late August through November.`,
    metric: "Texas cotton harvested",
    frameLabel: "Calendar week",
    series: seasons.map((s) => ({ name: s.year === thisYear ? `${s.year} (this season)` : String(s.year), unit: "percent" as const })),
    frames,
    chapters: chapters.map(({ frame, label }) => ({ frame, label })),
    takeaway: headline
      ? { title: `${100 - headline.pct}% of the Texas crop remains to harvest`,
          text: `At the same point in the five preceding seasons, an average of ${100 - headline.baseline}% was still in the field${headline.lastYear != null ? `; last season, ${100 - headline.lastYear}%` : ""}. These are USDA statewide estimates.` }
      : (() => {
          const early = Math.max(...valuesAt(5).map((v) => v ?? 0));
          const end = lanes[last].filter((l) => l.pct != null && !l.note).map((l) => l.pct as number);
          return { title: early < 50 ? `Most of the Texas harvest comes after ${label(5)}` : "Texas cotton seasons run at different speeds",
                   text: `By ${label(5)}, no season in these lanes was past ${early}% harvested.` + (end.length ? ` By ${label(last)}, the seasons with a report that week ranged from ${Math.min(...end)}% to ${Math.max(...end)}%.` : "") };
        })(),
    source: "nass",
    method: "Each lane shows that season’s newest USDA NASS statewide report on or before the same calendar day. A lane that holds still is waiting on its next report.",
    visual: { kind: "harvest", current: current >= 0 ? current : null, notes: lanes.map((l) => l.map((x) => x.note)) },
    frameMs: 950,
    highlights: [
      ...(latestCurrent ? [{ label: `This season, ${day(latestCurrent.date, latestCurrent.date)}`, value: latestCurrent.pct + "%" }] : []),
      ...(headline ? [{ label: "Five-year average", value: headline.baseline + "%" }] : []),
    ],
    related: cottonDashboard,
  };
}

export const cottonStory: StoryEntry = {
  slug: cottonStorySlug,
  fallback: {
    title: "Texas cotton harvest pace",
    topic: "Cotton",
    description: "This race between seasons returns when the USDA statewide cotton reports are current.",
    related: cottonDashboard,
  },
  build: buildCottonStory,
  featured: ({ latest }) => cottonHeadline(latest) != null,
};
