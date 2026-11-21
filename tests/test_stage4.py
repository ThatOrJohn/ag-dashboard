from datetime import date

import numpy as np

from kad.adapters import stage4


def test_projection_is_polar_stereographic_true_at_60n_centered_on_105w():
    x, y = stage4.project(-105.0, 90.0)
    assert abs(x) < 1e-6 and abs(y) < 1e-6                                    # the pole is the origin
    x, y = stage4.project(-105.0, 60.0)
    assert abs(x) < 1e-6 and abs(-y - 6371200 * np.cos(np.radians(60))) < 1    # true scale at 60° N
    x, _ = stage4.project(-97.0, 31.0)
    assert x > 0                                                               # east of 105° W is +x


def test_county_cells_skip_holes_and_means_skip_mostly_missing_days(monkeypatch):
    # Identity projection, so the ring is drawn straight on a 10 × 10 grid of cell centers 0..9.
    monkeypatch.setattr(stage4, "project", lambda a, b: (np.asarray(a, float), np.asarray(b, float)))
    geom = {"type": "Polygon", "coordinates": [
        [[1.5, 1.5], [5.5, 1.5], [5.5, 5.5], [1.5, 5.5], [1.5, 1.5]],          # cells 2–5 both ways
        [[2.5, 2.5], [3.5, 2.5], [3.5, 3.5], [2.5, 3.5], [2.5, 2.5]]]}         # a hole around cell (3, 3)
    cells = stage4.county_cells({"A": geom}, np.arange(10.0), np.arange(10.0))
    ri, ci = cells["A"]
    assert len(ri) == 15 and not ((ri == 3) & (ci == 3)).any()
    obs = np.full((10, 10), np.nan)
    obs[ri, ci] = 1.0                                                          # 1 inch everywhere
    rows = stage4.county_means(date(2026, 11, 18), obs, cells)
    assert [(r["geo"], r["var"], r["value"], r["source"]) for r in rows] == [("A", "rain_mm", 25.4, "stage4")]
    obs[ri[:10], ci[:10]] = np.nan
    assert stage4.county_means(date(2026, 11, 18), obs, cells) == []
