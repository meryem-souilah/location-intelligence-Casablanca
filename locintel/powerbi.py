"""Étape 9 — Projet Power BI (format PBIP) généré à partir de la couche Gold.

Produit powerbi/Casablanca_Agences.pbip : le modèle sémantique (tables typées,
relations, paramètres What-if, mesures DAX) est prêt ; les pages du rapport sont
créées vides et se remplissent en glissant les champs (voir docs/05).

Le modèle est écrit en TMDL, le format texte de Power BI : il se relit et se
versionne dans Git comme du code.
"""
import json
import re
import shutil

import pandas as pd

from . import config
from .utils import log

NOM = "Casablanca_Agences"
OUT = config.ROOT / "powerbi"

TABLES = {  # nom Power BI -> fichier Gold
    "Fait_Hexagones": "fait_hexagones.csv",
    "Dim_Agences": "dim_agences.csv",
    "Dim_Arrondissement": "dim_arrondissements.csv",
    "Dim_Marque": "dim_marques.csv",
    "Huff_Candidats": "huff_candidats.csv",
    "Huff_Flux": "huff_flux.csv",
    "Robustesse": "robustesse_scenarios.csv",
    "Qualite_Regles": "qualite_regles.csv",
    "Qualite_Calage": "qualite_calage_hcp.csv",
    "Qualite_Arrondissements": "qualite_arrondissements.csv",
}
CATEGORIES = {"lat": "Latitude", "lon": "Longitude", "lat_origine": "Latitude", "lon_origine": "Longitude",
              "arrondissement": "Place"}

RELATIONS = [  # (de, vers, bidirectionnel, un_a_un)
    ("Fait_Hexagones.arrondissement", "Dim_Arrondissement.arrondissement", False, False),
    ("Dim_Agences.arrondissement", "Dim_Arrondissement.arrondissement", False, False),
    ("Dim_Agences.marque", "Dim_Marque.marque", False, False),
    ("Huff_Candidats.h3", "Fait_Hexagones.h3", True, True),
    ("Huff_Flux.h3_candidat", "Huff_Candidats.h3", False, False),
    ("Qualite_Arrondissements.arrondissement", "Dim_Arrondissement.arrondissement", False, False),
]

POIDS = [("Demande", "demande"), ("Concurrence", "concurrence"),
         ("Accessibilite", "accessibilite"), ("Attractivite", "attractivite")]

MESURES = {  # nom -> (expression DAX, format)
    "Total Poids": ("[Valeur Poids Demande] + [Valeur Poids Concurrence] + [Valeur Poids Accessibilite] "
                    "+ [Valeur Poids Attractivite]", "0"),
    "Score Dynamique": ("""VAR wD = [Valeur Poids Demande]
VAR wC = [Valeur Poids Concurrence]
VAR wA = [Valeur Poids Accessibilite]
VAR wT = [Valeur Poids Attractivite]
VAR s =
    DIVIDE (
        wD * AVERAGE ( Fait_Hexagones[demande_norm] )
            + wC * ( 1 - AVERAGE ( Fait_Hexagones[concurrence_norm] ) )
            + wA * AVERAGE ( Fait_Hexagones[accessibilite_norm] )
            + wT * AVERAGE ( Fait_Hexagones[attractivite_norm] ),
        wD + wC + wA + wT
    )
RETURN
    IF ( SELECTEDVALUE ( Fait_Hexagones[exclu] ) = TRUE (), BLANK (), s * 100 )""", "0.0"),
    "Rang Dynamique": ("""IF (
    HASONEVALUE ( Fait_Hexagones[h3] ) && NOT ISBLANK ( [Score Dynamique] ),
    RANKX (
        FILTER ( ALLSELECTED ( Fait_Hexagones[h3] ), NOT ISBLANK ( [Score Dynamique] ) ),
        [Score Dynamique], , DESC, DENSE
    )
)""", "0"),
    "Top 10 Dynamique": ("IF ( [Rang Dynamique] <= 10, 1, 0 )", "0"),
    "Couleur Score": ("""VAR s = [Score Dynamique]
RETURN
    SWITCH ( TRUE (),
        ISBLANK ( s ), "#E1E0D9",
        s >= 80, "#0D366B",
        s >= 70, "#256ABF",
        s >= 60, "#3987E5",
        s >= 50, "#86B6EF",
        "#CDE2FB" )""", None),
    "Message Poids": ("""IF ( [Total Poids] = 0, "Choisissez au moins un poids",
    "Poids appliqués : Demande " & FORMAT ( DIVIDE ( [Valeur Poids Demande], [Total Poids] ), "0%" )
        & " · Concurrence " & FORMAT ( DIVIDE ( [Valeur Poids Concurrence], [Total Poids] ), "0%" )
        & " · Accès " & FORMAT ( DIVIDE ( [Valeur Poids Accessibilite], [Total Poids] ), "0%" )
        & " · Attractivité " & FORMAT ( DIVIDE ( [Valeur Poids Attractivite], [Total Poids] ), "0%" ) )""", None),
    "Population Totale": ("SUM ( Dim_Arrondissement[population] )", "#,0"),
    "Nb Agences": ('CALCULATE ( COUNTROWS ( Dim_Agences ), Dim_Agences[type] = "agence" )', "#,0"),
    "Nb Agences Client": ("CALCULATE ( [Nb Agences], Dim_Agences[est_client] = TRUE () )", "#,0"),
    "Part Agences Client": ("DIVIDE ( [Nb Agences Client], [Nb Agences] )", "0.0%"),
    "Habitants par Agence": ("DIVIDE ( [Population Totale], [Nb Agences] )", "#,0"),
    "Gain Net Recommandations": ("CALCULATE ( SUM ( Fait_Hexagones[gain_net_client] ), "
                                 "Fait_Hexagones[recommande] = TRUE () )", "#,0"),
    "Zones Blanches": ("CALCULATE ( COUNTROWS ( Fait_Hexagones ), Fait_Hexagones[n_concurrents_1km] = 0, "
                       "Fait_Hexagones[pop_k1] >= 50000 )", "0"),
    "Alertes Qualite": ('CALCULATE ( COUNTROWS ( Qualite_Regles ), Qualite_Regles[statut] = "Alerte" )', "0"),
    "Regles Conformes": ('CALCULATE ( COUNTROWS ( Qualite_Regles ), Qualite_Regles[statut] = "Conforme" )', "0"),
}

PAGES = ["Vue exécutive", "Analyse concurrentielle", "Simulateur", "Fiche zone", "Qualité des données"]


def q(name: str) -> str:
    """Nom TMDL : entre apostrophes s'il contient autre chose que [A-Za-z0-9_]."""
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else "'" + name.replace("'", "''") + "'"


def _types(s: pd.Series):
    """(type TMDL, type M) d'une colonne CSV."""
    if s.dtype == bool:
        return "boolean", "type logical"
    if pd.api.types.is_integer_dtype(s):
        return "int64", "Int64.Type"
    if pd.api.types.is_float_dtype(s):
        # entiers stockés en décimal à cause de valeurs vides (rang, gain net...)
        if s.dropna().apply(float.is_integer).all() and not s.name.endswith(("lat", "lon", "_norm")):
            return "int64", "Int64.Type"
        return "double", "type number"
    return "string", "type text"


def _indent(text: str, n: int) -> str:
    return "\n".join("\t" * n + line for line in text.splitlines())


def _table(name: str, csv: str, df: pd.DataFrame, mesures: dict | None = None) -> str:
    lines = [f"table {q(name)}", ""]
    types_m = []
    for col in df.columns:
        t, m = _types(df[col])
        types_m.append(f'{{"{col}", {m}}}')
        lines += [f"\tcolumn {q(col)}", f"\t\tdataType: {t}"]
        if t in ("int64", "double"):
            lines.append("\t\tsummarizeBy: " + ("none" if col in CATEGORIES or "rang" in col else "sum"))
        else:
            lines.append("\t\tsummarizeBy: none")
        if col in CATEGORIES:
            lines.append(f"\t\tdataCategory: {CATEGORIES[col]}")
        if col == "wkt":
            lines.append("\t\tisHidden")
        lines += [f"\t\tsourceColumn: {col}", ""]
    for m_name, (expr, fmt) in (mesures or {}).items():
        lines.append(f"\tmeasure {q(m_name)} =")
        lines.append(_indent(expr, 3))
        if fmt:
            lines.append(f'\t\tformatString: {fmt}')
        lines.append("")
    m = f"""let
    Source = Csv.Document(File.Contents(DossierGold & "{csv}"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    EnTetes = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Types = Table.TransformColumnTypes(EnTetes, {{{", ".join(types_m)}}}, "en-US")
in
    Types"""
    lines += [f"\tpartition {q(name)} = m", "\t\tmode: import", "\t\tsource =", _indent(m, 4), ""]
    return "\n".join(lines)


def _poids_table(label: str, cle: str) -> str:
    nom = f"Poids {label}"
    defaut = int(round(config.POIDS_SCORE[cle] * 100))
    return f"""table {q(nom)}

\tcolumn {q(nom)}
\t\tdataType: int64
\t\tformatString: 0
\t\tsummarizeBy: none
\t\tisNameInferred
\t\tsourceColumn: [Value]

\tmeasure {q("Valeur " + nom)} = SELECTEDVALUE ( {q(nom)}[{nom}], {defaut} )
\t\tformatString: 0

\tpartition {q(nom)} = calculated
\t\tmode: import
\t\tsource = GENERATESERIES ( 0, 100, 5 )
"""


def run():
    if OUT.exists():
        shutil.rmtree(OUT)
    sm = OUT / f"{NOM}.SemanticModel"
    rp = OUT / f"{NOM}.Report"
    (sm / "definition" / "tables").mkdir(parents=True)
    rp.mkdir(parents=True)

    def w(path, text):
        path.write_text(text, encoding="utf-8")

    w(OUT / f"{NOM}.pbip", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NOM}.Report"}}],
        "settings": {"enableAutoRecovery": True}}, indent=2))
    w(sm / "definition.pbism", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "settings": {}}, indent=2))
    w(rp / "definition.pbir", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NOM}.SemanticModel"}}}, indent=2))

    d = sm / "definition"
    w(d / "database.tmdl", "database\n\tcompatibilityLevel: 1567\n")
    noms = list(TABLES) + [f"Poids {p}" for p, _ in POIDS]
    w(d / "model.tmdl", "model Model\n\tculture: fr-FR\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
                        "\tsourceQueryCulture: fr-FR\n\n" + "\n".join(f"ref table {q(t)}" for t in noms) + "\n")
    dossier = str(config.GOLD).rstrip("\\/") + "\\"
    w(d / "expressions.tmdl",
      f'expression DossierGold = "{dossier}" meta [IsParameterQuery = true, Type = "Text", '
      f'IsParameterQueryRequired = true]\n\tannotation PBI_ResultType = Text\n')

    rel = []
    for i, (a, b, bidir, un) in enumerate(RELATIONS, 1):
        rel += [f"relationship rel_{i:02d}", f"\tfromColumn: {a}", f"\ttoColumn: {b}"]
        if un:
            rel += ["\tfromCardinality: one", "\ttoCardinality: one"]
        if bidir:
            rel.append("\tcrossFilteringBehavior: bothDirections")
        rel.append("")
    w(d / "relationships.tmdl", "\n".join(rel))

    for name, csv in TABLES.items():
        df = pd.read_csv(config.GOLD / csv)
        w(d / "tables" / f"{name}.tmdl", _table(name, csv, df, MESURES if name == "Fait_Hexagones" else None))
    for label, cle in POIDS:
        w(d / "tables" / f"Poids {label}.tmdl", _poids_table(label, cle))

    sections = [{"name": f"Page{i}", "displayName": p, "displayOption": 1, "width": 1280, "height": 720,
                 "config": "{}", "filters": "[]", "visualContainers": []} for i, p in enumerate(PAGES, 1)]
    w(rp / "report.json", json.dumps({"config": json.dumps({"version": "5.43", "activeSectionIndex": 0}),
                                      "layoutOptimization": 0, "sections": sections}, indent=2, ensure_ascii=False))
    w(OUT / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    log.info("Projet Power BI : powerbi/%s.pbip (%d tables, %d mesures, %d relations)",
             NOM, len(noms), len(MESURES) + len(POIDS), len(RELATIONS))
