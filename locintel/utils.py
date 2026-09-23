"""Fonctions transverses : environnement, entrées/sorties, normalisation."""
import logging
import os
import unicodedata
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from . import config

log = logging.getLogger("locintel")


def setup():
    """Prépare l'environnement d'exécution (logs, dossiers, réseau)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s",
                        datefmt="%H:%M:%S")
    # Certains postes Windows exportent un CURL_CA_BUNDLE vers un fichier absent
    # (installation PostgreSQL) : requests échoue alors sur toute requête HTTPS.
    for var in ("CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        path = os.environ.get(var)
        if path and not Path(path).exists():
            log.warning("Variable %s ignorée : fichier introuvable (%s)", var, path)
            os.environ.pop(var)
    for d in (config.BRONZE, config.SILVER, config.GOLD, config.FIGURES, config.CACHE):
        d.mkdir(parents=True, exist_ok=True)


def normalize_text(s) -> str:
    """Minuscules, sans accents latins, espaces réduits. L'arabe est conservé."""
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def minmax(x: pd.Series, clip=(0.01, 0.99)) -> pd.Series:
    """Normalisation min-max robuste : on écrête aux centiles 1 et 99 pour
    qu'un seul hexagone extrême n'écrase pas toute l'échelle."""
    x = x.astype(float)
    lo, hi = x.quantile(clip[0]), x.quantile(clip[1])
    if hi == lo:
        return pd.Series(0.0, index=x.index)
    return ((x.clip(lo, hi) - lo) / (hi - lo)).round(4)


def to_points(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Polygones OSM (bâtiments d'agence, campus...) -> points représentatifs."""
    gdf = gdf.copy()
    metric = gdf.to_crs(config.CRS_METRIC)
    pts = metric.geometry.where(metric.geom_type == "Point", metric.geometry.representative_point())
    gdf["geometry"] = pts.to_crs(gdf.crs)
    return gdf


def flatten_osm(gdf: gpd.GeoDataFrame, keep: list[str]) -> gpd.GeoDataFrame:
    """Garde les colonnes utiles d'une extraction OSM et les rend écrivables."""
    gdf = gdf.reset_index()
    gdf["osm_id"] = gdf["element"].str[0] + gdf["id"].astype(str) if "element" in gdf else gdf.index
    cols = ["osm_id"] + [c for c in keep if c in gdf.columns] + ["geometry"]
    out = gdf[cols].copy()
    for c in out.columns:
        if c != "geometry" and out[c].dtype == object:
            out[c] = out[c].map(lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) else str(v))
    return out


def write(gdf, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    gdf.to_file(path, driver="GPKG")
    log.info("  -> %s (%d lignes)", path.relative_to(config.ROOT), len(gdf))


def read(path: Path) -> gpd.GeoDataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path} manquant : lancez d'abord l'étape précédente du pipeline.")
    return gpd.read_file(path)
