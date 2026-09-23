# 5. Guide de construction du dashboard Power BI

Toutes les tables se trouvent dans `data/gold/`.

## 5.0 Raccourci : ouvrir le projet généré

Le pipeline génère un projet Power BI prêt à l'emploi : [powerbi/Casablanca_Agences.pbip](../powerbi/). Il contient les 10 tables typées, les 6 relations, les 4 curseurs What-if, les 19 mesures ci-dessous et les 5 pages (vides).

1. Installer **Power BI Desktop** (Microsoft Store, gratuit).
2. Double-cliquer sur `Casablanca_Agences.pbip`.
3. Si le dossier du projet a été déplacé : **Transformer les données → Modifier les paramètres → `DossierGold`**, puis indiquer le chemin du dossier `data/gold\`.
4. **Actualiser**, puis construire les visuels de chaque page (section 5.6). Les étapes 5.1 à 5.4 sont déjà faites.

> Le projet est généré en texte (format PBIP / TMDL), sans avoir pu être ouvert dans Power BI Desktop, qui n'était pas installé sur le poste de développement. En cas d'erreur à l'ouverture, les sections 5.1 à 5.4 décrivent exactement le même modèle, à reconstruire à la main (environ une heure).

Sans le projet généré, il faut compter une journée.

## 5.1 Import

**Accueil → Obtenir les données → Texte/CSV.** Choisir l'encodage **65001 : Unicode (UTF-8)**, sinon les accents et l'arabe s'affichent mal.

| Fichier | Nom de la table dans Power BI |
|---|---|
| `fait_hexagones.csv` | `Fait_Hexagones` |
| `dim_agences.csv` | `Dim_Agences` |
| `dim_arrondissements.csv` | `Dim_Arrondissement` |
| `dim_marques.csv` | `Dim_Marque` |
| `huff_candidats.csv` | `Huff_Candidats` |
| `huff_flux.csv` | `Huff_Flux` |
| `robustesse_scenarios.csv` | `Robustesse` |
| `qualite_regles.csv`, `qualite_calage_hcp.csv`, `qualite_arrondissements.csv` | `Qualite_Regles`, `Qualite_Calage`, `Qualite_Arrondissements` |

Dans Power Query, vérifier que `lat`, `lon` et les champs `*_norm` sont en **nombre décimal**, avec les paramètres régionaux « Anglais (États-Unis) » pour ces colonnes (le séparateur décimal du fichier est le point), et que `exclu`, `recommande`, `est_client` sont en **vrai/faux**.

Catégorie de données (onglet Outils de colonne) : `lat` → Latitude, `lon` → Longitude.

## 5.2 Modèle en étoile

```
                 Dim_Marque
                     │ 1
                     │ *
Dim_Arrondissement ─1──*─ Dim_Agences
        │ 1
        │ *
  Fait_Hexagones ─1──1─ Huff_Candidats ─1──*─ Huff_Flux
        (h3)              (h3)            (h3_candidat)
```

| De | Vers | Cardinalité | Filtrage |
|---|---|---|---|
| `Fait_Hexagones[arrondissement]` | `Dim_Arrondissement[arrondissement]` | *:1 | simple |
| `Dim_Agences[arrondissement]` | `Dim_Arrondissement[arrondissement]` | *:1 | simple |
| `Dim_Agences[marque]` | `Dim_Marque[marque]` | *:1 | simple |
| `Huff_Candidats[h3]` | `Fait_Hexagones[h3]` | 1:1 | double sens |
| `Huff_Flux[h3_candidat]` | `Huff_Candidats[h3]` | *:1 | simple |

## 5.3 Paramètres What-if (le simulateur)

**Modélisation → Nouveau paramètre → Plage numérique**, quatre fois :

| Nom | Min | Max | Incrément | Défaut |
|---|---|---|---|---|
| Poids Demande | 0 | 100 | 5 | 35 |
| Poids Concurrence | 0 | 100 | 5 | 25 |
| Poids Accessibilite | 0 | 100 | 5 | 20 |
| Poids Attractivite | 0 | 100 | 5 | 20 |

Power BI crée pour chacun une table, un segment (curseur) et une mesure. Selon la langue de l'interface, la mesure s'appelle `[Valeur Poids Demande]` ou `[Poids Demande Value]` : adaptez les noms ci-dessous.

## 5.4 Mesures DAX

Créez une table vide `_Mesures` (Entrer des données → OK) pour y ranger les mesures.

```dax
Total Poids =
[Valeur Poids Demande] + [Valeur Poids Concurrence]
    + [Valeur Poids Accessibilite] + [Valeur Poids Attractivite]

Score Dynamique =
VAR wD = [Valeur Poids Demande]
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
    -- un hexagone exclu (agence client < 500 m, zone vide) n'a pas de score
    IF ( SELECTEDVALUE ( Fait_Hexagones[exclu] ) = TRUE (), BLANK (), s * 100 )

Rang Dynamique =
IF (
    HASONEVALUE ( Fait_Hexagones[h3] ) && NOT ISBLANK ( [Score Dynamique] ),
    RANKX (
        FILTER ( ALLSELECTED ( Fait_Hexagones[h3] ), NOT ISBLANK ( [Score Dynamique] ) ),
        [Score Dynamique], , DESC, DENSE
    )
)

Top 10 Dynamique = IF ( [Rang Dynamique] <= 10, 1, 0 )

Couleur Score =
VAR s = [Score Dynamique]
RETURN
    SWITCH ( TRUE (),
        ISBLANK ( s ), "#E1E0D9",      -- exclu : gris neutre
        s >= 80, "#0D366B",
        s >= 70, "#256ABF",
        s >= 60, "#3987E5",
        s >= 50, "#86B6EF",
        "#CDE2FB" )

Message Poids =
IF ( [Total Poids] = 0, "Choisissez au moins un poids",
     "Poids normalisés : Demande " & FORMAT ( DIVIDE ( [Valeur Poids Demande], [Total Poids] ), "0%" )
     & " · Concurrence " & FORMAT ( DIVIDE ( [Valeur Poids Concurrence], [Total Poids] ), "0%" )
     & " · Accès " & FORMAT ( DIVIDE ( [Valeur Poids Accessibilite], [Total Poids] ), "0%" )
     & " · Attractivité " & FORMAT ( DIVIDE ( [Valeur Poids Attractivite], [Total Poids] ), "0%" ) )

-- KPI de la vue exécutive
-- une mesure ne peut pas porter le nom d'une colonne de sa table (population) : d'où « Population Totale »
Population Totale = SUM ( Dim_Arrondissement[population] )
Nb Agences = CALCULATE ( COUNTROWS ( Dim_Agences ), Dim_Agences[type] = "agence" )
Nb Agences Client = CALCULATE ( [Nb Agences], Dim_Agences[est_client] = TRUE () )
Part Agences Client = DIVIDE ( [Nb Agences Client], [Nb Agences] )
Habitants par Agence = DIVIDE ( [Population Totale], [Nb Agences] )
Gain Net Recommandations =
CALCULATE ( SUM ( Fait_Hexagones[gain_net_client] ), Fait_Hexagones[recommande] = TRUE () )
Zones Blanches =
CALCULATE ( COUNTROWS ( Fait_Hexagones ),
    Fait_Hexagones[n_concurrents_1km] = 0, Fait_Hexagones[pop_k1] >= 50000 )

-- Page qualité
Alertes Qualite = CALCULATE ( COUNTROWS ( Qualite_Regles ), Qualite_Regles[statut] = "Alerte" )
Regles Conformes = CALCULATE ( COUNTROWS ( Qualite_Regles ), Qualite_Regles[statut] = "Conforme" )
```

**Pourquoi diviser par la somme des poids ?** Le score reste sur une échelle de 0 à 100 même si les curseurs ne totalisent pas exactement 100. La mesure `Message Poids` affiche les poids effectivement appliqués.

## 5.5 La carte

**Option A : Azure Maps (natif, le plus simple).** Latitude = `Fait_Hexagones[lat]`, Longitude = `Fait_Hexagones[lon]`, Taille = `pop_k1`. Couche de bulles → Couleur de remplissage → **fx → Valeur du champ → `[Couleur Score]`**. Ajoutez une seconde couche avec `Dim_Agences`, colorée par `est_client` (orange pour le client, gris pour les concurrents). Quand un curseur bouge, les couleurs se recalculent immédiatement.

**Option B : vrais hexagones.** Le visuel personnalisé **Icon Map** (AppSource) lit directement la colonne `wkt` et accepte la même couleur `[Couleur Score]`. C'est le rendu le plus proche des cartes du README. En alternative, on peut charger `hexagones.geojson` comme **couche de référence** dans Azure Maps, mais la couche est alors statique : elle se colore selon ses propriétés, pas selon les curseurs.

## 5.6 Les pages

**Pied de page obligatoire sur chaque page** : « © contributeurs OpenStreetMap (ODbL) ; population © Kontur (CC BY 4.0) ; HCP RGPH 2024 ».

### Page 1 : Vue exécutive
- Titre-message : *« 3 agences dans la ceinture est : ~74 000 habitants de clientèle nette captable »*
- Cartes KPI : Population (3 215 935), Agences (738), Part CIH (6,8 %), Gain net des 3 agences ouvertes ensemble (74 265, dans `huff_portefeuille.csv`)
- Carte des scores, avec les 3 zones recommandées mises en évidence
- Tableau `Fait_Hexagones` filtré sur `recommande = vrai` : rang, arrondissement, axe proche, pop_k1, concurrents, gain net

### Page 2 : Analyse concurrentielle
- Barres horizontales `Dim_Marque` : agences par marque, CIH en orange, les autres en gris
- Tableau `Dim_Arrondissement` trié par `hab_par_agence` : de 991 (Maârif) à 22 977 (Sidi Moumen)
- Carte des agences par marque
- Carte KPI `[Zones Blanches]` (19 hexagones : ≥ 50 000 habitants dans la zone de chalandise, aucune agence concurrente à 1 km)

### Page 3 : Simulateur
- Les 4 curseurs à gauche, `[Message Poids]` au-dessus
- Carte colorée par `[Couleur Score]`
- Tableau Top 10 : filtre visuel `[Top 10 Dynamique] = 1`, trié par `[Rang Dynamique]`
- Visuel `Robustesse` : matrice scénario × zone, valeur = rang
- **Démo** : avec les poids de référence, les 10 meilleurs hexagones sont presque tous dans l'est (Moulay Rachid, Sidi Othmane). Poussez « Attractivité » à 60 : le top 10 bouge à peine. Il faut descendre « Demande » à 0 pour que Sidi Belyout et Maârif y entrent. Le message : la recommandation ne dépend pas d'un réglage fin des poids.

### Page 4 : Fiche zone (drill-through)
- Champ d'extraction : `Fait_Hexagones[h3]`
- Cartes : arrondissement, axe proche, population, pop_k1, concurrents à 1 km, distance au tram, gain net
- Barres des 4 indicateurs normalisés, la zone comparée à la moyenne de la ville
- Carte `Huff_Flux` : bulles aux coordonnées `lat_origine` / `lon_origine`, taille = `clients_captes`. On voit d'où viendraient les clients.

### Page 5 : Qualité des données
- Tableau `Qualite_Regles` avec une icône conditionnelle sur `statut` (✅ Conforme, ⚠️ Alerte, ℹ️ Info, ⏳ À faire). Ne jamais signaler un statut par la couleur seule.
- Barres groupées `Qualite_Calage` : Kontur vs HCP par arrondissement
- Tableau `Qualite_Arrondissements` : % de marques identifiées
- Date d'extraction OSM et date Kontur

## 5.7 Rafraîchir

```bash
python run_pipeline.py            # extraction OSM fraîche + recalcul complet (~10 min)
python run_pipeline.py --from scoring   # après un changement de poids dans config.py (secondes)
```

Puis, dans Power BI : **Accueil → Actualiser**.
