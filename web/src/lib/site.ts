// Site name and mark, shared by the masthead (Base.astro) and the share images (og.ts).
export const SITE_NAME = "Texas Ag Dashboard";

/** The mark: crop rows running to the horizon under a sun. public/icon.svg is the same drawing. */
export function markSvg(bg: string, fg: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><rect width="80" height="80" rx="8" fill="${bg}"/>` +
    `<g fill="none" stroke="${fg}" stroke-width="4" stroke-linecap="round"><path d="M12 36 H68"/>` +
    `<path d="M40 36 L10 70 M40 36 L25 70 M40 36 V70 M40 36 L55 70 M40 36 L70 70"/></g>` +
    `<circle cx="57" cy="22" r="6" fill="${fg}"/></svg>`;
}

export const AUTHOR = "John Walley";
export const REPO_URL = "https://github.com/ThatOrJohn/ag-dashboard";
