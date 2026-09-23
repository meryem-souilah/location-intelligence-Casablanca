"""Étape 10 — Dashboard web autonome (dashboard/index.html).

Même contenu que le dashboard Power BI, sans logiciel : un seul fichier HTML où
les tables Gold sont embarquées en JSON et le score se recalcule dans le
navigateur quand on bouge les curseurs.
"""
import json
import math

import pandas as pd

from . import config
from .scoring import SCENARIOS
from .utils import log, read

TEMPLATE = config.ROOT / "locintel" / "templates" / "dashboard.html"
OUT = config.ROOT / "dashboard" / "index.html"


class Projection:
    """Projection équirectangulaire locale (suffisante à l'échelle d'une ville),
    en coordonnées SVG : x vers l'est, y vers le sud."""

    def __init__(self, lon0, lat0, lon1, lat1, width=1000):
        self.lon0, self.lat1 = lon0, lat1
        self.k = width / ((lon1 - lon0) * math.cos(math.radians((lat0 + lat1) / 2)))
        self.c = math.cos(math.radians((lat0 + lat1) / 2))
        self.w, self.h = width, (lat1 - lat0) * self.k

    def xy(self, lon, lat):
        return round((lon - self.lon0) * self.c * self.k, 1), round((self.lat1 - lat) * self.k, 1)

    def path(self, geom) -> str:
        polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        out = []
        for p in polys:
            pts = [self.xy(x, y) for x, y in p.exterior.coords]
            out.append("M" + "L".join(f"{x},{y}" for x, y in pts) + "Z")
        return "".join(out)


def run():
    g = config.GOLD
    fait = pd.read_csv(g / "fait_hexagones.csv")
    hexes = read(config.SILVER / "scores_h3.gpkg").to_crs(config.CRS_WGS84).set_index("h3")
    arr = read(config.SILVER / "arrondissements.gpkg").to_crs(config.CRS_WGS84)
    ag = pd.read_csv(g / "dim_agences.csv")
    ag = ag[ag["type"] == "agence"]
    flux = pd.read_csv(g / "huff_flux.csv")

    x0, y0, x1, y1 = hexes.total_bounds
    pad = 0.004
    pr = Projection(x0 - pad, y0 - pad, x1 + pad, y1 + pad)

    cols = ["h3", "arrondissement", "station_proche", "axe_proche", "population", "pop_k1", "n_concurrents_1km",
            "n_agences_client_1km", "dist_concurrent_m", "dist_agence_client_m", "dist_transport_m",
            "mode_transport_proche", "dist_axe_m", "attractivite_brute_k1", "demande_norm", "concurrence_norm",
            "accessibilite_norm", "attractivite_norm", "exclu", "motif_exclusion", "score_100", "rang",
            "candidat_huff", "recommande", "rang_recommandation", "clients_captes", "cannibalisation_client",
            "gain_net_client", "lat", "lon"]
    hx = []
    for d in fait[cols].to_dict("records"):   # types Python natifs, sérialisables en JSON
        d = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in d.items()}
        d["path"] = pr.path(hexes.loc[d["h3"], "geometry"])
        d["cx"], d["cy"] = pr.xy(d["lon"], d["lat"])
        hx.append(d)

    arr["geometry"] = arr.geometry.simplify(0.0002)
    arr_paths = [{"nom": n, "path": pr.path(geom)} for n, geom in zip(arr["arrondissement"], arr.geometry)]

    marques = pd.read_csv(g / "dim_marques.csv")
    idx = {m: i for i, m in enumerate(marques["marque"])}
    agences = [[*pr.xy(lo, la), idx.get(m, -1), int(c)] for lo, la, m, c in
               zip(ag["lon"], ag["lat"], ag["marque"], ag["est_client"])]

    fl = {}
    for h, grp in flux.groupby("h3_candidat"):
        fl[h] = [[*pr.xy(lo, la), round(c)] for lo, la, c in
                 zip(grp["lon_origine"], grp["lat_origine"], grp["clients_captes"]) if c >= 20]

    stats = json.loads((config.SILVER / "_stats_nettoyage.json").read_text(encoding="utf-8"))
    meta = json.loads((config.BRONZE / "_metadata.json").read_text(encoding="utf-8"))
    data = {
        "viewBox": [0, 0, pr.w, round(pr.h, 1)],
        "hex": hx, "arr": arr_paths, "agences": agences, "flux": fl,
        "marques": marques.to_dict("records"),
        "arrondissements": pd.read_csv(g / "dim_arrondissements.csv").to_dict("records"),
        "huff": pd.read_csv(g / "huff_candidats.csv").to_dict("records"),
        "portefeuille": json.loads((config.SILVER / "huff_portefeuille.json").read_text(encoding="utf-8")),
        "robustesse": pd.read_csv(g / "robustesse_scenarios.csv").to_dict("records"),
        "qualite": pd.read_csv(g / "qualite_regles.csv").fillna("").to_dict("records"),
        "calage": pd.read_csv(g / "qualite_calage_hcp.csv").to_dict("records"),
        "poids": {k: round(v * 100) for k, v in config.POIDS_SCORE.items()},
        "scenarios": {n: {k: round(v * 100) for k, v in p.items()} for n, p in SCENARIOS.items()},
        "client": config.CLIENT_BRAND,
        "stats": {"population": config.HCP_POP_CASABLANCA_2024,
                  "agences": stats["agences"]["agences_retenues"],
                  "agences_client": stats["agences"]["agences_client"],
                  "date_osm": meta["date_extraction_utc"][:10]},
    }
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("NaN", "null").replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", js)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    log.info("Dashboard web : dashboard/index.html (%d Ko)", OUT.stat().st_size // 1024)
