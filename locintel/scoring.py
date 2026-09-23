"""Étape 4 — Score multicritère (MCDA) et sélection des zones recommandées.

Score = 0,35 × Demande + 0,25 × (1 − Concurrence) + 0,20 × Accessibilité + 0,20 × Attractivité
"""
import geopandas as gpd
import numpy as np
import pandas as pd

from . import config
from .utils import log, read, write


def score(df: pd.DataFrame, poids: dict) -> pd.Series:
    total = sum(poids.values())
    s = (poids["demande"] * df["demande_norm"]
         + poids["concurrence"] * (1 - df["concurrence_norm"])
         + poids["accessibilite"] * df["accessibilite_norm"]
         + poids["attractivite"] * df["attractivite_norm"]) / total
    return s.round(4)


def select_spaced(df: gpd.GeoDataFrame, n: int, min_dist: float) -> list[str]:
    """Sélection gloutonne : le meilleur hexagone, puis le meilleur situé à plus
    de min_dist de tous ceux déjà retenus, etc. Évite 3 recommandations collées."""
    cand = df[~df["exclu"]].sort_values("score", ascending=False)
    pts = cand.geometry.centroid
    chosen, xy = [], []
    for h, p in zip(cand["h3"], pts):
        if all(np.hypot(p.x - x, p.y - y) >= min_dist for x, y in xy):
            chosen.append(h)
            xy.append((p.x, p.y))
        if len(chosen) == n:
            break
    return chosen


SCENARIOS = {
    "Offensif (demande)": {"demande": 0.50, "concurrence": 0.15, "accessibilite": 0.15, "attractivite": 0.20},
    "Prudent (concurrence)": {"demande": 0.25, "concurrence": 0.45, "accessibilite": 0.15, "attractivite": 0.15},
    "Flux (accès + activité)": {"demande": 0.20, "concurrence": 0.20, "accessibilite": 0.30, "attractivite": 0.30},
    "Poids égaux": {"demande": 0.25, "concurrence": 0.25, "accessibilite": 0.25, "attractivite": 0.25},
}


def robustesse(df: pd.DataFrame, recos: list[str]) -> pd.DataFrame:
    """Rang de chaque zone recommandée si le client choisit d'autres pondérations."""
    rows = []
    for nom, p in {"Pondération de référence": config.POIDS_SCORE, **SCENARIOS}.items():
        s = score(df, p).where(~df["exclu"])
        rang = s.rank(ascending=False, method="first")
        for h in recos:
            r = int(rang[df["h3"] == h].iloc[0])
            rows.append({"scenario": nom, "h3": h, "rang": r, "dans_top20": r <= 20})
    return pd.DataFrame(rows)


def run():
    """Entonnoir, étage 1 : le score présélectionne des candidats espacés.
    L'étage 2 (huff.py) les départage sur la clientèle nette captée."""
    df = read(config.SILVER / "indicateurs_h3.gpkg")
    df["score"] = score(df, config.POIDS_SCORE)
    df.loc[df["exclu"], "score"] = np.nan   # un hexagone exclu n'est pas classé
    df["rang"] = df["score"].rank(ascending=False, method="first").astype("Int64")
    df["score_100"] = (df["score"] * 100).round(1)

    candidats = select_spaced(df, config.N_CANDIDATS_HUFF, config.DISTANCE_MIN_ENTRE_CANDIDATS_M)
    df["candidat_huff"] = df["h3"].isin(candidats)
    for h in candidats:
        r = df[df["h3"] == h].iloc[0]
        log.info("Candidat rang %3d : %s (%s) score %.1f — %s hab. k1, %d concurrents à 1 km",
                 r["rang"], h, r["arrondissement"], r["score_100"], f"{r['pop_k1']:,}".replace(",", " "),
                 r["n_concurrents_1km"])
    write(df, config.SILVER / "scores_h3.gpkg")
