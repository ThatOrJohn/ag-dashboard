// Build-time geometry for flyover maps (decision 0027): shapes, a waypoint per stop, the curved route
// between them, a camera box per stop, and labels placed for each stop's own zoom. Shared by the player and
// the Stories index thumbnails so both draw the same route.
import { countyPaths, placeLabels, stateName, statePaths } from "../geo";
import type { FlyoverIcon, FlyoverStop } from "./flyover";
import type { StoryDisplayContext } from "./model";

export type Box = [number, number, number, number];
type Point = [number, number];

interface Options {
  /** Draw the counties around a district, faintly, so zooming out shows where it sits. */
  surroundings?: boolean;
  /** Skip per-stop labels and scenes (thumbnails only need shapes and the route). */
  scenes?: boolean;
}

const overlaps = ([[x0, y0], [x1, y1]]: [[number, number], [number, number]], [l, t, r, b]: number[]) =>
  x1 > l && x0 < r && y1 > t && y0 < b;

export function flyoverGeometry(stops: readonly FlyoverStop[], { area, counties }: Pick<StoryDisplayContext, "area" | "counties">,
                                width: number, height: number, { surroundings = false, scenes: withScenes = true }: Options = {}) {
  const own = new Set(Object.keys(counties).filter((fips) => area.level === "state" || counties[fips].district === area.id));
  const groupOf = (fips: string) => counties[fips]?.district ?? "";
  let { shapes, borders } = area.level === "us" ? statePaths(width, height)
    : area.level === "district" && surroundings
      ? countyPaths(area.stateFips, new Set(Object.keys(counties)), width, height, groupOf, own)
      : countyPaths(area.stateFips, own, width, height, groupOf);
  if (area.level === "district" && surroundings) {
    const near = [-width * .8, -height * .8, width * 1.8, height * 1.8];
    shapes = shapes.filter((shape) => own.has(shape.fips) || overlaps(shape.bounds, near));
  }
  const inArea = (fips: string) => area.level === "us" || own.has(fips);
  const byFips = new Map(shapes.map((shape) => [shape.fips, shape]));
  const nameOf = (fips: string) => area.level === "us" ? stateName(fips) : counties[fips]?.name ?? "";

  // Each stop's waypoint is the area-weighted centroid of its shapes; the whole-area stops have none.
  const selections = stops.map(({ fips }) => fips.map((id) => byFips.get(id)).filter((shape) => shape != null));
  const points: (Point | null)[] = selections.map((selected) => {
    const total = selected.reduce((sum, { area }) => sum + area, 0);
    return total ? [selected.reduce((s, { area, cx }) => s + area * cx, 0) / total,
      selected.reduce((s, { area, cy }) => s + area * cy, 0) / total] : null;
  });

  // Legs bow gently, alternating sides, so the route reads as a flight path rather than a polyline.
  const legs = points.slice(0, -1).flatMap((from, i) => {
    const to = points[i + 1];
    if (!from || !to) return [];
    const [dx, dy] = [to[0] - from[0], to[1] - from[1]];
    const bow = (i % 2 ? .22 : -.22);
    const control: Point = [(from[0] + to[0]) / 2 - dy * bow, (from[1] + to[1]) / 2 + dx * bow];
    const r = (n: number) => n.toFixed(1);
    return [{ from: i, to: i + 1, d: `M${r(from[0])} ${r(from[1])}Q${r(control[0])} ${r(control[1])} ${r(to[0])} ${r(to[1])}` }];
  });

  const whole: Box = [-width * .025, -height * .025, width * 1.05, height * 1.05];
  const boxes = selections.map((selected): Box => {
    if (!selected.length) return whole;
    const [left, top, right, bottom] = selected.reduce(([l, t, r, b], { bounds: [[x0, y0], [x1, y1]] }) =>
      [Math.min(l, x0), Math.min(t, y0), Math.max(r, x1), Math.max(b, y1)], [Infinity, Infinity, -Infinity, -Infinity]);
    // A lone county gets more room around it, so its neighbors and the route in and out stay in view.
    const scale = Math.max((right - left) / width, (bottom - top) / height, .07) * (selected.length === 1 ? 2.2 : 1.35);
    const w = width * scale, h = height * scale;
    return [(left + right - w) / 2, (top + bottom - h) / 2, w, h];
  });

  const scenes = !withScenes ? [] : stops.map(({ pin, name }, index) => {
    const box = boxes[index];
    const scale = box[2] / width;
    const size = 17 * scale;
    const point = points[index];
    const selected = selections[index];
    const single = selected.length === 1 && pin?.fips === selected[0].fips;
    const shape = pin && byFips.get(pin.fips);
    const marker = pin && shape ? {
      ...pin, x: single && point ? point[0] : shape.cx, y: single && point ? point[1] : shape.cy, scale: scale * 1.5,
    } : null;

    // On the whole area, name the places the tour visits, under their waypoints. At a stop, name its counties,
    // but leave room around the waypoint and the pin so labels never sit under a marker.
    const keepClear = [point, marker && [marker.x, marker.y]].filter((p): p is Point => p != null);
    const items = !selected.length
      ? stops.flatMap(({ name: text }, i) => {
          const p = points[i];
          return p ? [{ fips: `stop-${i}`, text: text.replace(/ County$/, ""), cx: p[0], cy: p[1] + 19 * scale, area: 1e9 - i }] : [];
        })
      : selected.map((s) => ({ ...s, text: nameOf(s.fips) }))
          .filter(({ text, cx, cy }) => text && !keepClear.some(([x, y]) => Math.hypot(cx - x, cy - y) < 24 * scale));
    const fit = placeLabels(items, size, undefined, scale);
    return {
      index, box, name,
      spot: selected.map(({ d }) => d).join(""),
      labels: items.flatMap(({ fips, cx, cy, text }) => {
        const factor = fit.get(fips);
        return factor ? [{ cx, cy, text, size: size * factor, stop: fips.startsWith("stop-") }] : [];
      }),
      marker,
    };
  });

  const stopOf = new Map(stops.flatMap(({ fips }, i) => i === 0 || i === stops.length - 1 ? [] : fips.map((id) => [id, i] as const)));
  return {
    shapes: shapes.map((shape) => ({ ...shape, inArea: inArea(shape.fips), stop: stopOf.get(shape.fips), name: nameOf(shape.fips) })),
    borders, points, legs, boxes, whole, scenes,
  };
}

/** Faint survey grid behind the map: coarse lines everywhere the camera can reach, fine ones over the area. */
export function surveyGrid(width: number, height: number) {
  const lines = (step: number, [l, t, r, b]: number[]) => {
    const out: string[] = [];
    for (let x = Math.ceil(l / step) * step; x <= r; x += step) out.push(`M${x} ${t}V${b}`);
    for (let y = Math.ceil(t / step) * step; y <= b; y += step) out.push(`M${l} ${y}H${r}`);
    return out.join("");
  };
  return {
    coarse: lines(64, [-width, -height, width * 2, height * 2]),
    fine: lines(16, [-width * .1, -height * .1, width * 1.1, height * 1.1]),
  };
}

export const pinPaths: Record<FlyoverIcon, string> = {
  cotton: "M12 19v3m0-3c-3 0-8-3-8-7a4 4 0 0 1 4-4 4 4 0 0 1 8 0 4 4 0 0 1 4 4c0 4-5 7-8 7Z",
  cattle: "M4 9 1 5l6 2h10l6-2-3 4-3 2-1 7-2 3h-4l-2-3-1-7-3-2Zm5 7h6",
  water: "M12 2C9 7 5 11 5 15a7 7 0 0 0 14 0c0-4-4-8-7-13Z",
  well: "M3 10h18L12 3 3 10Zm3 0v11m12-11v11M4 21h16m-8-11v6m-3 0h6v5H9z",
  rain: "M8 9v12h8V9M7 9h10m-9 5h4m-4 3h4M12 2l-2 4h4z",
};
