# 1. Cadrage de la mission

## Le client (fictif)

**CIH Bank**, banque marocaine de taille moyenne : 50 agences dans la commune de Casablanca (6,8 % du parc), contre 156 pour Attijariwafa bank et 131 pour Bank of Africa. La direction du réseau veut **ouvrir 3 nouvelles agences à Casablanca d'ici 2027**.

> La mission est fictive. Le choix de CIH Bank sert uniquement à rendre l'exercice concret, sans aucun lien avec la banque. Pour refaire toute l'analyse pour une autre banque, il suffit de changer `CLIENT_BRAND` dans [locintel/config.py](../locintel/config.py).

## La question business

> **Quelles zones de Casablanca offrent le meilleur potentiel pour une nouvelle agence, compte tenu de la demande, de la concurrence et de l'accessibilité ?**

## Périmètre

| Élément | Choix | Justification |
|---|---|---|
| Territoire | Commune de Casablanca, 16 arrondissements, 216 km² | Territoire de la question du client ; les communes périphériques (Bouskoura, Dar Bouazza) sont hors mandat |
| Unité d'analyse | Hexagone H3, résolution 8 (~0,74 km²) | Maille assez fine pour décider d'une implantation, identique à celle de Kontur |
| Horizon | Situation actuelle (OSM 2026, population Kontur 2023 calée sur le RGPH 2024 par arrondissement) | Pas de projection démographique à ce stade |
| Cible | Agences de détail | Les GAB OSM sont trop incomplets (voir règle Q06) |

## KPI de décision

| KPI | Mesure | Sens |
|---|---|---|
| **Demande** | Habitants dans la zone de chalandise (hexagone + 6 voisins, ~1 km) | ↑ mieux |
| **Concurrence** | Agences concurrentes à moins de 1 km | ↓ mieux |
| **Accessibilité** | Distance au tram/busway/gare et à un axe principal | ↓ mieux |
| **Attractivité économique** | Commerces, bureaux, santé, enseignement supérieur, centres commerciaux | ↑ mieux |
| **Clientèle captable** (Huff) | Habitants captés par la nouvelle agence, moins la cannibalisation des agences CIH existantes | ↑ mieux |

## Contraintes

- Pas d'agence à moins de **500 m** d'une agence CIH existante (anti-cannibalisation).
- Les 3 agences recommandées doivent être espacées d'au moins **2,5 km**.
- Uniquement des **données ouvertes** (OSM, Kontur, HCP).

## Livrables

1. Pipeline Python reproductible (Bronze → Silver → Gold) : [run_pipeline.py](../run_pipeline.py)
2. Tables Gold pour Power BI : [data/gold/](../data/gold/)
3. Dossier de gouvernance : [04_gouvernance.md](04_gouvernance.md) et [03_dictionnaire_donnees.md](03_dictionnaire_donnees.md)
4. Dashboard en 5 pages : version web interactive ([dashboard/index.html](../dashboard/index.html)) et projet Power BI généré ([powerbi/](../powerbi/), guide [05_guide_powerbi.md](05_guide_powerbi.md))
5. Deck de restitution : [06_storytelling.md](06_storytelling.md)

## Planning (5 semaines)

| Semaine | Livrable | État |
|---|---|---|
| 1 | Cadrage, collecte, dictionnaire de données | ✅ pipeline + docs |
| 2 | Nettoyage, maillage H3, indicateurs | ✅ |
| 3 | Scoring, Huff, validation | ✅ scoring, Huff, portefeuille, calage HCP · ⏳ échantillon terrain (Q11) |
| 4 | Dashboard + page qualité | ✅ dashboard web publié · ✅ projet Power BI généré (visuels à placer) |
| 5 | Deck, README, vidéo démo de 3 min | ✅ README · ✅ trame du deck et script vidéo (06) · ⏳ slides et vidéo à produire |
