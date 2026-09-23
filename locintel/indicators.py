"""Étape 3 — Indicateurs par hexagone H3 (Silver -> table d'indicateurs).

Quatre familles : demande, concurrence, accessibilité, attractivité.
Chaque indicateur brut est conservé à côté de sa version normalisée (0-1),
pour que le client puisse toujours lire la valeur réelle (habitants, mètres).
"""
import geopandas as gpd
import h3
import numpy as np
import pandas as pd

from . import config
from .utils import log, minmax, read, write


def _distances(a: gpd.GeoSeries, b: gpd.GeoSeries) -> np.ndarray:
    """Matrice des distances (m) entre deux séries de points en EPSG:26191."""
    ax, ay = a.x.values[:, None], a.y.values[:, None]
    return np.hypot(ax - b.x.values[None, :], ay - b.y.values[None, :])


def _ring_sum(values: pd.Series, k: int) -> pd.Series:
    """Somme d'une valeur sur l'hexagone et ses voisins jusqu'à l'anneau k."""
    lookup = values.to_dict()
    return pd.Series({c: sum(lookup.get(n, 0) for n in h3.grid_disk(c, k)) for c in values.index})


def run():
    grid = read(config.SILVER / "grille_h3.gpkg")
    pop_df = pd.read_parquet(config.SILVER / "population_h3.parquet").set_index("h3")
    pop = pop_df["population"]
    agences = read(config.SILVER / "agences.gpkg")
    poi = read(config.SILVER / "poi.gpkg")
    tc = read(config.SILVER / "transport.gpkg")
    axes = read(config.SILVER / "axes.gpkg")

    df = grid.copy()
    centres = df.geometry.centroid

    # --- Demande -----------------------------------------------------------
    df["population_kontur"] = df["h3"].map(pop_df["population_kontur"]).fillna(0).astype(int)
    df["population"] = df["h3"].map(pop).fillna(0).astype(int)   # calée sur le RGPH 2024
    df["pop_k1"] = df["h3"].map(_ring_sum(pop, config.K_RING)).fillna(0).astype(int)

    # --- Concurrence (agences uniquement, les GAB OSM sont trop incomplets) -
    ag = agences[agences["type"] == "agence"]
    conc, cli = ag[~ag["est_client"]], ag[ag["est_client"]]
    d_conc, d_cli = _distances(centres, conc.geometry), _distances(centres, cli.geometry)
    df["n_concurrents_1km"] = (d_conc < config.RAYON_CONCURRENCE_M).sum(axis=1)
    df["n_agences_client_1km"] = (d_cli < config.RAYON_CONCURRENCE_M).sum(axis=1)
    df["dist_concurrent_m"] = d_conc.min(axis=1).round()
    df["dist_agence_client_m"] = d_cli.min(axis=1).round() if len(cli) else np.inf
    n_tot = df["n_concurrents_1km"] + df["n_agences_client_1km"]
    df["hab_par_agence_1km"] = (df["pop_k1"] / n_tot.replace(0, np.nan)).round()

    # --- Accessibilité -----------------------------------------------------
    d_tc = _distances(centres, tc.geometry)
    df["dist_transport_m"] = d_tc.min(axis=1).round()
    df["mode_transport_proche"] = tc["mode"].values[d_tc.argmin(axis=1)]
    # Station nommée la plus proche : le repère que le client comprend (« près de la station X »)
    # (libellés en caractères latins, pour des fiches homogènes en français)
    nommees = tc[tc["name"].fillna("").str.contains(r"[A-Za-z]")].reset_index(drop=True)
    df["station_proche"] = nommees["name"].values[_distances(centres, nommees.geometry).argmin(axis=1)]
    nearest = gpd.sjoin_nearest(gpd.GeoDataFrame(geometry=centres, crs=df.crs), axes[["geometry"]],
                                distance_col="d")
    df["dist_axe_m"] = nearest.groupby(level=0)["d"].min().round().values

    # --- Attractivité économique -------------------------------------------
    j = gpd.sjoin(poi, df[["h3", "geometry"]], predicate="within")
    counts = j.pivot_table(index="h3", columns="categorie", values="osm_id", aggfunc="count", fill_value=0)
    for cat in config.POIDS_POI:
        if cat not in counts:
            counts[cat] = 0
    counts = counts.reindex(df["h3"]).fillna(0).astype(int)
    for cat in config.POIDS_POI:
        df[f"n_{cat}"] = counts[cat].values
    raw = sum(counts[c] * w for c, w in config.POIDS_POI.items())
    df["attractivite_brute_k1"] = df["h3"].map(_ring_sum(raw, config.K_RING)).round(1)

    # --- Normalisation 0-1 ---------------------------------------------------
    df["demande_norm"] = minmax(df["pop_k1"])
    df["concurrence_norm"] = minmax(df["n_concurrents_1km"])
    wa = config.POIDS_ACCES
    df["accessibilite_norm"] = (wa["transport_collectif"] * (1 - minmax(df["dist_transport_m"]))
                                + wa["axe_principal"] * (1 - minmax(df["dist_axe_m"]))).round(4)
    # log : quelques hexagones du centre concentrent des centaines de commerces
    df["attractivite_norm"] = minmax(np.log1p(df["attractivite_brute_k1"]))

    # --- Exclusions ---------------------------------------------------------
    sat = df["dist_agence_client_m"] < config.RAYON_SATURATION_CLIENT_M
    vide = df["pop_k1"] < config.POP_MIN_ZONE_K1
    df["exclu"] = sat | vide
    df["motif_exclusion"] = np.select(
        [sat, vide],
        [f"Agence {config.CLIENT_BRAND} à moins de {config.RAYON_SATURATION_CLIENT_M} m",
         f"Zone de chalandise < {config.POP_MIN_ZONE_K1} habitants"], default="")
    log.info("Indicateurs calculés sur %d hexagones, %d exclus (%d saturés client, %d peu peuplés)",
             len(df), df["exclu"].sum(), sat.sum(), (vide & ~sat).sum())

    write(df, config.SILVER / "indicateurs_h3.gpkg")
