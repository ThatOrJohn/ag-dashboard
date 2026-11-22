import fs from "node:fs";
import path from "node:path";
import { parse } from "yaml";
import { dataRoot, loadDistrict, loadLatest, loadNationalStorySnapshot, loadStoryData, REGION } from "../data";
import { legacyStorySlugs, localStoryAdapters, originalSlugs } from "../local-stories";
import type { DistrictFile, Latest, StoryData } from "../types";
import { censusStory } from "./census";
import { cottonStory } from "./cotton";
import { droughtStory } from "./drought";
import type { Story, StoryArea, StoryContext, StoryDisplayContext, StoryEntry, StoryFallback } from "./model";

export * from "./model";
export { legacyStorySlugs };
export { cottonHeadline, cottonStorySlug } from "./cotton";
export { droughtStorySlug, droughtStoryTitle } from "./drought";

const templates = [droughtStory, cottonStory, censusStory];
export const storiesDescription = "Animated replays of drought, rain, water, harvests, cattle prices and farms, built from public data.";

interface RegionConfig {
  id: string;
  name: string;
  phrase?: string;
  state_fips: string;
  districts: { slug: string; name: string; phrase?: string }[];
  sources?: { nass?: { weekly?: { id: string }[] } };
  stories?: Record<string, unknown>;
}

export interface BuiltStory {
  slug: string;
  area: StoryArea;
  path: string;
  image: string;
  story: Story | null;
  fallback: StoryFallback;
  featured: boolean;
  context: StoryDisplayContext;
}

export function buildAreaStories(context: StoryContext, supportsCotton: boolean, local: string[] = []): BuiltStory[] {
  const { area, counties, sources } = context;
  const scope = area.level === "district" ? [area.stateId, area.id] : [area.id];
  const entries: StoryEntry[] = templates.filter((entry) => entry !== cottonStory || supportsCotton);
  for (const key of local) {
    if (!Object.hasOwn(localStoryAdapters, key)) throw new Error(`Unknown story adapter "${key}" in ${area.id}`);
    entries.push(localStoryAdapters[key]);
  }
  return entries.map((entry) => {
    const slug = area.level === "state" && area.id === "tx" ? originalSlugs[entry.slug] ?? entry.slug : entry.slug;
    const story = entry.build(context);
    const fallback = typeof entry.fallback === "function" ? entry.fallback(context) : entry.fallback;
    const segments = [...scope, slug];
    return {
      slug: entry.slug, area, path: segments.join("/"), image: `story-${segments.join("-")}`,
      story, fallback, featured: story ? entry.featured(context, story) : false, context: { area, counties, sources },
    };
  });
}

function readConfig(region: string): RegionConfig {
  return parse(fs.readFileSync(path.join(process.cwd(), "..", "regions", `${region}.yaml`), "utf8"));
}

function storyContext(area: StoryArea, latest: Latest, data: StoryData): StoryContext {
  const hasDashboard = area.level === "district" ? area.stateId === REGION : area.level === "state" && area.id === REGION;
  const overview = hasDashboard
    ? { href: area.level === "district" ? `district/${area.id}/` : "", label: `${area.name} overview` }
    : { href: `stories/#${area.level === "district" ? area.stateId : area.id}`, label: `${area.name} stories` };
  return {
    area, data, asof: latest.asof, sources: latest.sources, counties: latest.counties ?? {},
    cottonProgress: latest.texas?.crops?.cotton?.progress, overview,
    cottonDashboard: hasDashboard && area.level === "state" && latest.personas?.some(({ id }) => id === "cotton")
      ? { href: "for/cotton/", label: "Cotton dashboard" } : undefined,
  };
}

export function districtStoryData(data: StoryData, district: Pick<DistrictFile, "counties" | "drought_history">): StoryData {
  const keep = new Set(district.counties.map(({ fips }) => fips));
  const roster = data.drought?.counties ?? [];
  const positions = roster.flatMap((fips, i) => keep.has(fips) ? [i] : []);
  const history = new Map(district.drought_history.map(({ date, ...coverage }) => [date, coverage]));
  return {
    cotton: null,
    drought: data.drought && positions.length ? {
      counties: positions.map((i) => roster[i]),
      weeks: data.drought.weeks.map(({ date, map }) => ({
        date, map: positions.map((i) => map[i] ?? "?").join(""), coverage: history.get(date),
      })),
    } : null,
    census: data.census?.counties ? {
      years: data.census.years,
      counties: Object.fromEntries(Object.entries(data.census.counties).filter(([fips]) => keep.has(fips))),
    } : null,
  };
}

function districtStories(config: RegionConfig, latest: Latest, data: StoryData, district: DistrictFile): BuiltStory[] {
  const settings = config.districts.find(({ slug }) => slug === district.slug);
  const area: StoryArea = {
    level: "district", id: district.slug, name: district.name, phrase: settings?.phrase ?? `the ${district.name} district`,
    stateId: config.id, stateFips: config.state_fips,
  };
  return buildAreaStories(storyContext(area, latest, districtStoryData(data, district)), false);
}

export function buildDistrictStories(latest: Latest, district: DistrictFile): BuiltStory[] {
  const region = latest.region.id;
  return districtStories(readConfig(region), latest, loadStoryData(region), district);
}

export function buildStories(): BuiltStory[] {
  const regions = fs.readdirSync(dataRoot).filter((id) => fs.existsSync(path.join(dataRoot, id, "latest.json"))).sort();
  return regions.flatMap((region) => {
    const data = loadStoryData(region);
    if (region === "us") {
      const area: StoryArea = { level: "us", id: region, name: "United States", phrase: "the United States" };
      const snapshot = loadNationalStorySnapshot();
      return buildAreaStories({
        area, data, asof: snapshot.asof, sources: snapshot.sources, counties: {}, cottonProgress: snapshot.cotton_progress,
        overview: { href: "stories/#us", label: "United States stories" },
      }, true);
    }
    const latest = loadLatest(region);
    const config = readConfig(region);
    const area: StoryArea = {
      level: "state", id: config.id, name: config.name, phrase: config.phrase ?? config.name, stateFips: config.state_fips,
    };
    const supportsCotton = config.sources?.nass?.weekly?.some(({ id }) => id === "cotton") ?? false;
    return [
      ...buildAreaStories(storyContext(area, latest, data), supportsCotton, Object.keys(config.stories ?? {})),
      ...latest.districts.flatMap(({ slug }) => districtStories(config, latest, data, loadDistrict(slug, region))),
    ];
  });
}
