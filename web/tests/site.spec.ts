import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { loadDistrict, loadLatest } from "../src/lib/data";

// Must match astro.config.mjs (and its SITE_URL / SITE_BASE overrides).
const ORIGIN = `${process.env.SITE_URL || "https://thatorjohn.github.io"}${process.env.SITE_BASE || "/ag-dashboard/"}`;
const NASS = "This product uses the NASS API but is not endorsed or certified by NASS.";
const DISTRICTS = loadLatest().districts.map((d) => `district/${d.slug}/`);
const PAGES = ["", ...DISTRICTS, "about/", "for/corn-sorghum/", "for/cotton/", "for/wheat/", "for/cattle-hay/", "for/land-water/"];

for (const p of PAGES) {
  test.describe(`/${p}`, () => {
    test("shows the NASS notice verbatim and the canonical URL", async ({ page }) => {
      await page.goto(p);
      await expect(page.getByRole("contentinfo")).toContainText(NASS);
      const canonical = await page.locator('link[rel="canonical"]').getAttribute("href");
      expect(canonical).toBe(`${ORIGIN}${p}`);
    });

    for (const theme of ["light", "dark"] as const) {
      test(`passes axe in ${theme}`, async ({ page }) => {
        await page.addInitScript((t) => localStorage.setItem("theme", t), theme);
        await page.goto(p);
        await expect(page.locator("html")).toHaveClass(theme === "dark" ? /dark/ : /^(?!.*dark).*$/);
        const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
        // Map county names and district labels are ink with a 3px paper halo (paint-order: stroke), so the
        // glyphs sit on paper, the same AA pair as body text. Axe measures SVG text against the county fill and
        // can't see the halo, so contrast on .county-name and .map-label only is excluded (docs/decisions/0005).
        const violations = r.violations
          .map((v) => ({ ...v, nodes: v.id === "color-contrast" ? v.nodes.filter((n) => !/county-name|map-label/.test(String(n.html))) : v.nodes }))
          .filter((v) => v.nodes.length);
        expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`)).toEqual([]);
      });
    }

    test("has no horizontal scroll", async ({ page }) => {
      await page.goto(p);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(0);
    });
  });
}

test("the Texas screwworm card warns and expires on an open page", async ({ page }) => {
  const { screwworm } = loadLatest().texas;
  test.skip(!screwworm, "No screwworm snapshot was available at build time");
  if (!screwworm) return;
  const staleAt = Date.parse(screwworm.stale_at);
  const hideAt = Date.parse(screwworm.hide_at);
  await page.clock.install({ time: staleAt - 60_000 });
  await page.goto("");
  const card = page.getByRole("region", { name: "New World screwworm in Texas" });
  const warning = card.getByText("Stale data.");
  await expect(card).toBeVisible();
  await expect(warning).toBeHidden();
  await expect(card.getByRole("link", { name: "Texas movement restriction map" })).toBeVisible();
  await expect(card.getByRole("link", { name: "USDA weekly map of planned sterile fly releases" })).toBeVisible();

  await page.clock.fastForward(60_000);
  await expect(warning).toBeVisible();
  await page.clock.fastForward(hideAt - staleAt);
  await expect(card).toBeHidden();
  await page.reload();
  await expect(card).toBeHidden();
});

test("Texas map links a featured-district county to its card", async ({ page }) => {
  await page.goto("");
  const link = page.locator('svg.map a[href*="district/blacklands/#c-48491"]');
  await expect(link).toHaveCount(1);
  await link.click();
  await expect(page).toHaveURL(/district\/blacklands\/#c-48491$/);
  await expect(page.locator("#c-48491")).toContainText("Williamson");
  await expect(page.locator("#c-48491")).toHaveAttribute("open", "");   // the map click opens the card
  await expect(page.locator("#c-48491")).toContainText("Rain, 7 days to");
});

test("the county map and conditions share the first desktop view", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "The mobile layout stacks the conditions and map");
  await page.setViewportSize({ width: 1366, height: 768 });
  for (const path of ["", "district/south-central/"]) {
    await page.goto(path);
    await page.evaluate(() => document.fonts.ready);
    const overview = page.locator(".overview");
    const map = overview.getByRole("region", { name: /County (drought )?map/ });
    const heading = overview.getByRole("heading", { level: 1 });
    await expect(map).toBeVisible();
    const mapBox = (await map.boundingBox())!;
    const titleBox = (await heading.boundingBox())!;
    expect(mapBox.x).toBeGreaterThan(titleBox.x);
    expect(mapBox.y + mapBox.height).toBeLessThanOrEqual(768);
    const drought = path ? loadDistrict("south-central").summary.drought : loadLatest().texas.drought;
    if (drought && !loadLatest().sources.usdm.stale) {
      await overview.getByRole("link", { name: /^Drought/ }).click();
      await expect(page).toHaveURL(/#drought-h$/);
    }
  }
});

test("the homepage links to one alphabetical comparison of every district", async ({ page }) => {
  await page.goto("");
  await page.getByRole("link", { name: "Compare Texas districts" }).click();
  await expect(page).toHaveURL(/#districts-h$/);
  const comparison = page.getByRole("region", { name: /District comparison/ });
  const districts = loadLatest().districts.map((d) => d.name).sort((a, b) => a.localeCompare(b, "en"));
  await expect(comparison.getByRole("link")).toHaveText(districts);
  await comparison.getByRole("link", { name: "Trans-Pecos" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Trans-Pecos");
});

test("every district has a page, and the Texas map links counties outside the featured districts", async ({ page }) => {
  expect(DISTRICTS).toHaveLength(15);
  await page.goto("");
  // Lubbock County, Southern High Plains: not a featured district.
  const link = page.locator('svg.map a[href*="district/southern-high-plains/#c-48303"]');
  await expect(link).toHaveCount(1);
  await link.click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Southern High Plains");
  await expect(page.locator(".eyebrow").first()).not.toContainText("featured district");
  await expect(page.locator("#c-48303")).toHaveAttribute("open", "");
});

test("district section links follow the sections present on each district page", async ({ page }) => {
  for (const path of DISTRICTS) {
    await page.goto(path);
    const nav = page.getByRole("navigation", { name: "On this page" });
    const sections = await page.locator("main > section[aria-labelledby] > h2").evaluateAll(
      (headings) => headings.map((heading) => `#${heading.id}`),
    );
    const links = await nav.getByRole("link").evaluateAll((items) => items.map((item) => item.getAttribute("href")));
    expect(links, path).toEqual(sections);
  }
  await page.getByRole("navigation", { name: "On this page" }).getByRole("link", { name: /^Counties/ }).click();
  await expect(page).toHaveURL(/#co-h$/);
  await expect(page.getByRole("heading", { name: "Counties", exact: true })).toBeInViewport();
});

test("on wide screens the header lists featured districts and a menu of the rest", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("");
  await expect(page.locator(".nav .nav-district")).toHaveCount(5);
  await page.locator(".nav-menu summary").click();
  const menu = page.locator(".nav-menu-list");
  await expect(menu.getByRole("link", { name: "Blacklands" })).toBeHidden();
  await menu.getByRole("link", { name: "Northern High Plains" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Northern High Plains");
});

test("theme toggle switches and remembers", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("");
  await page.getByRole("button", { name: "Switch color theme" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
});

test("ships a 404 page at the site root for GitHub Pages", async ({ page }) => {
  await page.goto("404/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("That page isn't here");
  await expect(page.getByRole("contentinfo")).toContainText(NASS);
});

test("district map click opens the county card", async ({ page }) => {
  await page.goto("district/blacklands/");
  await page.locator('svg.map a[href="#c-48331"]').click();
  await expect(page.locator("#c-48331")).toHaveAttribute("open", "");
});

test("persona pages follow card_order", async ({ page }) => {
  await page.goto("for/cattle-hay/");
  const h2 = await page.locator("main h2").allTextContents();
  expect(h2.slice(0, 4)).toEqual(["Cattle markets", "Edwards Plateau sheep and goats", "Pasture", "Drought"]);
  await page.goto("");
  await page.getByRole("navigation", { name: "Views by what you raise" }).getByRole("link", { name: "Cattle & Hay" }).click();
  await expect(page).toHaveURL(/for\/cattle-hay\/$/);
});

test("the weekly San Angelo sheep and goat market appears on Cattle & Hay and Edwards Plateau", async ({ page }) => {
  const market = loadLatest().markets.find((m) => m.slug === 2014)!;
  await page.goto("for/cattle-hay/");
  const section = page.getByRole("region", { name: "Edwards Plateau sheep and goats" });
  await expect(section.getByRole("link", { name: "USDA AMS Market News" })).toHaveAttribute("href", /viewReport\/2014$/);
  if (market.stale) {
    await expect(section.getByText(/No recent report/)).toBeVisible();
    await expect(section.getByRole("table")).toHaveCount(0);
  } else if (market.series?.length) {
    await expect(section.getByRole("columnheader", { name: "$/cwt" })).toBeVisible();
    await expect(section.getByRole("rowheader")).toHaveCount(market.series.length);
  }
  await page.goto("district/edwards-plateau/");
  await expect(page.getByRole("region", { name: "Sheep and goat market" })).toBeVisible();
  await page.goto("for/wheat/");
  await expect(page.getByRole("heading", { name: /Sheep and Goat Auction/ })).toHaveCount(0);
});

test("every page has a 1200x630 share image", async ({ page, request }) => {
  for (const p of PAGES) {
    await page.goto(p);
    const url = await page.locator('meta[property="og:image"]').getAttribute("content");
    expect(url!.startsWith(`${ORIGIN}og/`)).toBe(true);
    expect(url).toMatch(/\/og\/[\w-]+\.png\?v=\d+$/);
    const local = url!.slice(ORIGIN.length).replace(/\?.*$/, "");
    const res = await request.get(local);
    expect(res.status(), local).toBe(200);
    const png = await res.body();
    expect([png.readUInt32BE(16), png.readUInt32BE(20)]).toEqual([1200, 630]);
  }
});

test("on narrow screens the districts fold into a menu that works", async ({ page }) => {
  await page.setViewportSize({ width: 412, height: 800 });
  await page.goto("");
  await expect(page.locator(".nav .nav-district").first()).toBeHidden();
  await page.locator(".nav-menu summary").click();
  await page.locator(".nav-menu-list").getByRole("link", { name: "East Texas South" }).click();
  await expect(page).toHaveURL(/district\/east-texas-south\/$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("East Texas South");
});

test("district weather strip shows past days and a labeled forecast, with a table of every day", async ({ page }, testInfo) => {
  await page.goto("district/blacklands/");
  await page.getByRole("link", { name: "Temperature and rain" }).click();
  await expect(page).toHaveURL(/#wx-h$/);
  const fig = page.locator("figure.wx");
  const plot = fig.getByRole("img");
  await expect(plot).toHaveAttribute("aria-label", /Daily high and low temperature and rain in Blacklands\. The \d+ days through [A-Z][a-z.]+ \d+: highs/);
  const key = fig.getByRole("list", { name: "Chart key" });
  await expect(key.getByText(/^Forecast · [A-Z]/)).toBeVisible();
  await expect(key.getByText(/^Not yet reported · [A-Z]/)).toBeVisible();
  await expect(plot.locator("text").filter({ hasText: /Pending|Forecast/ })).toHaveCount(0);
  await expect(fig).toContainText("nClimGrid-Daily");
  await expect(fig).toContainText("National Weather Service");
  await expect(fig).toContainText("Not yet reported");
  const weather = loadDistrict("blacklands").weather;
  const normalDays = weather?.days.filter((day) => day.normal_hi_f != null && day.normal_lo_f != null) ?? [];
  const normalBandCount = normalDays.length > 1 ? 1 : 0;
  await expect(fig.locator(".wx-normal")).toHaveCount(normalBandCount);
  await expect(fig.getByText("Normal high to low, 1991–2020", { exact: true })).toHaveCount(normalBandCount);
  const rows = fig.locator("tbody tr");
  expect(await rows.count()).toBeGreaterThan(30);
  await fig.getByText("Daily weather values").click();
  await expect(rows.filter({ hasText: "(forecast)" }).first()).toBeVisible();
  // The days since NOAA's newest: each one is a rain estimate or not yet reported, and estimates say so.
  await expect(rows.filter({ hasText: /\((not yet reported|rain estimate)\)/ }).first()).toBeVisible();
  if (await rows.filter({ hasText: "(rain estimate)" }).count()) {
    await expect(key.getByText("Rain estimate", { exact: true })).toBeVisible();
    await expect(fig).toContainText("Stage IV");
    await expect(rows.filter({ hasText: "(rain estimate)" }).first()).toContainText("(est.)");
  }
  // Read the date using the project's input method.
  const observed = plot.locator('.wx-hit[data-k="observed"]').nth(10);
  if (testInfo.project.name === "phone") {
    await observed.tap();
  } else {
    await observed.hover();
  }
  const tip = fig.locator(".wx-tip");
  await expect(tip).toBeVisible();
  await expect(tip).toContainText("high");
  await page.keyboard.press("Escape");
  await expect(tip).toBeHidden();
});

test("About says the site is free, built from public data, and a personal project", async ({ page }) => {
  await page.goto("about/");
  await expect(page.getByRole("heading", { name: "Free, from public data" })).toBeVisible();
  await expect(page.locator("main")).toContainText("no ads, no sign-up, no subscriptions");
  await expect(page.locator("main")).toContainText("NOAA NCEI nClimGrid-Daily");
  await expect(page.locator("main")).toContainText("a personal project by");
});

test("no page mentions Open-Meteo", async ({ page }) => {
  for (const p of ["", "district/blacklands/", "about/", "for/cattle-hay/"]) {
    await page.goto(p);
    await expect(page.locator("body")).not.toContainText(/open-meteo/i);
  }
});

test("district rain since Jan. 1 shows the chart and month table when the data is available", async ({ page }) => {
  await page.goto("district/blacklands/");
  const fig = page.locator("figure.sr");
  const { season_rain } = loadDistrict("blacklands");
  if (loadLatest().sources.nclimgrid.stale || !season_rain) {
    await expect(fig).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Rain since Jan. 1" })).toHaveCount(0);
    return;
  }
  await expect(fig.getByRole("img")).toHaveAttribute("aria-label", /Rain since Jan\. 1 in Blacklands, in inches\. Since Jan\. 1, the district has had about [\d.]+ in of rain through/);
  await expect(fig).toContainText("Typical range (middle 80% of years)");
  await fig.getByText("Month by month").click();
  await expect(fig.locator("tbody tr")).toHaveCount(12);
  await fig.locator("svg").scrollIntoViewIfNeeded();
  const box = (await fig.locator("svg").boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.5);
  await expect(fig.locator(".sr-tip")).toContainText("normal");
});

test("district land cover lists classes, labels them satellite-classified, and compares crops only", async ({ page }) => {
  await page.goto("district/blacklands/");
  const card = page.locator(".mix-card");
  await expect(card.getByRole("heading")).toHaveText(/What covers the land, \d{4}/);
  await expect(card).toContainText("satellite-classified");
  await expect(card.locator("tbody tr").first()).toContainText("%");
  // The "Since" column appears only once every county has an earlier year (the backfill fills in over runs).
  if (await card.getByRole("columnheader", { name: /^Since \d{4}$/ }).count()) {
    await expect(card.getByRole("row", { name: /Grassland and pasture/ })).toContainText("not compared");
    await expect(card.getByRole("row", { name: /^Corn/ })).toContainText(/[+−]?[\d,]+ ac/);
  }
});

test("county cards show their satellite figures when available", async ({ page }) => {
  const { counties } = loadDistrict("blacklands");
  const cropCounty = counties.find((c) => c.annual?.crop_mix?.since)
    ?? counties.find((c) => c.annual?.crop_mix);
  if (cropCounty) {
    const mix = cropCounty.annual!.crop_mix!;
    await page.goto(`district/blacklands/#c-${cropCounty.fips}`);
    const card = page.locator(`#c-${cropCounty.fips}`);
    const table = card.getByRole("table", { name: "Crop mix" });
    await expect(table.getByRole("columnheader", { name: `${mix.year} acres` })).toBeVisible();
    if (mix.since) {
      await expect(table.getByRole("columnheader", { name: `${mix.since} acres` })).toBeVisible();
    }
    await expect(table.locator("tbody tr")).toHaveCount(mix.classes.length);
    await expect(card.getByRole("link", { name: /Cropland Data Layer/ })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  }

  const rangeCounty = counties.find((c) => c.annual?.rangeland?.cover?.now.ltr != null);
  if (rangeCounty) {
    await page.goto(`district/blacklands/#c-${rangeCounty.fips}`);
    const card = page.locator(`#c-${rangeCounty.fips}`);
    const table = card.getByRole("table", { name: "Rangeland cover" });
    await expect(table.getByRole("rowheader", { name: "Litter" })).toBeVisible();
    await expect(card.getByRole("link", { name: "Rangeland Analysis Platform, USDA ARS" })).toBeVisible();
  }
});
