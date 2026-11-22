import { cattleStory } from "./cattle";
import { rainStory } from "./rain";
import { reservoirStory } from "./reservoirs";
import { riverStory } from "./river";
import { wellsStory } from "./wells";
import type { StoryEntry } from "../stories/model";

export const localStoryAdapters: Readonly<Record<string, StoryEntry>> = {
  reservoirs: reservoirStory,
  wells: wellsStory,
  river: riverStory,
  cattle: cattleStory,
  rain: rainStory,
};

// Preserve the shipped slugs in the original state's scoped URLs.
export const originalSlugs: Readonly<Record<string, string>> = {
  "two-years-of-drought": "two-years-of-drought",
  "cotton-harvest-pace": "texas-cotton-harvest-pace",
  "texas-reservoirs-since-1950": "texas-reservoirs-since-1950",
  "ogallala-wells": "ogallala-wells",
  "brazos-at-richmond": "brazos-at-richmond",
  "a-year-of-calf-prices": "a-year-of-calf-prices",
  "farms-over-time": "texas-farms-2017-2022",
  "five-weeks-of-rain": "five-weeks-of-rain",
};

export const legacyStorySlugs = Object.values(originalSlugs);
