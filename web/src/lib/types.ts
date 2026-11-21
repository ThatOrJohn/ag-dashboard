// Mirrors kad/build.py output. Keep in step with it.
export type DroughtLevels = { d0: number; d1: number; d2: number; d3: number; d4: number };

export interface Source {
  name: string;
  url: string | null;
  license: string | null;
  as_of: string | null;
  fetched_at: string | null;
  stale: boolean;
  between_reports?: boolean;   // in the source's quiet months (NASS winter break)
}

export interface DroughtSummary {
  map_date: string;
  basis: "official" | "county_area_weighted";
  now: DroughtLevels;
  week_ago: DroughtLevels | null;
  year_ago: DroughtLevels | null;
}

export type SeasonStatus = "fresh" | "out_of_season" | "stale";

export interface ProgressCard {
  status: SeasonStatus;
  last_report: string | null;
  level: "state";
  week_ending?: string;
  stages?: { stage: string; pct: number; last_week: number | null; last_year: number | null; avg_5yr: number | null }[];
}

export interface ConditionCard {
  status: SeasonStatus;
  last_report: string | null;
  level: "state";
  week_ending?: string;
  classes?: Record<"excellent" | "good" | "fair" | "poor" | "very_poor", number | null>;
  good_excellent?: number | null;
  last_week?: number | null;
  last_year?: number | null;
}

export interface MarketCard {
  slug: number;
  name: string;
  scope: string;
  district: string | null;
  url: string;
  report_date: string | null;
  stale: boolean;
  series?: { id: string; price_cwt: number | null; head: number | null; prev: number | null; year_ago: number | null }[];
  receipts?: number | null;
  narrative?: string | null;
}

export interface CountyCard {
  name: string;
  district: string;
  drought?: DroughtLevels;
  drought_year_ago?: DroughtLevels;
  burn_ban?: boolean;
  through?: string;
  last_7d_in?: number;
  last_30d_in?: number;
  next_7d_in?: number;
  rain_vs_normal?: RainVsNormal;
  rain_estimate?: RainEstimate;
}

// Stage IV radar-and-gauge rain for the days after NOAA's newest county-average day (decision 0017).
export interface RainEstimate { from: string; through: string; in: number; counties?: number }

// NOAA nClimGrid county-average rain over the 30 days through its newest day, vs the 1991–2020 normal for those
// dates (decision 0013). NOAA runs about a week behind, so it carries its own date.
export interface RainVsNormal { through: string; days: number; in: number; normal_in: number; pct: number | null; counties?: number }

export interface Headline {
  sentences: string[];
  sources: SourceKey[];
  items?: { source: SourceKey; topic: string; text: string }[];   // topic: drought, rain, burn_bans, cattle, crop:<id>
}

export interface DistrictSummary {
  slug: string;
  name: string;
  home: boolean;
  counties: number;
  crops: ("wheat" | "cotton" | "corn" | "sorghum")[];   // statewide crop cards this district's page shows
  drought?: DroughtSummary | null;
  burn_bans?: number;
  rain_7d_in?: number | null;
  rain_30d_in?: number | null;
  rain_next_7d_in?: number | null;
  rain_through?: string | null;     // NOAA's newest day for rain_7d_in / rain_30d_in
  rain_vs_normal?: RainVsNormal | null;
  rain_estimate?: RainEstimate | null;
  headline?: Headline;
}

export interface Persona { id: string; name: string; blurb?: string; card_order: string[] }

export type SourceKey = "usdm" | "nass" | "ams" | "burn_bans" | "nws" | "census" | "nass_county" | "rap" | "cdl" | "nclimgrid" | "normals" | "stage4";

// Annual figures (kad/annual_build.py). Missing means "not published", never zero.
export type CoverKey = "pfg" | "afg" | "shr" | "tre" | "ltr" | "bgr";
export interface CensusCard {
  year: number; farms?: number; land_in_farms_acres?: number; avg_farm_acres?: number; median_farm_acres?: number;
  cropland_acres?: number; pasture_acres?: number; sales_usd?: number; land_value_usd_ac?: number; producers?: number;
  cattle?: number; goats?: number; sheep?: number; farms_prev?: number; prev_year?: number;
}
export interface CropEstimate { year: number; planted_acres: number; yield: number | null; yield_unit: string }
export interface CountyAnnual {
  census?: CensusCard;
  estimates?: Partial<Record<"corn" | "sorghum" | "cotton" | "wheat", CropEstimate>> & { cattle?: { year: number; head: number; beef_cows: number | null } };
  rangeland?: {
    cover?: { year: number; now: Record<CoverKey, number | null>; baseline: Record<CoverKey, number | null>; baseline_years: [number, number] };
    production?: { through: string; ytd_lb_ac: number; normal_lb_ac: number | null; pct_of_normal: number | null };
  };
  crop_mix?: { year: number; classes: { id: string; acres: number; pct: number }[] };
}
export interface DistrictAnnual {
  counties: number;
  census?: { year: number; farms: number; land_in_farms_acres: number; sales_usd: number; cattle: number; counties: number; farms_prev: number | null; prev_year: number };
  crops_published?: Partial<Record<"corn" | "sorghum" | "cotton" | "wheat", { year: number; planted_acres: number; published_counties: number }>>;
  forage_pct_of_normal?: { pct: number; through: string; counties: number };
  // Cropland Data Layer, our sum of county acres (decision 0016). `since` is null when only one year is in.
  crop_mix?: { year: number; since: number | null; land_acres: number; counties: number;
    classes: { id: string; acres: number; pct: number; crop?: boolean; acres_then?: number; change_acres?: number; change_pts?: number }[] };
}

export interface Latest {
  generated_at: string;
  asof: string;
  region: { id: string; name: string };
  nass_notice: string;
  sources: Record<SourceKey, Source>;
  failures: string[];
  personas: Persona[];
  texas: {
    drought: DroughtSummary | null;
    burn_bans: { count: number; of: number } | null;
    crops: Record<"corn" | "sorghum" | "cotton" | "wheat", { progress: ProgressCard; condition: ConditionCard }>;
    pasture: ConditionCard;
    headline?: Headline;
    headline_all?: Headline;
  };
  districts: DistrictSummary[];
  markets: MarketCard[];
  counties: Record<string, CountyCard>;
}

// Our area-weighted average of NOAA nClimGrid county values (observed) and NWS county-center forecasts
// (kad/build.py weather_strip, decision 0014). Pending days: NOAA hasn't published them yet; no values.
export interface WeatherStrip {
  through: string;
  basis: "county_average_area_weighted";
  days: { date: string; kind: "observed" | "estimated" | "pending" | "forecast"; hi_f: number | null; lo_f: number | null; rain_in: number | null;
    normal_hi_f?: number | null; normal_lo_f?: number | null }[];   // normals: NOAA nClimGrid 1991–2020
}

// Rain since Jan. 1 vs 1991–2020 (kad/build.py season_rain, decision 0015). Arrays are inches, one per day
// from Jan. 1: `actual` through NOAA's newest day, the rest for the whole year.
export interface SeasonRain {
  year: number; through: string; start: string;
  actual: number[]; normal: number[]; low: number[]; high: number[];
  to_date_in: number; normal_to_date_in: number; pct: number | null; normal_year_in: number;
  drier_years: number; years: number; range_years: [number, number];
}

export interface DistrictFile {
  slug: string;
  name: string;
  asof: string;
  summary: DistrictSummary;
  drought_history: ({ date: string } & Partial<DroughtLevels>)[];
  weather?: WeatherStrip | null;
  season_rain?: SeasonRain | null;
  counties: ({ fips: string; annual?: CountyAnnual } & CountyCard)[];
  markets: MarketCard[];
  annual?: DistrictAnnual;
}
