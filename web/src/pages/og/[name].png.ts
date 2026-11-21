// One share image per page, rebuilt with the data every run: og/index.png (Texas), og/district-<slug>.png,
// og/for-<persona>.png and og/about.png. Base.astro points og:image at them.
import type { APIRoute, GetStaticPaths } from "astro";
import { loadLatest } from "../../lib/data";
import { day } from "../../lib/format";
import { render, type Card } from "../../lib/og";
import type { Headline } from "../../lib/types";

export const getStaticPaths = (() => {
  const L = loadLatest();
  return [
    { params: { name: "index" }, props: { kind: "texas" } },
    ...L.districts.map((d) => ({ params: { name: `district-${d.slug}` }, props: { kind: "district", id: d.slug } })),
    ...L.personas.map((p) => ({ params: { name: `for-${p.id}` }, props: { kind: "persona", id: p.id } })),
    { params: { name: "about" }, props: { kind: "about" } },
  ];
}) satisfies GetStaticPaths;

const drought = (hl?: Headline) => hl?.items?.find((i) => i.topic === "drought")?.text;

export const GET: APIRoute = async ({ props }) => {
  const L = loadLatest();
  const credit = L.sources.usdm.stale ? undefined : `Drought: U.S. Drought Monitor, map of ${day(L.sources.usdm.as_of)}`;
  let card: Card;
  if (props.kind === "district") {
    const d = L.districts.find((x) => x.slug === props.id)!;
    card = { eyebrow: "NASS district", title: `${d.name} this week`, sentence: drought(d.headline), credit };
  } else if (props.kind === "persona") {
    const p = L.personas.find((x) => x.id === props.id)!;
    card = { eyebrow: "This week", title: `${p.name}: Texas this week`, sentence: drought(L.texas.headline), credit };
  } else if (props.kind === "about") {
    card = { eyebrow: "About", title: "About the data",
      sentence: "Where every figure comes from, how district totals are computed, and what I don't claim." };
  } else {
    card = { eyebrow: "This week", title: "Texas agriculture this week", sentence: drought(L.texas.headline), credit };
  }
  return new Response(new Uint8Array(await render(card)), { headers: { "Content-Type": "image/png" } });
};
