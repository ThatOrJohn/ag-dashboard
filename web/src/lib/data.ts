// Build-time data access: pages read the pipeline's JSON so every page is pre-rendered with current numbers.
import fs from "node:fs";
import path from "node:path";
import type { DistrictFile, Latest, NationalStorySnapshot, StoryData } from "./types";

export const REGION = process.env.REGION || "tx";
export const dataRoot = path.join(process.cwd(), "public", "data");

export function loadLatest(region = REGION): Latest {
  return JSON.parse(fs.readFileSync(path.join(dataRoot, region, "latest.json"), "utf8"));
}

export function loadNationalStorySnapshot(): NationalStorySnapshot {
  return JSON.parse(fs.readFileSync(path.join(dataRoot, "us", "latest.json"), "utf8"));
}

export function loadDistrict(slug: string, region = REGION): DistrictFile {
  return JSON.parse(fs.readFileSync(path.join(dataRoot, region, "districts", `${slug}.json`), "utf8"));
}

/** History for the animated stories. Absent (an older build) reads as no story data. */
export function loadStoryData(region = REGION): StoryData {
  const file = path.join(dataRoot, region, "stories.json");
  if (!fs.existsSync(file)) return { drought: null, cotton: null };
  return JSON.parse(fs.readFileSync(file, "utf8"));
}
