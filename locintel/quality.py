"""Étape 6 — Règles de qualité des données (Data Governance).

Chaque règle a un identifiant stable (Q01...), une dimension de qualité, une
valeur mesurée, un seuil et un statut. La table alimente la page « Qualité des
données » du dashboard.
"""
import json
from datetime import datetime

import pandas as pd

from . import config
from .brands import NON_IDENTIFIEE
from .export import population_par_arrondissement
from .utils import log, read


def _statut(ok: bool | None) -> str:
    return "Info" if ok is None else ("Conforme" if ok else "Alerte")


def _controle_hcp():
    """Rapproche les 16 chiffres de config.py du fichier Excel officiel du HCP."""
    try:
        x = pd.read_excel(config.HCP_FICHIER, header=None).iloc[:, [0, 3]].dropna()
    except Exception as e:  # fichier absent ou openpyxl non installé
        return "Non vérifié", "16 / 16", None, f"Fichier HCP illisible : {e}"
    x.columns = ["libelle", "population"]
    x = x[x["libelle"].astype(str).str.startswith("Arrondissement")]
    ok, ecarts = 0, []
    for nom, val in config.HCP_POP_ARRONDISSEMENTS_2024.items():
        lib = config.LIBELLE_HCP.get(nom, nom)
        row = x[x["libelle"].str.contains(lib, regex=False)]
        if len(row) == 1 and int(row["population"].iloc[0]) == val:
            ok += 1
        else:
            ecarts.append(nom)
    n = len(config.HCP_POP_ARRONDISSEMENTS_2024)
    return (f"{ok} / {n}", f"{n} / {n}", ok == n,
            "Source : " + config.HCP_FICHIER.name + (f" ; écarts : {', '.join(ecarts)}" if ecarts else ""))


def _fraicheur(ag: pd.DataFrame):
    t = pd.to_datetime(ag["derniere_modif_osm"], utc=True, errors="coerce")
    if t.isna().all():
        return "Non vérifié", "≥ 80 %", None, "Métadonnées OSM indisponibles lors de l'extraction."
    age = (pd.Timestamp.now(tz="UTC") - t).dt.days / 365.25
    pct = round(100 * (age < config.FRAICHEUR_MAX_ANS).mean(), 1)
    annee = int(t.dt.year.value_counts().idxmax())
    return (f"{pct} %", "≥ 80 %", pct >= 80,
            f"Pic de modifications en {annee} ({(t.dt.year == annee).sum()} agences) : probablement une mise à "
            "jour de masse des marques, pas une vérification terrain. Une date récente ne prouve donc pas "
            "que l'agence existe : seul le contrôle Q11 le fait.")


def run():
    s = json.loads((config.SILVER / "_stats_nettoyage.json").read_text(encoding="utf-8"))
    meta = json.loads((config.BRONZE / "_metadata.json").read_text(encoding="utf-8"))
    a, p = s["agences"], s["population"]
    ag = read(config.SILVER / "agences.gpkg")
    ag = ag[ag["type"] == "agence"]
    scores = read(config.SILVER / "scores_h3.gpkg")

    pct = lambda n, d: round(100 * n / d, 1) if d else 0.0
    brand_ok = pct(a["agences_brutes"] - a["agences_sans_tag_brand"], a["agences_brutes"])
    ident = pct(a["agences_retenues"] - a["agences_non_identifiees"], a["agences_retenues"])
    dup = pct(a["doublons_supprimes"], a["agences_brutes"])
    gab_ratio = round(a["gab_bruts"] / max(a["agences_brutes"], 1), 2)
    hors = int((ag["arrondissement"] == "Hors arrondissement").sum())
    age_kontur = (datetime.now() - datetime.fromisoformat(config.KONTUR_DATE)).days // 30

    regles = [
        ("Q01", "Complétude", "Agences OSM portant un tag brand", f"{brand_ok} %", "≥ 80 %", brand_ok >= 80,
         "Sans tag brand, la marque doit être déduite du nom : source d'erreur."),
        ("Q02", "Complétude", "Agences rattachées à une marque après harmonisation", f"{ident} %", "≥ 95 %", ident >= 95,
         f"{a['agences_non_identifiees']} agences restent « {NON_IDENTIFIEE} » (comptées comme concurrentes)."),
        ("Q03", "Conformité", "Libellés bruts ramenés au référentiel de marques",
         f"{a['libelles_distincts_avant']} → {a['marques_canoniques']}", "Référentiel unique", None,
         "Voir locintel/brands.py (données de référence)."),
        ("Q04", "Unicité", "Doublons supprimés (même marque à < 40 m)", f"{a['doublons_supprimes']} ({dup} %)", "≤ 5 %",
         dup <= 5, "Souvent un nœud + le contour du bâtiment de la même agence."),
        ("Q05", "Validité", "Objets tagués banque qui n'en sont pas", str(a["non_banques_exclues"]), "Exclus", None,
         "Transfert d'argent, crédit conso, assurance, banque centrale : " + ", ".join(a["exemples_non_banques"][:6])),
        ("Q06", "Complétude", "GAB cartographiés par agence", str(gab_ratio), "≥ 1", gab_ratio >= 1,
         "Les GAB sont très sous-cartographiés dans OSM : ils sont exclus de l'indicateur de concurrence."),
        ("Q07", "Couverture", "Agences hors des 16 arrondissements", str(hors), "0", hors == 0,
         "Agences situées dans la commune mais hors polygone d'arrondissement (Méchouar, bordures)."),
        ("Q08", "Cohérence", "Écart population Kontur vs RGPH 2024 (HCP)",
         f"{p['ecart_kontur_vs_hcp_pct']:+} %", "± 10 %", abs(p["ecart_kontur_vs_hcp_pct"]) <= 10,
         f"Kontur : {p['population_kontur_commune']:,} hab. ; HCP : {p['population_hcp_reference']:,} hab.".replace(",", " ")),
        ("Q13", "Exactitude", "Écart max Kontur vs RGPH 2024 par arrondissement",
         f"{p['ecart_max_arrondissement_pct']} % ({p['arrondissement_ecart_max']})", "± 15 %",
         p["ecart_max_arrondissement_pct"] <= 15,
         "Juste au total, faux dans la répartition : corrigé par calage (voir qualite_calage_hcp.csv)."
         if config.CALAGE_HCP else "Calage désactivé : la demande par quartier est biaisée."),
        ("Q14", "Exactitude", "Hexagones au plafond de Kontur (≥ 36 900 hab.)", str(p["hexagones_au_plafond_kontur"]),
         "0", p["hexagones_au_plafond_kontur"] == 0,
         "Kontur sature dans les quartiers les plus denses : la demande y est sous-estimée et mal départagée."),
        ("Q15", "Conformité", "Chiffres de calage identiques au fichier officiel HCP", *_controle_hcp()),
        ("Q16", "Fraîcheur", f"Agences modifiées dans OSM depuis moins de {config.FRAICHEUR_MAX_ANS} ans",
         *_fraicheur(ag)),
        ("Q09", "Complétude", "Hexagones de la commune sans population", str(p["hexagones_sans_population"]),
         "Info", None, "Port, aéroport d'Anfa, zones industrielles, parcs : normal."),
        ("Q10", "Fraîcheur", "Âge de la population Kontur", f"{age_kontur} mois", "≤ 36 mois", age_kontur <= 36,
         f"Référence {config.KONTUR_DATE}. OSM extrait le {meta['date_extraction_utc'][:10]}."),
        ("Q11", "Exactitude", "Échantillon d'agences vérifié sur le terrain / Google Maps", "À réaliser",
         "≥ 90 % confirmées", None, "Remplir data/gold/verification_terrain.csv (30 agences tirées au hasard)."),
        ("Q12", "Licence", "Attribution OSM (ODbL) et Kontur (CC BY 4.0) affichées", "Oui", "Obligatoire", True,
         "Présente dans le README, chaque carte et data/gold/ATTRIBUTION.txt ; "
         "à reproduire en pied de page de chaque page Power BI."),
    ]
    regles.sort(key=lambda r: r[0])
    q = pd.DataFrame(regles, columns=["id", "dimension", "regle", "valeur", "seuil", "_ok", "commentaire"])
    q["statut"] = q["_ok"].map(_statut)
    q.loc[q["id"] == "Q11", "statut"] = "À faire"
    q = q.drop(columns="_ok")
    q.to_csv(config.GOLD / "qualite_regles.csv", index=False, encoding="utf-8-sig")
    pd.read_csv(config.SILVER / "calage_hcp.csv").to_csv(config.GOLD / "qualite_calage_hcp.csv",
                                                         index=False, encoding="utf-8-sig")

    # Complétude par arrondissement
    pop_arr = population_par_arrondissement()
    g = ag.groupby("arrondissement").agg(
        agences=("osm_id", "count"),
        agences_identifiees=("marque", lambda m: (m != NON_IDENTIFIEE).sum()),
        agences_avec_tag_brand=("marque_osm_renseignee", "sum"))
    g = g.join(pop_arr.rename("population"), how="outer").fillna(0)
    g["pct_identifiees"] = (100 * g["agences_identifiees"] / g["agences"].where(g["agences"] > 0)).round(1)
    g["pct_tag_brand"] = (100 * g["agences_avec_tag_brand"] / g["agences"].where(g["agences"] > 0)).round(1)
    g.reset_index().to_csv(config.GOLD / "qualite_arrondissements.csv", index=False, encoding="utf-8-sig")

    # Échantillon de contrôle terrain (tirage reproductible)
    ech = ag.sample(min(30, len(ag)), random_state=42).to_crs(config.CRS_WGS84)
    pd.DataFrame({
        "osm_id": ech["osm_id"], "marque": ech["marque"], "nom_osm": ech["name"],
        "arrondissement": ech["arrondissement"],
        "derniere_modif_osm": pd.to_datetime(ech["derniere_modif_osm"], errors="coerce").dt.strftime("%Y-%m-%d"),
        "lien_osm": [f"https://www.openstreetmap.org/{ {'n': 'node', 'w': 'way', 'r': 'relation'}[i[0]] }/{i[1:]}"
                     for i in ech["osm_id"]],
        "lat": ech.geometry.y.round(6), "lon": ech.geometry.x.round(6),
        "lien_google_maps": [f"https://www.google.com/maps?q={y:.6f},{x:.6f}" for x, y in
                             zip(ech.geometry.x, ech.geometry.y)],
        "existe (oui/non)": "", "marque_correcte (oui/non)": "", "commentaire": "",
    }).to_csv(config.GOLD / "verification_terrain.csv", index=False, encoding="utf-8-sig")

    log.info("Qualité : %s", q["statut"].value_counts().to_dict())
