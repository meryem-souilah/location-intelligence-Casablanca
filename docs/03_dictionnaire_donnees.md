# 3. Dictionnaire de données

**Propriétaires** : *Data owner* = directeur du développement réseau (client). *Data steward* = consultant data, responsable du pipeline et des règles de qualité.
**Coordonnées** : WGS84 (EPSG:4326) dans toutes les tables Gold ; EPSG:26191 dans la couche Silver.

## Fait_Hexagones — `data/gold/fait_hexagones.csv` (1 ligne par hexagone, 273 lignes)

| Champ | Type | Unité | Définition | Source / calcul |
|---|---|---|---|---|
| `h3` | texte | — | Identifiant H3 résolution 8 (**clé primaire**) | `h3.geo_to_cells` |
| `lat`, `lon` | décimal | degrés | Centre de l'hexagone | `h3.cell_to_latlng` |
| `wkt` | texte | — | Contour de l'hexagone au format WKT (Icon Map, Azure Maps) | Shapely |
| `arrondissement` | texte | — | Arrondissement contenant le centre (**clé vers Dim_Arrondissement**) | OSM admin_level=10 |
| `population_kontur` | entier | habitants | Population Kontur brute | Kontur 2023-11 |
| `population` | entier | habitants | Population calée sur le RGPH 2024 par arrondissement (pondération surfacique) | Kontur × facteur HCP de l'arrondissement |
| `pop_k1` | entier | habitants | Population de l'hexagone + 6 voisins (zone de chalandise ~1 km) | `grid_disk(k=1)` |
| `n_concurrents_1km` | entier | agences | Agences non-client à < 1 000 m du centre | OSM amenity=bank |
| `n_agences_client_1km` | entier | agences | Agences du client à < 1 000 m | OSM, marque harmonisée |
| `dist_concurrent_m` | décimal | m | Distance à l'agence concurrente la plus proche | EPSG:26191 |
| `dist_agence_client_m` | décimal | m | Distance à l'agence client la plus proche | EPSG:26191 |
| `hab_par_agence_1km` | décimal | hab./agence | `pop_k1` ÷ agences à 1 km (vide si aucune agence) | Calcul |
| `dist_transport_m` | décimal | m | Distance au tram / busway / gare le plus proche | OSM railway, network |
| `mode_transport_proche` | texte | — | tramway, busway ou train | OSM |
| `station_proche` | texte | — | Station nommée (en caractères latins) la plus proche : le repère pour le client | OSM name |
| `dist_axe_m` | décimal | m | Distance à l'axe principal le plus proche | OSM highway |
| `axe_proche` | texte | — | Nom de la voie nommée la plus proche (pour situer l'hexagone) | OSM name |
| `n_commerce` … `n_centre_commercial` | entier | POI | Nombre de POI par catégorie **dans** l'hexagone | OSM shop/office/amenity |
| `attractivite_brute_k1` | décimal | points | Somme pondérée des POI sur l'hexagone + voisins | Poids dans `config.POIDS_POI` |
| `demande_norm` | décimal | 0-1 | `pop_k1` normalisée (min-max P1-P99) | Calcul |
| `concurrence_norm` | décimal | 0-1 | `n_concurrents_1km` normalisé | Calcul |
| `accessibilite_norm` | décimal | 0-1 | 0,6 × (1 − dist. transport norm.) + 0,4 × (1 − dist. axe norm.) | Calcul |
| `attractivite_norm` | décimal | 0-1 | `log(1 + attractivite_brute_k1)` normalisé | Calcul |
| `exclu` | booléen | — | Hexagone non classable | Règles d'exclusion |
| `motif_exclusion` | texte | — | Agence client à < 500 m, ou zone < 2 000 habitants | Calcul |
| `score` / `score_100` | décimal | 0-1 / 0-100 | Score multicritère (pondérations de référence) | `scoring.py` |
| `rang` | entier | — | Rang du score (1 = meilleur), vide si exclu | Calcul |
| `candidat_huff` | booléen | — | Présélectionné pour le modèle de Huff | Top 12 espacés de 1,5 km |
| `recommande` / `rang_recommandation` | booléen / entier | — | Zone retenue (1 à 3) | Huff + espacement de 2,5 km |
| `clients_captes` | entier | habitants | Clientèle captée par une agence au centre de l'hexagone | Huff (candidats seulement) |
| `cannibalisation_client` | entier | habitants | Clientèle perdue par les agences client existantes | Huff |
| `gain_net_client` | entier | habitants | `clients_captes − cannibalisation_client` | Huff |
| `rang_huff` | entier | — | Rang du gain net parmi les candidats | Huff |

## Dim_Agences — `dim_agences.csv` (787 lignes : 738 agences + 49 GAB)

| Champ | Type | Définition |
|---|---|---|
| `osm_id` | texte | Identifiant OSM (`n` = nœud, `w` = way) + numéro, **clé primaire** |
| `type` | texte | `agence` ou `gab` |
| `marque` | texte | Marque canonique issue du référentiel ([brands.py](../locintel/brands.py)) |
| `est_client` | booléen | Marque = `CLIENT_BRAND` |
| `name`, `brand`, `operator` | texte | Libellés OSM d'origine, conservés pour l'audit |
| `marque_osm_renseignee` | booléen | Le tag OSM `brand` était présent |
| `arrondissement` | texte | Arrondissement (jointure spatiale) |
| `derniere_modif_osm` | date | Date de la dernière modification de l'objet dans OSM (règle Q16) |
| `version_osm` | entier | Nombre de versions de l'objet dans OSM |
| `lat`, `lon` | décimal | Position |

## Dim_Arrondissement — `dim_arrondissements.csv` (16 lignes)

`arrondissement` (clé), `superficie_km2`, `hexagones`, `population` (calée, égale au RGPH 2024), `agences_client`, `agences_concurrentes`, `agences_total`, `hab_par_agence`, `agences_pour_10k_hab`, `part_client_pct`, `score_moyen_100`, `zones_recommandees`.

## Dim_Marque — `dim_marques.csv` (18 lignes)

`marque` (clé), `agences`, `part_agences_pct`, `est_client`.

## Tables d'analyse

| Table | Grain | Contenu |
|---|---|---|
| `recommandations.csv` | 1 ligne / zone recommandée | Fiche complète des 3 zones |
| `huff_candidats.csv` | 1 ligne / candidat | Captés, cannibalisation, gain net, part de marché client avant/après dans un rayon de 5 km |
| `huff_flux.csv` | candidat × hexagone d'origine | Probabilité de choix et clients captés par origine (carte des flux) |
| `huff_portefeuille.csv` | 1 ligne / indicateur | Les 3 agences ouvertes ensemble : captés, cannibalisation, gain net, recouvrement |
| `robustesse_scenarios.csv` | scénario × zone | Rang de chaque zone recommandée sous 5 pondérations |

## Tables qualité

| Table | Contenu |
|---|---|
| `qualite_regles.csv` | 16 règles : id, dimension, valeur, seuil, statut, commentaire |
| `qualite_calage_hcp.csv` | Kontur vs RGPH 2024 par arrondissement, facteur de calage |
| `qualite_arrondissements.csv` | Complétude des marques par arrondissement |
| `verification_terrain.csv` | 30 agences tirées au hasard à vérifier (liens OSM et Google Maps, date de dernière modification) |

## Référence

| Fichier | Contenu |
|---|---|
| `data/reference/hcp_rgph2024_population_legale.xlsx` | Fichier officiel du HCP (population légale 2024), source des 16 chiffres de calage (règle Q15) |
