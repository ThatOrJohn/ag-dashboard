// The shape every story shares. A story is a list of frames (one per report week or day) that the player steps
// through; `visual` says which animation draws them. Every frame's values also fill the story's table, so the
// facts never depend on the animation.
import { inches } from "../format";
import type { Latest, SourceKey, StoryData } from "../types";

export type StoryUnit = "percent" | "inches" | "count";

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
  | { kind: "harvest"; current: number | null; notes: readonly (readonly (string | null)[])[] };

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
  if (unit === "count") return String(value);
  return (Number.isInteger(value) ? value : value.toFixed(1)) + "%";
}

/** Each frame's caption is its latest chapter's narration, so text stays put while playback runs. */
export function chapterCaptions(count: number, chapters: readonly { frame: number; caption: string }[]): string[] {
  const sorted = [...chapters].sort((a, b) => a.frame - b.frame);
  return Array.from({ length: count }, (_, i) => [...sorted].reverse().find(({ frame }) => frame <= i)?.caption ?? sorted[0]?.caption ?? "");
}
