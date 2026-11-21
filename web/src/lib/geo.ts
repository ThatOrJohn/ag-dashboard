// County and state shapes from us-atlas (Census cartographic boundaries, 1:10m), projected at build time.
import { geoConicEqualArea, geoPath } from "d3-geo";
import { feature, mesh } from "topojson-client";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import type { GeometryCollection, Topology } from "topojson-specification";
import us from "us-atlas/counties-10m.json";

const topo = us as unknown as Topology<{ counties: GeometryCollection; states: GeometryCollection; nation: GeometryCollection }>;
const counties = feature(topo, topo.objects.counties) as FeatureCollection<Geometry>;

export const TX = "48";

function texasCounties(keep?: Set<string>): Feature<Geometry>[] {
  return counties.features.filter((f) => String(f.id).startsWith(TX) && (!keep || keep.has(String(f.id))));
}

/** SVG paths for a set of Texas counties (all when `keep` is null) fitted to width × height, plus group
 *  borders: the outer edge and every edge between counties in different groups (districts). */
export function countyPaths(keep: Set<string> | null, width: number, height: number, groupOf: (fips: string) => string) {
  const feats = texasCounties(keep ?? undefined);
  const proj = geoConicEqualArea().parallels([27.5, 35]).rotate([100, 0])
    .fitSize([width, height], { type: "FeatureCollection", features: feats });
  const path = geoPath(proj);
  const inSet = (id: string) => id.startsWith(TX) && (!keep || keep.has(id));
  const borders = path(mesh(topo, topo.objects.counties, (a, b) => {
    const fa = String(a.id), fb = String(b.id);
    if (a === b) return inSet(fa);
    if (inSet(fa) !== inSet(fb)) return true;
    return inSet(fa) && groupOf(fa) !== groupOf(fb);
  })) ?? "";
  return {
    counties: feats.map((f) => {
      const [cx, cy] = path.centroid(f);
      return { fips: String(f.id), d: path(f) ?? "", cx, cy, area: path.area(f) };
    }),
    borders,
  };
}

/** Greedy label placement at build time: biggest county first, each label tries full size then smaller,
 *  and is dropped when it would still overlap a placed label. Returns fips → size factor (0 = no label).
 *  Width is estimated (Inter Tight semibold averages ~0.56 em per character). */
export function placeLabels(items: { fips: string; text: string; cx: number; cy: number; area: number }[],
                            base: number, steps = [1, 0.85, 0.72]): Map<string, number> {
  const placed: [number, number, number, number][] = [];
  const out = new Map<string, number>();
  const hit = (a: number[], b: number[]) => a[0] < b[2] + 2 && a[2] + 2 > b[0] && a[1] < b[3] + 1 && a[3] + 1 > b[1];
  for (const it of [...items].sort((a, b) => b.area - a.area)) {
    out.set(it.fips, 0);
    for (const k of steps) {
      const w = it.text.length * 0.56 * base * k, h = base * k * 1.05;
      const box: [number, number, number, number] = [it.cx - w / 2, it.cy - h / 2, it.cx + w / 2, it.cy + h / 2];
      if (!placed.some((b) => hit(box, b))) { placed.push(box); out.set(it.fips, k); break; }
    }
  }
  return out;
}
