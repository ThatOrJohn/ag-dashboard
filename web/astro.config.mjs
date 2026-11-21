// @ts-check
import { defineConfig } from "astro/config";
import react from "@astrojs/react";

// Published to GitHub Pages as a project site, so it builds under the repo's path. SITE_URL / SITE_BASE
// override both (e.g. for a custom domain, set SITE_BASE=/).
export default defineConfig({
  site: process.env.SITE_URL || "https://thatorjohn.github.io",
  base: process.env.SITE_BASE || "/ag-dashboard/",
  trailingSlash: "always",
  integrations: [react()],
  build: { format: "directory" },
  // Keep the classic whitespace collapsing so wrapped text in templates stays readable (ms-sound-check).
  compressHTML: true,
});
