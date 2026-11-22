// The shape every story shares. A story is a list of frames (one per report week or day) that the player steps
// through; `visual` says which animation draws them. Every frame's values also fill the story's table, so the
// facts never depend on the animation.
import { inches } from "../format";
import type { Latest, SourceKey, StoryData } from "../types";

export type StoryUnit = "percent" | "inches" | "count" | "feet" | "cfs" | "usd_cwt" | "head";

export interface StoryFrame {
  label: string;
  date?: string;
  values: readonly (number | null)[];
  caption: string;
}

export type StoryVisual =
  /** Every county's drought category on each frame's map, one character per county ("-", "0"–"4", "?"). */
  | { kind: "drought"; fips: readonly string[]; maps: readonly string[] }
  /** Rain that fell on each frame's day, per series (the frame values are the running totals). */
  | { kind: "rain"; daily: readonly (readonly number[])[]; scaleMax: number }
  /** One field lane per season. `notes` explains a lane that is holding at an older report. */
  | { kind: "harvest"; current: number | null; notes: readonly (readonly (string | null)[])[] }
  /** A reservoir cross-section; frame value 0 is percent full. */
  | { kind: "reservoir" }
  /** One well shaft per series; frame values are depth to water in feet (null: no winter reading). */
  | { kind: "wells"; maxDepth: number; first: readonly ({ year: number; depth: number } | null)[]; links: readonly (string | null)[] }
  /** A river seen from above; frame value 0 is mean flow. `typical` is the median for that calendar month. */
  | { kind: "river"; typical: readonly number[]; maxFlow: number }
  /** Price tags and a herd: values are [500 lb $/cwt, 700 lb $/cwt, 500 lb head, 700 lb head]. */
  | { kind: "cattle" }
  /** A dot per county sized by farms. Each frame shows one census year and may highlight losses or gains. */
  | { kind: "census"; fips: readonly string[]; farms: readonly (readonly [number | null, number | null])[]; years: readonly [number, number];
      steps: readonly { year: 0 | 1; highlight: "none" | "loss" | "gain" }[] };

/** A strip chart under the visual with a cursor on the current frame; tap it to jump. */
export interface StoryTimeline {
  series: readonly { index: number; label: string; mark: "area" | "line" | "bars"; tone: "amber" | "danger" | "green" | "ink" | "orange" }[];
  min: number;
  max: number;
  log?: boolean;
  ticks: readonly { value: number; label: string }[];
  /** Frame indexes where a new year (or other period) starts, with its label. */
  periods: readonly { frame: number; label: string }[];
  note: string;
}

export interface Story {
  slug: string;
  topic: string;
  period: string;
  title: string;
  description: string;
  metric: string;
  frameLabel: string;
  series: readonly { name: string; unit: StoryUnit; slug?: string }[];
  frames: readonly StoryFrame[];
  /** Frames worth stopping on. Playback pauses on each so its caption can be read. */
  chapters: readonly { frame: number; label: string }[];
  takeaway: { title: string; text: string };
  source: SourceKey;
  method: string;
  visual: StoryVisual;
  timeline?: StoryTimeline;
  /** Frames listed in the values table; all frames when absent. Long stories list a sample plus every chapter. */
  tableFrames?: readonly number[];
  frameMs: number;
  /** A few figures for the story's card on the collection page. */
  highlights: readonly { label: string; value: string }[];
  related?: { href: string; label: string };
}

export interface StoryFallback {
  title: string;
  topic: string;
  description: string;
  related: { href: string; label: string };
}

export interface StoryContext { latest: Latest; data: StoryData }

export interface StoryEntry {
  slug: string;
  /** Shown at the story's stable URL when its data is stale or out of range on this build. */
  fallback: StoryFallback;
  build: (ctx: StoryContext) => Story | null;
  /** Listed first, as a large card, on the collection page. */
  featured: (ctx: StoryContext, story: Story) => boolean;
}

/** Hold on a chapter frame this long during playback. */
export const chapterHoldMs = 2600;

export function formatStoryValue(value: number | null, unit: StoryUnit): string {
  if (value == null) return "—";
  if (unit === "inches") return inches(value);
  if (unit === "count" || unit === "head") return Math.round(value).toLocaleString("en-US");
  if (unit === "feet") return value.toFixed(1) + " ft";
  if (unit === "cfs") return Math.round(value).toLocaleString("en-US") + " cfs";
  if (unit === "usd_cwt") return "$" + value.toFixed(2);
  return (Number.isInteger(value) ? value : value.toFixed(1)) + "%";
}

/** Each frame's caption is its latest chapter's narration, so text stays put while playback runs. */
export function chapterCaptions(count: number, chapters: readonly { frame: number; caption: string }[]): string[] {
  const sorted = [...chapters].sort((a, b) => a.frame - b.frame);
  return Array.from({ length: count }, (_, i) => [...sorted].reverse().find(({ frame }) => frame <= i)?.caption ?? sorted[0]?.caption ?? "");
}

/** Frame indexes where the calendar year changes, for timeline labels. */
export function yearStarts(dates: readonly string[], every = 1): { frame: number; label: string }[] {
  const out: { frame: number; label: string }[] = [];
  dates.forEach((d, i) => {
    const y = Number(d.slice(0, 4));
    if (i > 0 && y !== Number(dates[i - 1].slice(0, 4)) && y % every === 0) out.push({ frame: i, label: String(y) });
  });
  return out;
}

/** "2026-05" → "May 2026". */
export function monthLabel(ym: string): string {
  const M = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."];
  return `${M[Number(ym.slice(5, 7)) - 1]} ${ym.slice(0, 4)}`;
}

const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];
/** AP style: spell out whole numbers under 10. */
export const words = (n: number) => (Number.isInteger(n) && n >= 0 && n < 10 ? WORDS[n] : n.toLocaleString("en-US"));
