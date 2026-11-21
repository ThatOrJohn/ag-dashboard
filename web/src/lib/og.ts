// Share images (Open Graph, 1200x630) drawn at build time, as in ms-sound-check (its decision 0026): satori
// lays the card out as SVG with the text as paths, sharp rasterizes it, so no fonts are needed on the build
// machine. Text is the page title plus the drought sentence only (Drought Monitor data), so no NASS figures
// appear on an image that can travel without the site's footer.
import fs from "node:fs";
import path from "node:path";
import satori from "satori";
import sharp from "sharp";
import { SITE_NAME, markSvg } from "./site";

export const OG_W = 1200;
export const OG_H = 630;

const root = process.cwd();
// Satori can't read woff2, so the static @fontsource packages supply plain woff files of the same faces.
const font = (pkg: string, file: string) => fs.readFileSync(path.join(root, "node_modules", "@fontsource", pkg, "files", file));
const FONTS = [
  { name: "Inter Tight", data: font("inter-tight", "inter-tight-latin-400-normal.woff"), weight: 400 as const, style: "normal" as const },
  { name: "Inter Tight", data: font("inter-tight", "inter-tight-latin-600-normal.woff"), weight: 600 as const, style: "normal" as const },
  { name: "Fraunces", data: font("fraunces", "fraunces-latin-500-normal.woff"), weight: 500 as const, style: "normal" as const },
];

/** OKLCH → sRGB hex (via OKLab), so the image uses the light tokens exactly. */
export function oklchToHex(L: number, C: number, hDeg: number): string {
  const h = (hDeg * Math.PI) / 180, a = C * Math.cos(h), b = C * Math.sin(h);
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const lin = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s];
  return "#" + lin.map((x) => {
    const v = x <= 0.0031308 ? 12.92 * x : 1.055 * Math.max(x, 0) ** (1 / 2.4) - 0.055;
    return Math.round(Math.min(1, Math.max(0, v)) * 255).toString(16).padStart(2, "0");
  }).join("");
}

/** Light-theme tokens from src/styles/tokens.css (the :root block), as hex. */
function tokens(): Record<string, string> {
  const css = fs.readFileSync(path.join(root, "src", "styles", "tokens.css"), "utf8");
  const block = css.slice(css.indexOf(":root {"), css.indexOf("}", css.indexOf(":root {")));
  return Object.fromEntries([...block.matchAll(/--([\w-]+):\s*oklch\(([\d.]+)\s+([\d.]+)\s+([\d.]+)\)/g)]
    .map((m) => [m[1], oklchToHex(+m[2], +m[3], +m[4])]));
}

type Node = { type: string; props: Record<string, unknown> };
const h = (type: string, style: Record<string, unknown>, ...children: (Node | string | null | false)[]): Node => {
  const kids = children.filter((c) => c !== null && c !== false);
  return { type, props: { style, children: kids.length === 1 ? kids[0] : kids } };
};

/** Where the site lives, for the card's footer: host plus base path, e.g. "thatorjohn.github.io/ag-dashboard". */
function siteHost(): string {
  const u = new URL(import.meta.env.BASE_URL, import.meta.env.SITE);
  return (u.host + u.pathname).replace(/\/$/, "");
}

export interface Card { eyebrow: string; title: string; sentence?: string; credit?: string }

export async function render(card: Card): Promise<Buffer> {
  const t = tokens();
  const mark = markSvg(t.ink, t.paper);
  const sentence = card.sentence && card.sentence.length > 230 ? card.sentence.slice(0, 227).replace(/\s+\S*$/, "") + "…" : card.sentence;
  const el = h("div", { width: OG_W, height: OG_H, display: "flex", flexDirection: "column", background: t.paper, color: t.ink,
      fontFamily: "Inter Tight", padding: "56px 72px 44px" },
    h("div", { display: "flex", alignItems: "center", gap: 16 },
      { type: "img", props: { src: `data:image/svg+xml;base64,${Buffer.from(mark).toString("base64")}`, width: 44, height: 44 } },
      h("div", { fontFamily: "Fraunces", fontSize: 34, fontWeight: 500, letterSpacing: -0.5 }, SITE_NAME),
      h("div", { fontSize: 20, fontWeight: 600, color: t["ink-2"], letterSpacing: 2.5, marginLeft: 12, paddingLeft: 16,
        borderLeft: `2px solid ${t.rule}` }, card.eyebrow.toUpperCase())),
    h("div", { display: "flex", flexDirection: "column", flex: 1, justifyContent: "center", gap: 22 },
      h("div", { fontFamily: "Fraunces", fontSize: card.title.length > 28 ? 64 : 80, fontWeight: 500, lineHeight: 1.05, letterSpacing: -1.5 }, card.title),
      sentence ? h("div", { fontSize: 32, lineHeight: 1.35, color: t["ink-2"], paddingRight: 40 }, sentence) : null),
    h("div", { display: "flex", height: 6, borderRadius: 3, background: t.accent, marginBottom: 16 }),
    h("div", { display: "flex", justifyContent: "space-between", fontSize: 20, color: t["ink-2"] },
      h("div", {}, card.credit ?? "Free, plain-language Texas agriculture from public data"),
      h("div", {}, `${siteHost()} · Not an official source`)));
  const svg = await satori(el as any, { width: OG_W, height: OG_H, fonts: FONTS });
  return sharp(Buffer.from(svg)).png().toBuffer();
}
