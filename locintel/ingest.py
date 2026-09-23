"""Étape 1 — Ingestion : sources brutes -> couche Bronze.

Rien n'est corrigé ici : on stocke ce que les sources renvoient, avec la date
d'extraction, pour pouvoir toujours remonter à l'état d'origine (lineage).
"""
import gzip
import json
import shutil
from datetime import datetime, timezone

import osmnx as ox
import requests

from . import config
from .utils import flatten_osm, log, write

OSM_KEEP = ["amenity", "shop", "office", "railway", "public_transport", "highway",
            "name", "name:fr", "brand", "brand:wikidata", "operator", "network",
            "admin_level", "boundary"]


def _osm(polygon, tags, name):
    log.info("OSM : %s", name)
    gdf = ox.features_from_polygon(polygon, tags=tags)
    return flatten_osm(gdf, OSM_KEEP)


def run():
    ox.settings.cache_folder = str(config.CACHE / "osmnx")
    ox.settings.use_cache = True
    ox.settings.requests_timeout = 300

    log.info("Limite communale : %s", config.PLACE)
    boundary = ox.geocode_to_gdf(config.PLACE)[["osm_id", "display_name", "geometry"]]
    write(boundary, config.BRONZE / "osm_limite_casablanca.gpkg")
    poly = boundary.geometry.iloc[0]

    arr = _osm(poly, {"boundary": "administrative"}, "arrondissements")
    arr = arr[(arr["admin_level"] == config.ARRONDISSEMENT_ADMIN_LEVEL)
              & arr.geom_type.isin(["Polygon", "MultiPolygon"])]
    write(arr, config.BRONZE / "osm_arrondissements.gpkg")

    write(_osm(poly, {"amenity": ["bank", "atm"]}, "banques et GAB"),
          config.BRONZE / "osm_banques.gpkg")

    write(_osm(poly, {"shop": True, "office": True,
                      "amenity": ["university", "college", "clinic", "hospital", "doctors",
                                  "dentist", "pharmacy", "restaurant", "cafe", "fast_food",
                                  "marketplace"]},
               "points d'intérêt économiques"),
          config.BRONZE / "osm_poi.gpkg")

    write(_osm(poly, {"railway": ["tram_stop", "station", "halt"],
                      "public_transport": ["station", "platform", "stop_position"],
                      "highway": "bus_stop"},
               "arrêts de transport"),
          config.BRONZE / "osm_transport.gpkg")

    roads = _osm(poly, {"highway": ["motorway", "trunk", "primary", "secondary",
                                    "motorway_link", "trunk_link", "primary_link"]},
                 "axes routiers principaux")
    write(roads[roads.geom_type.isin(["LineString", "MultiLineString"])],
          config.BRONZE / "osm_axes.gpkg")

    _download_bank_metadata(boundary)
    _download_kontur()

    meta = {"date_extraction_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "osm_source": "OpenStreetMap via Overpass API (osmnx " + ox.__version__ + ")",
            "osm_licence": "ODbL 1.0 — © contributeurs OpenStreetMap",
            "kontur_url": config.KONTUR_URL, "kontur_date": config.KONTUR_DATE,
            "kontur_licence": "CC BY 4.0 — Kontur Population"}
    (config.BRONZE / "_metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                                                  encoding="utf-8")


def _download_bank_metadata(boundary):
    """Date de dernière modification et version de chaque objet banque/GAB.
    osmnx ne renvoie pas ces métadonnées : requête Overpass directe (« out meta »)."""
    import pandas as pd
    b = boundary.total_bounds
    q = (f'[out:json][timeout:120];nwr["amenity"~"^(bank|atm)$"]'
         f'({b[1]},{b[0]},{b[3]},{b[2]});out meta center;')
    for url in config.OVERPASS_URLS * 2:        # deux tours : les serveurs saturent par intermittence
        try:
            r = requests.post(url, data={"data": q}, timeout=180,
                              headers={"User-Agent": "locintel-portfolio/1.0"})
            r.raise_for_status()
            el = r.json()["elements"]
            break
        except Exception as e:  # serveur saturé : on essaie le suivant
            log.warning("Overpass %s indisponible (%s)", url, e)
    else:
        log.warning("Métadonnées OSM non récupérées : la règle de fraîcheur Q16 sera « Non vérifié »")
        return
    df = pd.DataFrame([{"osm_id": e["type"][0] + str(e["id"]), "derniere_modif_osm": e.get("timestamp"),
                        "version_osm": e.get("version")} for e in el])
    df.to_csv(config.BRONZE / "osm_banques_meta.csv", index=False)
    log.info("  -> data/bronze/osm_banques_meta.csv (%d objets)", len(df))


def _download_kontur():
    """Kontur Population : population estimée sur grille H3 res. 8 (tout le Maroc)."""
    target = config.BRONZE / "kontur_population_MA.gpkg"
    if target.exists():
        log.info("Kontur déjà présent : %s", target.name)
        return
    gz = config.CACHE / "kontur_population_MA.gpkg.gz"
    if not gz.exists():
        log.info("Téléchargement Kontur Population (~8 Mo)")
        with requests.get(config.KONTUR_URL, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(gz, "wb") as f:
                shutil.copyfileobj(r.raw, f)
    with gzip.open(gz, "rb") as src, open(target, "wb") as dst:
        shutil.copyfileobj(src, dst)
    log.info("  -> %s", target.relative_to(config.ROOT))
