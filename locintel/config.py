"""Paramètres de la mission : tout ce qu'un consultant voudrait ajuster se trouve ici."""
from pathlib import Path

# --- Chemins (architecture Bronze / Silver / Gold) ---------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BRONZE = DATA / "bronze"   # données brutes, jamais modifiées
SILVER = DATA / "silver"   # données nettoyées, harmonisées, projetées
GOLD = DATA / "gold"       # tables finales prêtes pour Power BI
FIGURES = ROOT / "figures"
CACHE = ROOT / ".cache"

# --- Périmètre --------------------------------------------------------------
PLACE = "Casablanca, Morocco"          # commune de Casablanca (16 arrondissements, ~216 km²)
ARRONDISSEMENT_ADMIN_LEVEL = "10"      # niveau OSM des arrondissements au Maroc

# --- Systèmes de coordonnées ------------------------------------------------
CRS_WGS84 = 4326     # stockage / affichage (Power BI)
CRS_METRIC = 26191   # Merchich / Nord Maroc, en mètres : tous les calculs de distance

# --- Maillage H3 ------------------------------------------------------------
H3_RES = 8           # ~0,74 km² par hexagone, maille native de Kontur Population
K_RING = 1           # zone de chalandise = hexagone + 6 voisins (~1 km de rayon)

# --- Client (mission fictive) -----------------------------------------------
# Banque cliente fictive : une banque de taille moyenne qui veut ouvrir 3 agences.
# Changer la marque ici relance toute l'analyse pour une autre banque.
CLIENT_BRAND = "CIH Bank"
N_RECOMMANDATIONS = 3
DISTANCE_MIN_ENTRE_RECOS_M = 2500   # évite de recommander 3 hexagones voisins
N_CANDIDATS_HUFF = 12              # présélection par le score (étage 1 de l'entonnoir)
DISTANCE_MIN_ENTRE_CANDIDATS_M = 1500

# --- Indicateurs ------------------------------------------------------------
RAYON_CONCURRENCE_M = 1000       # agences concurrentes comptées dans 1 km
RAYON_SATURATION_CLIENT_M = 500  # agence du client à < 500 m => hexagone exclu
POP_MIN_ZONE_K1 = 2000           # zone de chalandise quasi inhabitée => exclue

# Poids des points d'intérêt dans l'indice d'attractivité économique
POIDS_POI = {
    "commerce": 1.0,
    "restauration": 0.5,
    "bureau": 2.0,
    "sante": 1.0,
    "enseignement_sup": 3.0,
    "centre_commercial": 10.0,
}
# Accessibilité = combinaison des deux distances (plus court = mieux)
POIDS_ACCES = {"transport_collectif": 0.6, "axe_principal": 0.4}

# --- Score multicritère (somme = 1) ----------------------------------------
POIDS_SCORE = {
    "demande": 0.35,
    "concurrence": 0.25,     # appliqué à (1 - concurrence)
    "accessibilite": 0.20,
    "attractivite": 0.20,
}

# --- Modèle de Huff ---------------------------------------------------------
HUFF_LAMBDA = 2.0          # sensibilité à la distance
HUFF_DIST_MIN_M = 250      # plancher : évite la division par ~0 à l'intérieur d'un hexagone
HUFF_DIST_MAX_M = 5000     # au-delà, une agence ne fait pas partie du choix du client

# --- Sources ----------------------------------------------------------------
OVERPASS_URLS = [                        # essayés dans l'ordre (le serveur principal sature souvent)
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
FRAICHEUR_MAX_ANS = 3                    # une agence non modifiée depuis 3 ans est « à vérifier »
KONTUR_URL = (
    "https://geodata-eu-central-1-kontur-public.s3.amazonaws.com/"
    "kontur_datasets/kontur_population_MA_20231101.gpkg.gz"
)
KONTUR_DATE = "2023-11-01"

# Référence officielle : HCP, RGPH 2024, « Population légale du Royaume du Maroc »
# (fichier Excel https://www.hcp.ma/file/242341/, copie dans data/reference/).
HCP_POP_CASABLANCA_2024 = 3_215_935    # Commune de Casablanca (hors Méchouar : 2 101 hab.)
HCP_SOURCE = "HCP, Recensement Général de la Population et de l'Habitat 2024 — population légale"
HCP_FICHIER = ROOT / "data" / "reference" / "hcp_rgph2024_population_legale.xlsx"

# Calage de Kontur sur le recensement. Kontur est juste au total (~ -2 %) mais
# se trompe sur la répartition entre quartiers. On conserve sa répartition fine
# à l'intérieur de chaque arrondissement et on force le total de l'arrondissement
# à égaler le RGPH 2024 (pondération surfacique pour les hexagones à cheval).
CALAGE_HCP = True
HCP_POP_ARRONDISSEMENTS_2024 = {
    "Anfa": 66_202, "Maârif": 139_669, "Sidi Belyout": 138_294,
    "Al Fida": 125_933, "Mers Sultan": 98_139,
    "Hay Mohammadi": 104_232, "Roches noires": 104_775, "Aïn Sebaâ": 155_828,
    "Hay Hassani": 537_509, "Aïn-Chock": 374_707,
    "Sidi Bernoussi": 154_919, "Sidi Moumen": 551_443,
    "Ben M'Sick": 105_612, "Sbata": 101_640,
    "Moulay Rachid": 245_139, "Sidi Othmane": 211_894,
}
# Libellé HCP de chaque arrondissement (contrôle de rapprochement avec le fichier officiel)
LIBELLE_HCP = {"Roches noires": "Asoukhour Assawda", "Aïn Sebaâ": "Aïn-Sebaâ", "Al Fida": "Al-Fida", "Mers Sultan": "Mers-Sultan",
               "Hay Mohammadi": "Hay-Mohammadi", "Hay Hassani": "Hay-Hassani", "Ben M'Sick": "Ben-M'sick"}
KONTUR_PLAFOND = 36_900   # valeur à laquelle Kontur sature dans les zones très denses
