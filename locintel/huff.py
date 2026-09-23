"""Étape 5 — Modèle de Huff : combien de clients une nouvelle agence capterait-elle ?

P(i -> j) = (A_j / d_ij^λ) / Σ_k (A_k / d_ik^λ)

i = hexagone d'origine (habitants), j = agence. A = 1 pour toutes les agences
(on ne connaît ni leur taille ni leur notoriété). Pour chaque site candidat on
compare la situation avant / après ouverture :
- clients captés        = Σ_i pop_i × P(i -> nouvelle agence)
- cannibalisation       = clients que le client perd dans ses propres agences
- gain net              = captés − cannibalisation (pris aux concurrents)

Entonnoir, étage 2 : parmi les candidats présélectionnés par le score, on
recommande ceux qui apportent le plus gros gain net, espacés d'au moins
DISTANCE_MIN_ENTRE_RECOS_M pour ne pas se cannibaliser entre eux.
"""
import json

import geopandas as gpd
import h3
import numpy as np
import pandas as pd

from . import config
from .scoring import robustesse
from .utils import log, read, write


def _utility(d: np.ndarray) -> np.ndarray:
    u = 1.0 / np.maximum(d, config.HUFF_DIST_MIN_M) ** config.HUFF_LAMBDA
    return np.where(d <= config.HUFF_DIST_MAX_M, u, 0.0)


def run():
    scores = read(config.SILVER / "scores_h3.gpkg")
    pop = pd.read_parquet(config.SILVER / "population_h3.parquet")
    ag = read(config.SILVER / "agences.gpkg")
    ag = ag[ag["type"] == "agence"]

    latlng = np.array([h3.cell_to_latlng(c) for c in pop["h3"]])
    origins = gpd.GeoSeries(gpd.points_from_xy(latlng[:, 1], latlng[:, 0]), crs=config.CRS_WGS84) \
        .to_crs(config.CRS_METRIC)
    ox_, oy_ = origins.x.values[:, None], origins.y.values[:, None]
    P = pop["population"].values.astype(float)

    d_ag = np.hypot(ox_ - ag.geometry.x.values, oy_ - ag.geometry.y.values)
    u_ag = _utility(d_ag)
    is_cli = ag["est_client"].values
    u_all = u_ag.sum(axis=1)
    u_cli = u_ag[:, is_cli].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        p_cli_before = np.where(u_all > 0, u_cli / u_all, 0.0)

    cand = scores[scores["candidat_huff"]].copy()
    centres = cand.geometry.centroid
    rows, flux = [], []
    for (_, r), c in zip(cand.iterrows(), centres):
        d_new = np.hypot(origins.x.values - c.x, origins.y.values - c.y)
        u_new = _utility(d_new)
        denom = u_all + u_new
        with np.errstate(invalid="ignore", divide="ignore"):
            p_new = np.where(denom > 0, u_new / denom, 0.0)
            p_cli_after = np.where(denom > 0, u_cli / denom, 0.0)
        captes = P * p_new
        cannib = P * (p_cli_before - p_cli_after)
        zone = d_new <= config.HUFF_DIST_MAX_M
        rows.append({
            "h3": r["h3"], "arrondissement": r["arrondissement"],
            "rang_score": int(r["rang"]),
            "score_100": r["score_100"],
            "clients_captes": int(captes.sum()),
            "cannibalisation_client": int(cannib.sum()),
            "gain_net_client": int(captes.sum() - cannib.sum()),
            "part_captee_zone_5km_pct": round(100 * captes[zone].sum() / P[zone].sum(), 2),
            "part_client_avant_pct": round(100 * (P * p_cli_before)[zone].sum() / P[zone].sum(), 2),
            "part_client_apres_pct": round(100 * (P * (p_cli_after + p_new))[zone].sum() / P[zone].sum(), 2),
        })
        keep = captes >= 1
        flux.append(pd.DataFrame({"h3_candidat": r["h3"], "h3_origine": pop["h3"].values[keep],
                                  "lat_origine": latlng[keep, 0].round(6), "lon_origine": latlng[keep, 1].round(6),
                                  "distance_m": d_new[keep].round(), "population": P[keep].astype(int),
                                  "probabilite": p_new[keep].round(4),
                                  "clients_captes": captes[keep].round(1)}))

    res = pd.DataFrame(rows).sort_values("gain_net_client", ascending=False).reset_index(drop=True)
    res["rang_huff"] = range(1, len(res) + 1)

    # Sélection finale : meilleur gain net, avec espacement minimal entre agences
    xy = dict(zip(cand["h3"], zip(centres.x, centres.y)))
    recos = []
    for h in res["h3"]:
        if all(np.hypot(xy[h][0] - xy[o][0], xy[h][1] - xy[o][1]) >= config.DISTANCE_MIN_ENTRE_RECOS_M
               for o in recos):
            recos.append(h)
        if len(recos) == config.N_RECOMMANDATIONS:
            break
    rang_reco = {h: i + 1 for i, h in enumerate(recos)}
    res["recommande"] = res["h3"].isin(recos)
    res["rang_recommandation"] = res["h3"].map(rang_reco).astype("Int64")
    res.to_csv(config.SILVER / "huff_candidats.csv", index=False)
    pd.concat(flux).to_csv(config.SILVER / "huff_flux.csv", index=False)

    # Portefeuille : les 3 agences ouvertes ensemble se prennent aussi des clients entre elles,
    # donc le gain réel est inférieur à la somme des gains calculés site par site.
    u_new = sum(_utility(np.hypot(origins.x.values - xy[h][0], origins.y.values - xy[h][1])) for h in recos)
    denom = u_all + u_new
    with np.errstate(invalid="ignore", divide="ignore"):
        capt = (P * np.where(denom > 0, u_new / denom, 0.0)).sum()
        cli_apres = np.where(denom > 0, u_cli / denom, 0.0)
    cannib = (P * (p_cli_before - cli_apres)).sum()
    somme = int(res.loc[res["recommande"], "gain_net_client"].sum())
    portefeuille = {"clients_captes": int(capt), "cannibalisation_client": int(cannib),
                    "gain_net_portefeuille": int(capt - cannib), "somme_gains_individuels": somme,
                    "recouvrement_pct": round(100 * (somme - (capt - cannib)) / somme, 1)}
    (config.SILVER / "huff_portefeuille.json").write_text(json.dumps(portefeuille, indent=2), encoding="utf-8")
    log.info("Portefeuille des %d agences : gain net %s (somme des gains isolés %s, recouvrement %s %%)",
             len(recos), portefeuille["gain_net_portefeuille"], somme, portefeuille["recouvrement_pct"])

    scores["recommande"] = scores["h3"].isin(recos)
    scores["rang_recommandation"] = scores["h3"].map(rang_reco).astype("Int64")
    write(scores, config.SILVER / "scores_h3.gpkg")
    robustesse(scores, recos).to_csv(config.SILVER / "robustesse_scenarios.csv", index=False)

    for _, r in res[res["recommande"]].sort_values("rang_recommandation").iterrows():
        log.info("Reco %d : %s (%s, rang score %d) — %s captés, %s cannibalisés, gain net %s",
                 r["rang_recommandation"], r["h3"], r["arrondissement"], r["rang_score"],
                 r["clients_captes"], r["cannibalisation_client"], r["gain_net_client"])
