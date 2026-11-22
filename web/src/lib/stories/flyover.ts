import { cdlName, day, inches, num, pct } from "../format";
import type { DistrictFile, DroughtSummary, Latest, RainVsNormal, SourceKey } from "../types";
import { chapterHoldMs, type Story, type StoryContext } from "./model";

export const weeklyTourSlug = "this-week-flyover";
export const profileTourSlug = "district-profile";

export type FlyoverIcon = "cotton" | "cattle" | "water" | "well" | "rain";

export interface FlyoverTile {
  label: string;
  value: string;
  source: SourceKey;
  date: string;
  note?: string;
}

export interface FlyoverStop {
  name: string;
  caption: string;
  tiles: FlyoverTile[];
  /** County FIPS, or state FIPS for a national map. An empty list frames the whole map. */
  fips: string[];
  pin?: { fips: string; icon: FlyoverIcon; label: string };
}

interface Candidate {
  stop: FlyoverStop;
  scores: Partial<Record<"change" | "rain" | "drought" | "cotton" | "cattle" | "cover" | "normal" | "farms", number>>;
}

function tile(ctx: StoryContext, source: SourceKey, date: string | number | null | undefined,
              label: string, value: string, note?: string): FlyoverTile[] {
  if (ctx.sources[source]?.stale !== false || date == null) return [];
  return [{ label, value, source, date: String(date), note }];
}

function droughtTiles(ctx: StoryContext, drought: DroughtSummary | null | undefined) {
  if (!drought) return [];
  const note = drought.basis === "county_area_weighted" ? "My area-weighted county figures" : undefined;
  return [
    ...tile(ctx, "usdm", drought.map_date, "Land in drought (D1+)", pct(drought.now.d1), note),
    ...tile(ctx, "usdm", drought.map_date, "Land in severe drought (D2+)", pct(drought.now.d2), note),
  ];
}

function rainTiles(ctx: StoryContext, rain: RainVsNormal | null | undefined, note?: string) {
  if (!rain || ctx.sources.nclimgrid?.stale !== false) return [];
  return [
    ...tile(ctx, "nclimgrid", rain.through, `${rain.days}-day rain`, inches(rain.in), note),
    ...tile(ctx, "normals", ctx.sources.normals?.as_of, "Normal for those dates", inches(rain.normal_in), "1991–2020"),
  ];
}

function cottonProgress(ctx: StoryContext) {
  const report = ctx.cottonProgress;
  if (!report) return [];
  const harvest = report.stages?.find(({ stage }) => stage === "harvested");
  if (report.status === "out_of_season" && ctx.sources.nass?.stale === false) {
    return tile(ctx, "nass", ctx.asof, "Statewide cotton harvest", "Out of season");
  }
  return report.status === "fresh" && harvest
    ? tile(ctx, "nass", report.week_ending, "Statewide cotton harvested", pct(harvest.pct)) : [];
}

function countyProfile(ctx: StoryContext, county: DistrictFile["counties"][number]): Candidate {
  const { crop_mix: mix, census, rangeland } = county.annual ?? {};
  const crops = mix?.classes.filter(({ acres }) => acres > 0) ?? [];
  const cotton = crops.find(({ id }) => id === "cotton");
  const crop = cotton ?? crops[0];
  const cropTiles = crop ? tile(ctx, "cdl", mix?.year, `${cdlName(crop.id)} share of land`, pct(crop.pct), "Satellite-classified") : [];
  const farms = census?.farms == null ? [] : tile(ctx, "census", census.year, "Farms", num(census.farms));
  const cattle = census?.cattle == null ? [] : tile(ctx, "census", census.year, "Cattle and calves", num(census.cattle));
  const cover = rangeland?.cover?.now.pfg;
  const grass = cover == null ? [] : tile(ctx, "rap", rangeland?.cover?.year, "Perennial grass and forb cover", pct(cover), "Satellite estimate");
  const normal = normalTile(ctx, county.normal_year_in);
  const name = `${county.name} County`;
  return {
    stop: {
      name, fips: [county.fips], tiles: [...cropTiles, ...cattle, ...grass, ...normal, ...farms].slice(0, 4),
      caption: cropTiles.length && cotton ? "The Cropland Data Layer maps cotton here. Its share is measured against all county land."
        : grass.length ? "The rangeland estimate shows how much ground is covered by perennial grasses and forbs."
        : "The county figures show the size of its farming and ranching economy and the land it works.",
      pin: cropTiles.length && cotton ? { fips: county.fips, icon: "cotton", label: "Cotton" }
        : cattle.length ? { fips: county.fips, icon: "cattle", label: "Cattle and calves" }
        : normal.length ? { fips: county.fips, icon: "rain", label: "Normal rainfall" } : undefined,
    },
    scores: {
      cotton: cropTiles.length ? cotton?.pct : undefined,
      cattle: cattle.length ? census?.cattle : undefined,
      cover: grass.length ? cover ?? undefined : undefined,
      normal: normal.length ? county.normal_year_in : undefined,
      farms: farms.length ? census?.farms : undefined,
    },
  };
}

function normalTile(ctx: StoryContext, value: number | null | undefined, note = "1991–2020") {
  return value == null ? [] : tile(ctx, "normals", ctx.sources.normals?.as_of, "Normal annual rain", inches(value), note);
}

function districtProfile(ctx: StoryContext, district: DistrictFile) {
  const { census, crop_mix: mix, crops_published: estimates } = district.annual ?? {};
  const cotton = mix?.classes.find(({ id }) => id === "cotton");
  const planted = estimates?.cotton;
  const crop = cotton && ctx.sources.cdl?.stale === false
    ? tile(ctx, "cdl", mix?.year, "Cotton share of land", pct(cotton.pct), "Satellite-classified · My county total")
    : planted ? tile(ctx, "nass_county", planted.year, "Cotton acres planted", num(planted.planted_acres),
      planted.published_counties < district.counties.length ? "My county total · Lower bound" : "My county total") : [];
  // The rollup sums published figures. Some counties report farms but withhold their cattle counts.
  const censusTile = (key: "farms" | "cattle", label: string) => {
    if (!census) return [];
    const published = district.counties.filter(({ annual }) => annual?.census?.year === census.year && annual.census[key] != null).length;
    return published ? tile(ctx, "census", census.year, label, num(census[key]),
      published < district.counties.length ? "My county total · Lower bound" : "My county total") : [];
  };
  return [...crop, ...censusTile("cattle", "Cattle and calves"), ...censusTile("farms", "Farms"),
    ...normalTile(ctx, district.summary.normal_year_in ?? district.season_rain?.normal_year_in,
      "1991–2020 · My area-weighted county figures")];
}

function weeklyDistrict(ctx: StoryContext, district: DistrictFile): Candidate {
  const { summary: { drought, rain_vs_normal: rain }, counties, name, water } = district;
  const droughtStats = droughtTiles(ctx, drought);
  const rainStats = rainTiles(ctx, rain, "My area-weighted county figures");
  const well = water?.find((item) => item.kind === "groundwater" && ctx.sources[item.source]?.stale === false &&
    counties.some((c) => item.name === `${c.name} County well`));
  const wellCounty = well && counties.find((c) => well.name === `${c.name} County well`);
  const wellStats = well ? tile(ctx, well.source, well.date, well.name, `${well.value.toFixed(1)} ft`, "Depth below land surface") : [];
  const rainCounty = counties.filter((c) => c.rain_vs_normal?.pct != null)
    .sort((a, b) => b.rain_vs_normal!.pct! - a.rain_vs_normal!.pct!)[0];
  const dryCounty = counties.filter((c) => c.drought)
    .sort((a, b) => b.drought!.d1 - a.drought!.d1)[0];
  const week = drought ? Date.parse(drought.map_date) - 7 * 864e5 : NaN;
  const last = district.drought_history.filter(({ date }) => Math.abs(Date.parse(date) - week) <= 3 * 864e5).at(-1);
  const delta = drought && last?.d1 != null ? Number((drought.now.d1 - last.d1).toFixed(1)) : undefined;
  const previous = last?.d1 != null
    ? tile(ctx, "usdm", last.date, "Land in drought last week (D1+)", pct(last.d1), "My area-weighted county figures") : [];
  const currentDrought = [...droughtStats.slice(0, 1), ...(previous.length ? previous : droughtStats.slice(1))];
  return {
    stop: {
      name, fips: counties.map(({ fips }) => fips),
      tiles: (wellStats.length ? [...currentDrought, ...wellStats, ...rainStats.slice(0, 1)] : [...currentDrought, ...rainStats]).slice(0, 4),
      caption: currentDrought.length && delta != null && delta !== 0
        ? `The map shows drought ${delta > 0 ? "expanded" : "eased"} since the previous weekly map.`
        : rainStats.length === 2 && !wellStats.length ? "The rain total can be compared with the 1991–2020 normal for the same dates."
        : "The latest county figures show conditions across the district.",
      pin: wellStats.length && wellCounty && well ? { fips: wellCounty.fips, icon: "well", label: well.name }
        : rainStats.length && rainCounty ? { fips: rainCounty.fips, icon: "rain", label: `${rainCounty.name} County rainfall` }
        : currentDrought.length && dryCounty ? { fips: dryCounty.fips, icon: "water", label: `${dryCounty.name} County drought` } : undefined,
    },
    scores: {
      change: previous.length && delta != null ? Math.abs(delta) : undefined,
      drought: droughtStats.length ? drought?.now.d1 : undefined,
      rain: rainStats.length === 2 && !wellStats.length ? rain?.pct ?? undefined : undefined,
    },
  };
}

function weeklyCounty(ctx: StoryContext, county: DistrictFile["counties"][number]): Candidate {
  const date = ctx.sources.usdm?.as_of;
  const drought = county.drought && date ? tile(ctx, "usdm", date, "Land in drought (D1+)", pct(county.drought.d1)) : [];
  const severe = county.drought && date ? tile(ctx, "usdm", date, "Land in severe drought (D2+)", pct(county.drought.d2)) : [];
  const rain = rainTiles(ctx, county.rain_vs_normal);
  return {
    stop: {
      name: `${county.name} County`, fips: [county.fips], tiles: [...drought, ...rain, ...severe],
      caption: rain.length === 2 ? "Compare the county’s recent rain with what usually falls over the same dates."
        : "The drought map shows how much of the county is in moderate drought or worse.",
      pin: rain.length ? { fips: county.fips, icon: "rain", label: "Rainfall" }
        : drought.length ? { fips: county.fips, icon: "water", label: "Drought coverage" } : undefined,
    },
    scores: {
      rain: rain.length === 2 ? county.rain_vs_normal?.pct ?? undefined : undefined,
      drought: drought.length ? county.drought?.d1 : undefined,
    },
  };
}

/** Start with the leader for each available measure, then fill the route with the next ranked places. */
function route(candidates: Candidate[], keys: (keyof Candidate["scores"])[], limit: number) {
  const eligible = candidates.filter(({ stop }) => stop.fips.length && stop.tiles.length >= 2);
  const reasons: Partial<Record<keyof Candidate["scores"], string>> = {
    change: "This stop had the largest change in drought coverage since the previous map.",
    rain: "This stop had the most rain relative to its normal for the same dates.",
    cotton: "This stop has the largest mapped cotton share among the reported county figures.",
  };
  const rankings = keys.map((key) => ({
    reason: reasons[key],
    ranked: eligible.filter(({ scores }) => scores[key] != null)
      .sort((a, b) => b.scores[key]! - a.scores[key]! || a.stop.name.localeCompare(b.stop.name)),
  }));
  const ordered = new Map<Candidate, FlyoverStop>();
  const longest = Math.max(0, ...rankings.map(({ ranked }) => ranked.length));
  for (let i = 0; i < longest && ordered.size < limit; i++) {
    for (const { ranked, reason } of rankings) {
      const candidate = ranked[i];
      if (candidate && !ordered.has(candidate)) {
        const { stop } = candidate;
        ordered.set(candidate, i === 0 && ranked.length > 1 && reason ? { ...stop, caption: reason } : stop);
      }
      if (ordered.size === limit) break;
    }
  }
  for (const candidate of eligible) {
    if (ordered.size === limit) break;
    if (!ordered.has(candidate)) ordered.set(candidate, candidate.stop);
  }
  return [...ordered.values()];
}

export function flyoverInfo(ctx: StoryContext, profile: boolean) {
  return {
    title: profile ? `${ctx.area.name} district profile` : `${ctx.area.name} this week: flyover`,
    topic: "Flyover",
    description: profile ? `Visit counties in ${ctx.area.phrase} and see the land, crops and livestock that shape it.`
      : `Tour ${ctx.area.phrase} to compare drought, rainfall and other conditions from the latest reports.`,
  };
}

function makeFlyover(ctx: StoryContext, profile: boolean, tiles: FlyoverTile[], places: FlyoverStop[]): Story | null {
  if (places.length < 2 || tiles.length < 2) return null;
  const stops: FlyoverStop[] = [
    { name: ctx.area.name, caption: profile ? "Start with the district’s totals before visiting its counties."
      : "Start with the area-wide figures, then compare conditions at each stop.", tiles, fips: [] },
    ...places,
    { name: `Back to ${ctx.area.name}`, caption: profile ? "Return to the full district after seeing how its counties differ."
      : "Return to the whole area after comparing local conditions.", tiles, fips: [] },
  ];
  return {
    ...flyoverInfo(ctx, profile),
    slug: profile ? profileTourSlug : weeklyTourSlug,
    period: profile ? "District profile" : day(ctx.asof),
    metric: profile ? "District profile" : "Latest conditions",
    frameLabel: "Stop",
    series: [],
    frames: stops.map(({ name, caption }) => ({ label: name, caption, values: [] })),
    chapters: stops.map(({ name }, frame) => ({ frame, label: name })),
    takeaway: {
      title: "Flyover figures",
      text: profile ? "Figures use the publication year for each source. District figures are my totals or averages of county figures."
        : "Each stop uses the newest available figures. Rainfall and drought maps can have different dates.",
    },
    method: "Map boundaries from the U.S. Census Bureau’s cartographic boundary files.",
    visual: { kind: "flyover", stops },
    frameMs: chapterHoldMs,
    highlights: [],
    related: ctx.overview,
  };
}

export function stateFlyover(ctx: StoryContext, latest: Latest, districts: DistrictFile[]) {
  const candidates = districts.map((district) => weeklyDistrict(ctx, district));
  return makeFlyover(ctx, false, [
    ...droughtTiles(ctx, latest.texas.drought), ...cottonProgress(ctx),
    ...rainTiles(ctx, latest.texas.rain_vs_normal, "My area-weighted county figures"),
  ].slice(0, 4), route(candidates, ["change", "rain", "drought"], districts.length));
}

export function districtFlyover(ctx: StoryContext, district: DistrictFile, profile: boolean) {
  if (profile) return makeFlyover(ctx, true, districtProfile(ctx, district),
    route(district.counties.map((c) => countyProfile(ctx, c)), ["cotton", "cattle", "cover", "normal", "farms"], 5));
  const { stop } = weeklyDistrict(ctx, district);
  return makeFlyover(ctx, false, stop.tiles,
    route(district.counties.map((c) => weeklyCounty(ctx, c)), ["rain", "drought"], 5));
}
