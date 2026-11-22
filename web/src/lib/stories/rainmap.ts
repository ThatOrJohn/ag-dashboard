// This year's rain, one day at a time, county by county. Chapters come from the data: the wettest day statewide,
// the biggest single-county day, the longest dry spell, and the latest day.
import { day } from "../format";
import { chapterCaptions, type Story, type StoryContext, type StoryEntry } from "./model";

export const rainMapStorySlug = "texas-rain-day-by-day";
/** A statewide average below this counts as a dry day. */
const DRY = 0.02;
const inch = (v: number) => v.toFixed(2) + " inches";

export function buildRainMapStory({ data, latest }: StoryContext): Story | null {
  const r = data.rain;
  const days = r?.days.filter((d) => d.mean_in != null) ?? [];
  if (!r || days.length < 30 || latest.sources.nclimgrid?.stale) return null;
  const name = (f: string) => (latest.counties[f]?.name ?? f) + " County";
  const mean = days.map((d) => d.mean_in!);
  let total = 0;
  const totals = mean.map((m) => (total = Math.round((total + m) * 100) / 100));
  const label = (i: number) => day(days[i].date, days[i].date);
  const last = days.length - 1;
  const wet = mean.indexOf(Math.max(...mean));
  const maxes = days.map((d) => d.max?.in ?? 0);
  const big = maxes.indexOf(Math.max(...maxes));
  let dry = { start: -1, len: 0 }, cur = 0;
  mean.forEach((m, i) => {
    cur = m < DRY ? cur + 1 : 0;
    if (cur > dry.len) dry = { start: i - cur + 1, len: cur };
  });
  const year = days[0].date.slice(0, 4);

  const chapters: { frame: number; label: string; caption: string }[] = [
    { frame: 0, label: "Jan. 1", caption: `Every day of ${year} so far: each county is shaded by that day’s rain. Watch storms sweep across the state.` },
    { frame: wet, label: "Wettest day", caption: `${label(wet)}: the wettest day of the year statewide, averaging ${inch(mean[wet])} across Texas.` },
    { frame: big, label: "Biggest downpour", caption: `${label(big)}: ${name(days[big].max!.fips)} gets ${inch(maxes[big])}, the most any county saw in one day this year.` },
    { frame: last, label: "Latest", caption: `Through ${label(last)}, the statewide average adds up to ${inch(totals[last])} of rain this year.` },
  ];
  if (dry.len >= 5 && !chapters.some((c) => c.frame === dry.start)) {
    chapters.push({ frame: dry.start, label: "Dry spell",
      caption: `From ${label(dry.start)}, Texas goes ${dry.len} days in a row with almost no rain anywhere, the longest dry spell this year.` });
  }
  chapters.sort((a, b) => a.frame - b.frame);
  const captions = chapterCaptions(days.length, chapters);
  const firsts = days.flatMap((d, i) => (d.date.endsWith("-01") ? [{ frame: i, label: day(d.date, d.date).replace(/ 1$/, "") }] : []));

  return {
    slug: rainMapStorySlug,
    topic: "Rain",
    period: `Jan. 1 – ${day(days[last].date, days[last].date)}, ${year}`,
    title: `Every rainy day of ${year}, county by county`,
    description: `${days.length} days of NOAA county rainfall in one animated map, from the wettest statewide day (${label(wet)}) to a ${maxes[big].toFixed(2)}-inch downpour in ${name(days[big].max!.fips)}.`,
    metric: "Rain that day",
    frameLabel: "Day",
    series: [
      { name: "Texas average that day", unit: "inches" }, { name: "Texas average so far this year", unit: "inches" },
      { name: "Wettest county that day", unit: "inches" },
    ],
    frames: days.map((d, i) => ({ date: d.date, label: label(i), values: [mean[i], totals[i], d.max?.in ?? null], caption: captions[i] })),
    chapters: chapters.map(({ frame, label }) => ({ frame, label })),
    takeaway: {
      title: `Texas averaged ${inch(totals[last])} of rain through ${label(last)}`,
      text: `Rain fell unevenly: the wettest day statewide (${label(wet)}) averaged ${inch(mean[wet])}, while ${name(days[big].max!.fips)} got ${inch(maxes[big])} on ${label(big)} alone.`
        + (dry.len >= 5 ? ` The longest dry spell lasted ${dry.len} days.` : ""),
    },
    source: "nclimgrid",
    method: "NOAA nClimGrid daily county averages. The Texas average weights counties by land area and is my own figure. Recent days can be revised as NOAA adds station reports. The table lists the first of each month and every chapter.",
    visual: { kind: "rainmap", fips: r.counties, maps: days.map((d) => d.map), classes: r.classes, tops: days.map((d) => (d.max ? name(d.max.fips) : null)) },
    timeline: {
      series: [{ index: 0, label: "Texas average that day", mark: "bars", tone: "green" }],
      min: 0, max: Math.max(0.5, Math.ceil(Math.max(...mean) * 4) / 4),
      ticks: [{ value: 0, label: "0" }, { value: Math.max(0.5, Math.ceil(Math.max(...mean) * 4) / 4), label: Math.max(0.5, Math.ceil(Math.max(...mean) * 4) / 4).toFixed(2) + "″" }],
      periods: firsts.slice(1),
      note: "Statewide average rain per day",
    },
    tableFrames: days.flatMap((d, i) => (d.date.endsWith("-01") || chapters.some((c) => c.frame === i) || i === last ? [i] : [])),
    frameMs: 110,
    highlights: [{ label: "Texas average so far", value: totals[last].toFixed(2) + " in" }, { label: "Biggest county day", value: maxes[big].toFixed(2) + " in" }],
    related: { href: "", label: "Rain this week on the Texas overview" },
  };
}

export const rainMapStory: StoryEntry = {
  slug: rainMapStorySlug,
  fallback: { title: "Texas rain, day by day", topic: "Rain", description: "This replay returns when NOAA’s county rainfall is current.", related: { href: "", label: "Texas overview" } },
  build: buildRainMapStory,
  featured: () => true,
};
