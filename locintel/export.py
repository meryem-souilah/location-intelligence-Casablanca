"""Étape 7 — Export de la couche Gold pour Power BI (schéma en étoile).

Fait_Hexagones (1 ligne / hexagone)  ─┬─ Dim_Arrondissement
                                      ├─ Huff_Candidats / Huff_Flux
Dim_Agences (1 ligne / agence)       ─┘  Dim_Marque
Toutes les coordonnées sont en WGS84 (lat/lon), attendu par Azure Maps.
"""
import shutil

import geopandas as gpd
import pandas as pd

from . import config
from .utils import log, read

ATTRIBUTION = "© contributeurs OpenStreetMap (ODbL) ; population © Kontur (CC BY 4.0)"


def _csv(df: pd.DataFrame, name: str):
    df.to_csv(config.GOLD / name, index=False, encoding="utf-8-sig")
    log.info("  -> data/gold/%s (%d lignes)", name, len(df))


def population_par_arrondissement() -> pd.Series:
    """Population calée par arrondissement, sommée sur les morceaux d'hexagones :
    un hexagone à cheval sur une limite est réparti au prorata de sa surface."""
    parts = pd.read_parquet(config.SILVER / "hex_arrondissement_parts.parquet")
    return parts.groupby("arrondissement")["pop_calee"].sum().round().astype(int).rename("population")


def run():
    sc = read(config.SILVER / "scores_h3.gpkg")
    ag = read(config.SILVER / "agences.gpkg")
    arr = read(config.SILVER / "arrondissements.gpkg")
    axes = read(config.SILVER / "axes.gpkg")
    huff = pd.read_csv(config.SILVER / "huff_candidats.csv")

    # Rue principale la plus proche : aide le client à situer l'hexagone
    named = axes[axes["name"].notna()]
    near = gpd.sjoin_nearest(sc[["h3"]].set_geometry(sc.geometry.centroid, crs=sc.crs),
                             named[["name", "geometry"]], distance_col="_d")
    sc["axe_proche"] = near.drop_duplicates("h3").set_index("h3").loc[sc["h3"], "name"].values

    wgs = sc.to_crs(config.CRS_WGS84)
    fait = pd.DataFrame(wgs.drop(columns="geometry"))
    fait["wkt"] = wgs.geometry.to_wkt(rounding_precision=6)
    fait = fait.merge(huff[["h3", "clients_captes", "cannibalisation_client", "gain_net_client", "rang_huff"]],
                      on="h3", how="left")
    _csv(fait, "fait_hexagones.csv")
    fait.to_parquet(config.GOLD / "fait_hexagones.parquet", index=False)

    geo_cols = ["h3", "arrondissement", "population", "pop_k1", "n_concurrents_1km", "score_100", "rang",
                "exclu", "recommande", "geometry"]
    path = config.GOLD / "hexagones.geojson"
    path.unlink(missing_ok=True)
    wgs[geo_cols].to_file(path, driver="GeoJSON")

    agw = ag.to_crs(config.CRS_WGS84)
    dim_ag = pd.DataFrame(agw.drop(columns="geometry"))
    dim_ag["lat"], dim_ag["lon"] = agw.geometry.y.round(6), agw.geometry.x.round(6)
    _csv(dim_ag, "dim_agences.csv")

    ag_only = ag[ag["type"] == "agence"]
    tot = len(ag_only)
    marques = ag_only.groupby("marque").agg(agences=("osm_id", "count")).reset_index()
    marques["part_agences_pct"] = (100 * marques["agences"] / tot).round(1)
    marques["est_client"] = marques["marque"] == config.CLIENT_BRAND
    _csv(marques.sort_values("agences", ascending=False), "dim_marques.csv")

    d = sc.groupby("arrondissement").agg(
        hexagones=("h3", "count"), score_moyen_100=("score_100", "mean"),
        zones_recommandees=("recommande", "sum")).reset_index()
    d = d.merge(population_par_arrondissement().reset_index(), on="arrondissement", how="left")
    cnt = ag_only.groupby(["arrondissement", "est_client"]).size().unstack(fill_value=0) \
        .rename(columns={True: "agences_client", False: "agences_concurrentes"})
    d = d.merge(cnt, on="arrondissement", how="left").fillna({"agences_client": 0, "agences_concurrentes": 0})
    d = d.merge(arr[["arrondissement", "superficie_km2"]], on="arrondissement", how="left")
    d["agences_total"] = d["agences_client"] + d["agences_concurrentes"]
    d["hab_par_agence"] = (d["population"] / d["agences_total"].where(d["agences_total"] > 0)).round()
    d["agences_pour_10k_hab"] = (1e4 * d["agences_total"] / d["population"].where(d["population"] > 0)).round(2)
    d["part_client_pct"] = (100 * d["agences_client"] / d["agences_total"].where(d["agences_total"] > 0)).round(1)
    d["score_moyen_100"] = d["score_moyen_100"].round(1)
    _csv(d, "dim_arrondissements.csv")

    reco = fait[fait["recommande"]].sort_values("rang_recommandation")
    _csv(reco[["rang_recommandation", "h3", "arrondissement", "station_proche", "axe_proche", "lat", "lon", "score_100", "rang",
               "population", "pop_k1", "n_concurrents_1km", "n_agences_client_1km", "dist_concurrent_m",
               "dist_agence_client_m", "hab_par_agence_1km", "dist_transport_m", "mode_transport_proche",
               "dist_axe_m", "attractivite_brute_k1", "demande_norm", "concurrence_norm",
               "accessibilite_norm", "attractivite_norm", "clients_captes", "cannibalisation_client",
               "gain_net_client"]], "recommandations.csv")

    _csv(huff, "huff_candidats.csv")
    shutil.copy(config.SILVER / "huff_flux.csv", config.GOLD / "huff_flux.csv")
    shutil.copy(config.SILVER / "robustesse_scenarios.csv", config.GOLD / "robustesse_scenarios.csv")
    pf = pd.read_json(config.SILVER / "huff_portefeuille.json", typ="series")
    _csv(pf.rename_axis("indicateur").reset_index(name="valeur"), "huff_portefeuille.csv")
    (config.GOLD / "ATTRIBUTION.txt").write_text(ATTRIBUTION + "\n", encoding="utf-8")
