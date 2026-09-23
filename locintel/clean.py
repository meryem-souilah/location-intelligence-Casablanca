"""Étape 2 — Nettoyage : Bronze -> Silver.

Toutes les couches Silver sont en EPSG:26191 (mètres) : c'est ici qu'on passe
définitivement des degrés aux mètres, avant tout calcul de distance.
"""
import json
import re

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from . import config
from .brands import NON_BANQUE, NON_IDENTIFIEE, canonical_brand
from .utils import log, read, to_points, write

RAYON_DOUBLON_M = 40   # deux objets de même marque à < 40 m = la même agence


def run():
    boundary = read(config.BRONZE / "osm_limite_casablanca.gpkg")
    arr = clean_arrondissements(read(config.BRONZE / "osm_arrondissements.gpkg"))
    write(arr, config.SILVER / "arrondissements.gpkg")

    grid = build_grid(boundary, arr)
    write(grid, config.SILVER / "grille_h3.gpkg")

    stats = {}
    agences, stats["agences"] = clean_banks(read(config.BRONZE / "osm_banques.gpkg"), arr)
    write(agences, config.SILVER / "agences.gpkg")

    write(clean_poi(read(config.BRONZE / "osm_poi.gpkg")), config.SILVER / "poi.gpkg")
    write(clean_transport(read(config.BRONZE / "osm_transport.gpkg")), config.SILVER / "transport.gpkg")
    write(read(config.BRONZE / "osm_axes.gpkg").to_crs(config.CRS_METRIC)[["osm_id", "highway", "name", "geometry"]],
          config.SILVER / "axes.gpkg")

    pop, stats["population"] = clean_population(grid, arr)
    pop.to_parquet(config.SILVER / "population_h3.parquet", index=False)
    log.info("  -> data/silver/population_h3.parquet (%d hexagones)", len(pop))

    (config.SILVER / "_stats_nettoyage.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")


def clean_arrondissements(arr: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    def nom(r):
        n = r["name:fr"] if "name:fr" in r and pd.notna(r["name:fr"]) else r["name"]
        n = re.sub(r"[^\x00-ɏ'’ -]", "", n).strip()           # retire arabe / tifinagh
        n = re.sub(r"^Arrondissement (de la |de l'|des |du |de |d'|d’)", "", n)
        return n[0].upper() + n[1:]
    arr = arr.copy()
    arr["arrondissement"] = arr.apply(nom, axis=1)
    arr = arr.to_crs(config.CRS_METRIC)
    arr["superficie_km2"] = (arr.area / 1e6).round(2)
    return arr[["osm_id", "arrondissement", "superficie_km2", "geometry"]].reset_index(drop=True)


def build_grid(boundary: gpd.GeoDataFrame, arr: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Grille H3 couvrant la commune (hexagones dont le centre est dans la limite)."""
    poly = boundary.to_crs(config.CRS_WGS84).geometry.union_all()
    cells = sorted(h3.geo_to_cells(poly, config.H3_RES))
    geoms = [Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(c)]) for c in cells]
    grid = gpd.GeoDataFrame({"h3": cells}, geometry=geoms, crs=config.CRS_WGS84)
    grid["lat"] = [h3.cell_to_latlng(c)[0] for c in cells]
    grid["lon"] = [h3.cell_to_latlng(c)[1] for c in cells]
    grid = grid.to_crs(config.CRS_METRIC)

    # Arrondissement = celui qui contient le centre de l'hexagone
    centres = grid[["h3"]].set_geometry(grid.geometry.centroid, crs=grid.crs)
    j = gpd.sjoin(centres, arr[["arrondissement", "geometry"]], predicate="within", how="left")
    grid["arrondissement"] = j.drop_duplicates("h3").set_index("h3").loc[grid["h3"], "arrondissement"].values
    grid["arrondissement"] = grid["arrondissement"].fillna("Hors arrondissement")
    log.info("Grille H3 res.%d : %d hexagones", config.H3_RES, len(grid))
    return grid


def clean_banks(raw: gpd.GeoDataFrame, arr: gpd.GeoDataFrame):
    df = to_points(raw).to_crs(config.CRS_METRIC)
    df["marque"] = [canonical_brand(b, n, o, f) for b, n, o, f in
                    zip(df["brand"], df["name"], df["operator"], df.get("name:fr", [None] * len(df)))]
    df["type"] = df["amenity"].map({"bank": "agence", "atm": "gab"})
    df["marque_osm_renseignee"] = df["brand"].notna()

    s = {
        "objets_bruts": int(len(df)),
        "agences_brutes": int((df["type"] == "agence").sum()),
        "gab_bruts": int((df["type"] == "gab").sum()),
        "agences_sans_tag_brand": int(((df["type"] == "agence") & df["brand"].isna()).sum()),
        "agences_sans_nom_ni_marque": int(((df["type"] == "agence") & df["brand"].isna() & df["name"].isna()).sum()),
        "libelles_distincts_avant": int(df.loc[df["type"] == "agence", ["brand", "name"]]
                                        .fillna("").agg(" | ".join, axis=1).nunique()),
    }
    non_banques = df["marque"] == NON_BANQUE
    s["non_banques_exclues"] = int(non_banques.sum())
    s["exemples_non_banques"] = sorted(set(df.loc[non_banques, "name"].dropna()))[:15]
    df = df[~non_banques].copy()

    # Doublons : même marque, même type, à moins de RAYON_DOUBLON_M (souvent un
    # nœud + le contour du bâtiment). On garde l'objet le mieux renseigné.
    df["_completude"] = df[["brand", "name", "operator"]].notna().sum(axis=1)
    df = df.sort_values("_completude", ascending=False).reset_index(drop=True)
    xy = np.c_[df.geometry.x, df.geometry.y]
    doublon = np.zeros(len(df), dtype=bool)
    for i in range(len(df)):
        if doublon[i]:
            continue
        d = np.hypot(*(xy[i + 1:] - xy[i]).T)
        meme = (df["marque"].values[i + 1:] == df["marque"].values[i]) & \
               (df["type"].values[i + 1:] == df["type"].values[i]) & (d < RAYON_DOUBLON_M)
        doublon[i + 1:] |= meme
    s["doublons_supprimes"] = int(doublon.sum())
    df = df[~doublon].drop(columns="_completude")

    df = gpd.sjoin(df, arr[["arrondissement", "geometry"]], predicate="within", how="left") \
        .drop(columns="index_right").drop_duplicates("osm_id")
    df["arrondissement"] = df["arrondissement"].fillna("Hors arrondissement")
    df["est_client"] = df["marque"] == config.CLIENT_BRAND

    ag = df[df["type"] == "agence"]
    s["agences_retenues"] = int(len(ag))
    s["agences_non_identifiees"] = int((ag["marque"] == NON_IDENTIFIEE).sum())
    s["agences_client"] = int(ag["est_client"].sum())
    s["marques_canoniques"] = int(ag["marque"].nunique())
    s["repartition_marques"] = ag["marque"].value_counts().to_dict()
    log.info("Agences : %d brutes -> %d retenues (%d non-banques, %d doublons), %d marques",
             s["agences_brutes"], s["agences_retenues"], s["non_banques_exclues"],
             s["doublons_supprimes"], s["marques_canoniques"])

    meta = config.BRONZE / "osm_banques_meta.csv"
    if meta.exists():
        df = df.merge(pd.read_csv(meta), on="osm_id", how="left")
    else:
        df["derniere_modif_osm"], df["version_osm"] = None, None
    cols = ["osm_id", "type", "marque", "est_client", "name", "brand", "operator",
            "marque_osm_renseignee", "arrondissement", "derniere_modif_osm", "version_osm", "geometry"]
    return df[cols].reset_index(drop=True), s


def clean_poi(raw: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    df = to_points(raw).to_crs(config.CRS_METRIC)
    a = df["amenity"].fillna("")
    cat = np.select(
        [df["shop"] == "mall",
         a.isin(["university", "college"]),
         a.isin(["clinic", "hospital", "doctors", "dentist", "pharmacy"]),
         df["office"].notna(),
         a.isin(["restaurant", "cafe", "fast_food"]),
         df["shop"].notna() | (a == "marketplace")],
        ["centre_commercial", "enseignement_sup", "sante", "bureau", "restauration", "commerce"],
        default="autre")
    df["categorie"] = cat
    df = df[df["categorie"] != "autre"]
    log.info("POI : %s", df["categorie"].value_counts().to_dict())
    return df[["osm_id", "categorie", "name", "geometry"]].reset_index(drop=True)


def clean_transport(raw: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Ne garde que le transport collectif lourd (tram, busway, train).
    Les ~1 400 arrêts de bus classiques couvrent toute la ville et ne
    discrimineraient pas les zones."""
    df = to_points(raw).to_crs(config.CRS_METRIC)
    net = df["network"].fillna("").str.lower()
    name = df["name"].fillna("").str.lower()
    mode = np.select(
        [net.str.contains("busway"),
         (df["railway"] == "tram_stop") | net.str.contains("tram"),
         df["railway"].isin(["station", "halt"]) & name.str.contains("gare"),
         df["railway"].isin(["station", "halt"])],
        ["busway", "tramway", "train", "tramway"], default="")
    df["mode"] = mode
    df = df[df["mode"] != ""]
    log.info("Transport collectif lourd : %s", df["mode"].value_counts().to_dict())
    return df[["osm_id", "mode", "name", "geometry"]].reset_index(drop=True)


def clean_population(grid: gpd.GeoDataFrame, arr: gpd.GeoDataFrame):
    """Population par hexagone. On garde aussi l'anneau extérieur à la commune :
    un hexagone en bordure a des clients potentiels de l'autre côté de la limite."""
    k = gpd.read_file(config.BRONZE / "kontur_population_MA.gpkg", ignore_geometry=True)
    k = k.rename(columns={c: c.lower() for c in k.columns})
    inside = set(grid["h3"])
    cells = set().union(*(h3.grid_disk(c, config.K_RING) for c in inside))
    pop = pd.DataFrame({"h3": sorted(cells)}).merge(k[["h3", "population"]], on="h3", how="left")
    pop["population"] = pop["population"].fillna(0).round().astype(int)
    pop["population_kontur"] = pop["population"]
    pop["dans_commune"] = pop["h3"].isin(inside)
    total = int(pop.loc[pop["dans_commune"], "population"].sum())

    # Part de chaque hexagone dans chaque arrondissement (pondération surfacique)
    inter = gpd.overlay(grid[["h3", "geometry"]], arr[["arrondissement", "geometry"]], how="intersection")
    inter["surface"] = inter.area
    inter["part"] = inter["surface"] / inter.groupby("h3")["surface"].transform("sum")
    inter = inter.merge(pop[["h3", "population_kontur"]], on="h3")
    inter["pop_kontur_part"] = inter["population_kontur"] * inter["part"]

    # Calage sur le RGPH 2024 par arrondissement
    comp = inter.groupby("arrondissement")["pop_kontur_part"].sum().to_frame("kontur")
    comp["hcp_2024"] = pd.Series(config.HCP_POP_ARRONDISSEMENTS_2024)
    comp["facteur_calage"] = comp["hcp_2024"] / comp["kontur"]   # exact : arrondi seulement à l'export
    comp["ecart_kontur_pct"] = (100 * (comp["kontur"] - comp["hcp_2024"]) / comp["hcp_2024"]).round(1)
    comp.round({"kontur": 0, "facteur_calage": 3}).reset_index().to_csv(config.SILVER / "calage_hcp.csv",
                                                                         index=False)
    if config.CALAGE_HCP:
        inter["pop_calee"] = inter["pop_kontur_part"] * inter["arrondissement"].map(comp["facteur_calage"])
    else:
        inter["pop_calee"] = inter["pop_kontur_part"]
    # Un morceau = l'intersection d'un hexagone et d'un arrondissement
    inter[["h3", "arrondissement", "part", "pop_calee"]].to_parquet(
        config.SILVER / "hex_arrondissement_parts.parquet", index=False)
    if config.CALAGE_HCP:
        calee = inter.groupby("h3")["pop_calee"].sum()
        pop["population"] = pop["h3"].map(calee).fillna(pop["population_kontur"]).round().astype(int)
        log.info("Calage HCP par arrondissement : facteurs de %.2f à %.2f",
                 comp["facteur_calage"].min(), comp["facteur_calage"].max())

    s = {"population_kontur_commune": total,
         "population_hcp_reference": config.HCP_POP_CASABLANCA_2024,
         "ecart_kontur_vs_hcp_pct": round(100 * (total - config.HCP_POP_CASABLANCA_2024)
                                          / config.HCP_POP_CASABLANCA_2024, 1),
         "hexagones_sans_population": int(((pop["population_kontur"] == 0) & pop["dans_commune"]).sum()),
         "hexagones_au_plafond_kontur": int(((pop["population_kontur"] >= config.KONTUR_PLAFOND)
                                             & pop["dans_commune"]).sum()),
         "ecart_max_arrondissement_pct": float(comp["ecart_kontur_pct"].abs().max()),
         "arrondissement_ecart_max": str(comp["ecart_kontur_pct"].abs().idxmax()),
         "population_apres_calage": int(pop.loc[pop["dans_commune"], "population"].sum())}
    log.info("Population Kontur sur la grille : %s hab. (HCP 2024 : %s, écart %s %%)",
             f"{total:,}".replace(",", " "), f"{config.HCP_POP_CASABLANCA_2024:,}".replace(",", " "),
             s["ecart_kontur_vs_hcp_pct"])
    return pop, s
