// Build-time data access: pages read the pipeline's JSON so every page is pre-rendered with current numbers.
import fs from "node:fs";
import path from "node:path";
import type { DistrictFile, Latest } from "./types";

export const REGION = process.env.REGION || "tx";
const dataDir = path.join(process.cwd(), "public", "data", REGION);

export function loadLatest(): Latest {
  return JSON.parse(fs.readFileSync(path.join(dataDir, "latest.json"), "utf8"));
}

export function loadDistrict(slug: string): DistrictFile {
  return JSON.parse(fs.readFileSync(path.join(dataDir, "districts", `${slug}.json`), "utf8"));
}
