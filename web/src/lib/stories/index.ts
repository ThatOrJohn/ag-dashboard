// The story registry. Every entry keeps a stable URL; each build decides whether its data supports the story
// (stale sources show the entry's fallback instead), and which stories lead the collection page.
import { loadLatest, loadStoryData } from "../data";
import { cottonStory } from "./cotton";
import { droughtStory } from "./drought";
import type { Story, StoryEntry, StoryFallback } from "./model";
import { cattleStory } from "./cattle";
import { censusStory } from "./census";
import { rainStory } from "./rain";
import { rainMapStory } from "./rainmap";
import { reservoirStory } from "./reservoirs";
import { riverStory } from "./river";
import { wellsStory } from "./wells";

export * from "./model";
export { cottonHeadline, cottonStorySlug } from "./cotton";
export { droughtStorySlug, droughtStoryTitle } from "./drought";
export { rainStorySlug } from "./rain";

export const storyEntries: readonly StoryEntry[] = [
  droughtStory, rainMapStory, cottonStory, reservoirStory, wellsStory, riverStory, cattleStory, censusStory, rainStory,
];
export const storiesDescription = "Animated replays of Texas drought, rain, water, harvests, cattle prices and farms, built from public data.";

export interface BuiltStory { slug: string; story: Story | null; fallback: StoryFallback; featured: boolean }

export function buildStories(ctx = { latest: loadLatest(), data: loadStoryData() }): BuiltStory[] {
  return storyEntries.map((entry) => {
    const story = entry.build(ctx);
    return { slug: entry.slug, story, fallback: entry.fallback, featured: story ? entry.featured(ctx, story) : false };
  });
}
