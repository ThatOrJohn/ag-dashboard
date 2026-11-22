import { expect, test } from "@playwright/test";
import { loadDistrict, loadLatest, REGION } from "../src/lib/data";
import { buildStories, chapterHoldMs, profileTourSlug, weeklyTourSlug } from "../src/lib/stories";
import { stateFlyover } from "../src/lib/stories/flyover";

const stories = buildStories();
const weekly = stories.find(({ area, slug }) => area.level === "state" && area.id === REGION && slug === weeklyTourSlug)!;
const districts = stories.filter(({ area, story, slug }) =>
  area.level === "district" && area.stateId === REGION && slug === profileTourSlug && story != null);
const profile = districts.find(({ featured }) => !featured);

test("a weekly tour drops stale sources and reports the cotton winter break", () => {
  const latest = loadLatest();
  const files = latest.districts.map(({ slug }) => loadDistrict(slug));
  const context = {
    ...weekly.context, asof: latest.asof, data: { drought: null, cotton: null },
    overview: weekly.fallback.related,
    cottonProgress: { status: "out_of_season", level: "state", last_report: "2025-11-17" } as const,
  };
  const source = { name: "Fixture", url: null, license: null, as_of: "2026-11-17", fetched_at: null, stale: false };
  const drought = {
    map_date: "2026-11-17", basis: "county_area_weighted" as const,
    now: { d0: 100, d1: 60, d2: 20, d3: 0, d4: 0 }, week_ago: null, year_ago: null,
  };
  const fixture = { ...latest, texas: { ...latest.texas, drought, rain_vs_normal: null } };
  const inputs = files.slice(0, 2).map((district) => ({
    ...district, summary: { ...district.summary, drought }, drought_history: [], water: [],
  }));
  const fresh = { ...context, sources: { usdm: source, nass: source } };
  const tour = stateFlyover(fresh, fixture, inputs);
  expect(tour?.visual.kind).toBe("flyover");
  if (tour?.visual.kind !== "flyover") return;
  expect(tour.visual.stops).toHaveLength(4);
  expect(tour.visual.stops[0].tiles).toContainEqual(expect.objectContaining({
    label: "Statewide cotton harvest", value: "Out of season", date: latest.asof,
  }));
  expect(stateFlyover({
    ...fresh, sources: { nass: source, usdm: { ...source, stale: true } },
  }, fixture, inputs)).toBeNull();
  expect(stateFlyover(fresh, fixture, inputs.slice(0, 1))).toBeNull();
});

test("the weekly flyover holds and zooms between chapters and returns to the overview", async ({ page }) => {
  test.skip(weekly.story?.visual.kind !== "flyover", "The snapshot has too few weekly figures");
  await page.clock.install();
  await page.goto(`stories/${weekly.path}/`);
  const map = page.getByRole("img", { name: `Map of ${weekly.area.name}` });
  const route = page.getByRole("group", { name: "Flyover route" });
  const buttons = route.getByRole("button");
  const whole = await map.getAttribute("viewBox");
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(buttons.first()).toHaveAttribute("aria-pressed", "true");
  await page.clock.runFor(chapterHoldMs + 700);
  await expect(buttons.nth(1)).toHaveAttribute("aria-pressed", "true");
  await expect(map).not.toHaveAttribute("viewBox", whole!);
  await expect(map.locator("path.selected").first()).toBeAttached();
  await buttons.last().click();
  await page.clock.runFor(700);
  await expect(map).toHaveAttribute("viewBox", whole!);
  await expect(page.getByRole("button", { name: "Replay", exact: true })).toBeVisible();
});

test("reduced motion cuts directly to the target viewBox", async ({ page }) => {
  test.skip(!weekly.story, "The snapshot has too few weekly figures");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`stories/${weekly.path}/`);
  const map = page.locator("[data-flyover-map]");
  const boxes: number[][] = JSON.parse((await map.getAttribute("data-boxes"))!);
  await page.getByRole("group", { name: "Flyover route" }).getByRole("button").nth(1).click();
  expect(await map.getAttribute("viewBox")).toBe(boxes[1].join(" "));
  await expect(page.locator("[data-flyover-card]:visible time").first()).toBeVisible();
});

test("the district picker and dashboard link to profiles that read without JavaScript", async ({ browser }) => {
  test.skip(!profile || profile.story?.visual.kind !== "flyover", "The snapshot has no non-featured district profile");
  const context = await browser.newContext({ javaScriptEnabled: false });
  try {
    const page = await context.newPage();
    await page.goto("stories/");
    await page.getByRole("group", { name: /district tours map/ })
      .getByRole("link", { name: `Take the ${profile!.area.name} tour`, exact: true }).click();
    const visual = profile!.story!.visual;
    if (visual.kind !== "flyover") throw new Error("Expected a district profile");
    await expect(page.locator("[data-flyover-card]:visible")).toHaveCount(visual.stops.length);
    await expect(page.getByRole("group", { name: "Flyover route" })).toHaveCount(0);
    await page.getByText("See all figures", { exact: true }).click();
    await expect(page.getByRole("table").getByRole("row")).toHaveCount(
      1 + visual.stops.reduce((sum, stop) => sum + stop.tiles.length, 0));
    await page.goto(`district/${profile!.area.id}/`);
    await expect(page.getByRole("link", { name: "Take the tour", exact: true })).toHaveAttribute("href",
      new RegExp(`/stories/${profile!.path}/$`));
  } finally {
    await context.close();
  }
});
