import type { DroughtLevels } from "./types";

/** Link inside the site, respecting the base path (astro.config.mjs). */
export function href(p = ""): string {
  const base = import.meta.env.BASE_URL.endsWith("/") ? import.meta.env.BASE_URL : `${import.meta.env.BASE_URL}/`;
  return base + p.replace(/^\//, "");
}

const MONTHS = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."];

/** "2026-11-17" → "Nov. 17" (AP style), with the year when it isn't `ref`'s year. */
export function day(iso: string | null | undefined, ref?: string): string {
  if (!iso) return "unknown date";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  const s = `${MONTHS[m - 1]} ${d}`;
  return ref && ref.slice(0, 4) === String(y) ? s : `${s}, ${y}`;
}

/** Newest source pull, in Texas time, AP style: "7:17 a.m. CT", with "Nov. 20, " first when the
 *  Central date isn't `ref`'s date. */
export function pulled(iso: string, ref?: string): string {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Chicago", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "numeric", minute: "2-digit", hour12: true, timeZoneName: "short",
  }).formatToParts(new Date(iso)).map((p) => [p.type, p.value]));
  const date = `${parts.year}-${parts.month}-${parts.day}`;
  const time = `${parts.hour}:${parts.minute} ${parts.dayPeriod === "AM" ? "a.m." : "p.m."} ${parts.timeZoneName?.startsWith("CD") ? "CDT" : "CST"}`;
  return ref && ref.slice(0, 10) === date ? time : `${day(date, ref)}, ${time}`;
}

/** Whole percent; a share above 0 but under 0.5 reads "<1%" rather than rounding to a misleading "0%". */
export const pct = (v: number | null | undefined) => (v == null ? "n/a" : v > 0 && v < 0.5 ? "<1%" : `${Math.round(v)}%`);
export const inches = (v: number | null | undefined) => (v == null ? "n/a" : `${v.toFixed(2)} in`);
export const usd = (v: number | null | undefined) => (v == null ? "n/a" : `$${v.toFixed(2)}`);

/** Signed change in points, in words: "up 3 pts", "down 1 pt", "unchanged". */
export function change(now: number | null | undefined, then: number | null | undefined, unit = "pt"): string {
  if (now == null || then == null) return "";
  const d = Math.round(now - then);
  if (d === 0) return "unchanged";
  const n = Math.abs(d);
  return `${d > 0 ? "up" : "down"} ${n} ${unit}${n === 1 ? "" : "s"}`;
}

export function moneyChange(now: number | null | undefined, then: number | null | undefined): string {
  if (now == null || then == null) return "";
  const d = now - then;
  if (Math.abs(d) < 0.005) return "unchanged";
  return `${d > 0 ? "up" : "down"} $${Math.abs(d).toFixed(2)}`;
}

export const STAGES: Record<string, string> = {
  planted: "Planted", emerged: "Emerged", silking: "Silking", dough: "Dough", dented: "Dented", mature: "Mature",
  harvested: "Harvested", headed: "Headed", coloring: "Coloring", squaring: "Squaring",
  setting_bolls: "Setting bolls", bolls_opening: "Bolls opening", milk: "Milk",
};

export const CROPS: Record<string, string> = { corn: "Corn", sorghum: "Sorghum", cotton: "Cotton", wheat: "Winter wheat" };

export const SERIES: Record<string, string> = {
  "steers:500": "Feeder steers, 500–599 lb", "steers:700": "Feeder steers, 700–799 lb",
  "heifers:500": "Feeder heifers, 500–599 lb", "cows:slaughter": "Slaughter cows",
};

export const DROUGHT_NAMES = ["Abnormally dry", "Moderate drought", "Severe drought", "Extreme drought", "Exceptional drought"];
const KEYS = ["d0", "d1", "d2", "d3", "d4"] as const;

/** Most severe category covering at least half the area: -1 none, 0 = D0 … 4 = D4. Inputs are cumulative. */
export function category(l: DroughtLevels | undefined | null): number {
  if (!l) return -1;
  let c = -1;
  KEYS.forEach((k, i) => { if (l[k] >= 50) c = i; });
  return c;
}

export function categoryName(c: number): string {
  return c < 0 ? "No drought" : `D${c}, ${DROUGHT_NAMES[c].toLowerCase()}`;
}

/** Cumulative (D1 = "D1 or worse") → bands that add to 100, for a stacked bar. */
export function bands(l: DroughtLevels): { key: string; label: string; value: number }[] {
  const out = [{ key: "none", label: "None", value: 100 - l.d0 }];
  KEYS.forEach((k, i) => out.push({ key: k, label: `D${i}`, value: l[k] - (i < 4 ? l[KEYS[i + 1]] : 0) }));
  return out.map((b) => ({ ...b, value: Math.max(0, Math.round(b.value * 10) / 10) }));
}

/** 1-9 as words, for prose ("these five districts"). */
export const countWord = (n: number) => ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"][n] ?? String(n);

/** "A, B and C". */
export const listAnd = (xs: string[]) => xs.length <= 1 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`;

export const num = (v: number | null | undefined) => (v == null ? "n/a" : Math.round(v).toLocaleString("en-US"));

/** 694398000 → "$694 million"; 38189000 → "$38.2 million". */
export function usdBig(v: number | null | undefined): string {
  if (v == null) return "n/a";
  if (v >= 1e9) return `$${(v / 1e9).toFixed(v >= 1e10 ? 0 : 1)} billion`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(v >= 1e8 ? 0 : 1)} million`;
  return `$${num(v)}`;
}

export const COVER_NAMES: Record<string, string> = {
  pfg: "Perennial grasses", afg: "Annual grasses and forbs", shr: "Shrubs", tre: "Trees", ltr: "Litter", bgr: "Bare ground",
};

export const CDL_NAMES: Record<string, string> = {
  developed: "Developed (towns, roads, buildings)",
  grassland_pasture: "Grassland and pasture", shrubland: "Shrubland", deciduous_forest: "Deciduous forest",
  evergreen_forest: "Evergreen forest", mixed_forest: "Mixed forest", woody_wetlands: "Woody wetlands",
  herbaceous_wetlands: "Herbaceous wetlands", winter_wheat: "Winter wheat", other_hay_non_alfalfa: "Hay (non-alfalfa)",
  fallow_idle_cropland: "Fallow or idle cropland", dbl_crop_winwht_sorghum: "Double crop: wheat then sorghum",
};

/** CDL class id → readable name: known names, else the id with spaces. */
export const cdlName = (id: string) => CDL_NAMES[id] ?? id.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
