// County and state shapes from us-atlas (Census cartographic boundaries, 1:10m), projected at build time.
import { geoAlbersUsa, geoCentroid, geoConicEqualArea, geoPath } from "d3-geo";
import { feature, mesh } from "topojson-client";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import type { GeometryCollection, Topology } from "topojson-specification";
import us from "us-atlas/counties-10m.json" with { type: "json" };

const topo = us as unknown as Topology<{ counties: GeometryCollection; states: GeometryCollection; nation: GeometryCollection }>;
const counties = feature(topo, topo.objects.counties) as FeatureCollection<Geometry>;

const states = feature(topo, topo.objects.states) as FeatureCollection<Geometry, { name: string }>;
const stateNames = new Map(states.features.map(({ id, properties }) => [String(id), properties.name]));
export const stateName = (fips: string) => stateNames.get(fips) ?? fips;

/** SVG paths for counties in a state fitted to width × height, plus group
 *  borders: the outer edge and every edge between counties in different groups (districts). */
export function countyPaths(stateFips: string, keep: Set<string> | null, width: number, height: number,
                            groupOf: (fips: string) => string) {
  const inSet = (id: string) => id.startsWith(stateFips) && (!keep || keep.has(id));
  const feats = counties.features.filter(({ id }) => inSet(String(id)));
  if (!stateFips || !feats.length) return { shapes: [], borders: "" };
  const collection: FeatureCollection<Geometry> = { type: "FeatureCollection", features: feats };
  const [lon, lat] = geoCentroid(collection);
  const proj = geoConicEqualArea().parallels([lat - 4, lat + 4]).rotate([-lon, 0])
    .fitSize([width, height], collection);
  const path = geoPath(proj);
  const borders = path(mesh(topo, topo.objects.counties, (a, b) => {
    const fa = String(a.id), fb = String(b.id);
    if (a === b) return inSet(fa);
    if (inSet(fa) !== inSet(fb)) return true;
    return inSet(fa) && groupOf(fa) !== groupOf(fb);
  })) ?? "";
  return {
    shapes: feats.map((f) => shape(path, f)),
    borders,
  };
}

function shape(path: ReturnType<typeof geoPath>, f: Feature<Geometry>) {
  const [cx, cy] = path.centroid(f);
  return { fips: String(f.id), d: path(f) ?? "", cx, cy, area: path.area(f), bounds: path.bounds(f) };
}

/** National stories draw state outlines, including Alaska and Hawaii in their inset positions. */
export function statePaths(width: number, height: number) {
  const path = geoPath(geoAlbersUsa().fitSize([width, height], states));
  const shapes = states.features.map((f) => shape(path, f)).filter(({ d }) => d);
  return { shapes, borders: shapes.map(({ d }) => d).join("") };
}

/** Greedy label placement at build time: biggest county first, each label tries full size then smaller,
 *  and is dropped when it would still overlap a placed label. Returns fips → size factor (0 = no label).
 *  Width is estimated (Inter Tight semibold averages ~0.56 em per character). */
export function placeLabels(items: { fips: string; text: string; cx: number; cy: number; area: number }[],
                            base: number, steps = [1, 0.85, 0.72], scale = 1): Map<string, number> {
  const placed: [number, number, number, number][] = [];
  const out = new Map<string, number>();
  const hit = (a: number[], b: number[]) =>
    a[0] < b[2] + 2 * scale && a[2] + 2 * scale > b[0] && a[1] < b[3] + scale && a[3] + scale > b[1];
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
