# 2. Méthodologie

Chaque choix est justifié ici pour pouvoir être défendu face à un jury ou à un client.

## 2.1 Systèmes de coordonnées

OSM et Kontur arrivent en degrés (WGS84, EPSG:4326 ; Kontur en EPSG:3857). **Tous les calculs de distance se font en EPSG:26191 (Merchich / Nord Maroc), en mètres.** On ne revient en WGS84 que pour l'export vers Power BI. Un buffer de « 1 » en WGS84 ferait environ 100 km, pas 1 km.

## 2.2 Pourquoi des hexagones H3

- **Le MAUP** (*Modifiable Areal Unit Problem*) : les résultats changent selon le découpage. Les 16 arrondissements vont de 3,1 km² (Ben M'Sick) à 40,7 km² (Hay Hassani), ce qui rend les comparaisons trompeuses.
- **La granularité** : « ouvrez à Sidi Moumen » ne suffit pas, le client veut une adresse. Un hexagone de résolution 8 fait environ 0,74 km².
- **Le voisinage** : les 6 voisins d'un hexagone sont tous à la même distance de son centre, ce qui en fait une bonne zone de chalandise (`h3.grid_disk(cellule, 1)`).
- **La cohérence** : Kontur publie sa population directement en H3 résolution 8, donc aucune ré-agrégation n'est nécessaire.

La commune est couverte par **273 hexagones**.

## 2.3 Population : Kontur calé sur le recensement

Kontur Population (novembre 2023) estime la population par hexagone à partir de l'imagerie du bâti. La référence est le **fichier Excel officiel du HCP** (« Population légale du Royaume du Maroc », RGPH 2024), qui donne la population des 16 arrondissements. Une copie est conservée dans `data/reference/`.

| Contrôle | Résultat |
|---|---|
| Total commune, Kontur vs RGPH 2024 | 3 162 620 contre 3 215 935 → **−1,7 %** ✅ |
| Répartition par arrondissement | de **−68,6 %** (Al Fida) à **+125,4 %** (Maârif) ❌ |
| Plafond du modèle | 30 hexagones bloqués à ~36 900 habitants ❌ |

Kontur est donc juste au total, mais sa répartition entre quartiers est faussée : il sous-estime les tissus anciens et denses (Al Fida, Mers Sultan, Sidi Belyout) et surestime Maârif et Sidi Moumen.

**Correction par calage.** Pour chaque arrondissement *a* :

```
population_calée(h ∩ a) = population_kontur(h) × part_surface(h, a) × RGPH_2024(a) / Kontur(a)
```

Un hexagone à cheval sur deux arrondissements est coupé en morceaux au prorata de sa surface, et chaque morceau reçoit le facteur de son arrondissement. Les facteurs vont de 0,44 (Maârif) à 3,19 (Al Fida). Après calage, **les 16 arrondissements retombent exactement sur le chiffre officiel**, et le total vaut 3 215 935 habitants. Les colonnes `population_kontur` et `population` sont toutes deux conservées pour la traçabilité. Pour désactiver le calage : `CALAGE_HCP = False`.

## 2.4 Indicateurs

| Famille | Indicateur brut | Calcul |
|---|---|---|
| Demande | `pop_k1` | Somme de la population de l'hexagone et de ses 6 voisins, y compris ceux hors commune |
| Concurrence | `n_concurrents_1km` | Agences non-CIH à moins de 1 000 m du centre de l'hexagone |
| | `dist_concurrent_m`, `hab_par_agence_1km` | Indicateurs de lecture, non utilisés dans le score |
| Accessibilité | `dist_transport_m` | Distance à l'arrêt de tram, de busway ou à la gare le plus proche. Les ~1 400 arrêts de bus classiques sont exclus : ils couvrent toute la ville et ne discriminent pas les zones |
| | `dist_axe_m` | Distance à l'axe le plus proche (autoroute, voie rapide, primaire) |
| Attractivité | `attractivite_brute_k1` | Somme pondérée des POI sur l'hexagone et ses voisins : commerce ×1, restauration ×0,5, bureau ×2, santé ×1, enseignement supérieur ×3, centre commercial ×10 |

## 2.5 Normalisation

On utilise un min-max robuste : on écrête aux centiles 1 et 99, puis on ramène sur [0, 1]. Sans écrêtage, un seul hexagone extrême du centre-ville (83 agences à moins de 1 km) écraserait toute l'échelle.

```
x_norm = (clip(x, P1, P99) − P1) / (P99 − P1)
```

- **Accessibilité** = 0,6 × (1 − dist_transport_norm) + 0,4 × (1 − dist_axe_norm)
- **Attractivité** : on normalise `log(1 + x)`, car la distribution est très asymétrique (médiane 58, maximum 924).

## 2.6 Score multicritère (MCDA)

```
Score = 0,35 × Demande + 0,25 × (1 − Concurrence) + 0,20 × Accessibilité + 0,20 × Attractivité
```

**Exclusions** : un hexagone n'est pas classé si une agence CIH existe à moins de 500 m (36 hexagones), ou si sa zone de chalandise compte moins de 2 000 habitants (3 hexagones).

**Justification des poids.** La demande pèse le plus lourd, car c'est elle qui fait le chiffre d'affaires. La concurrence vient ensuite, car une banque de taille moyenne ne gagne pas un combat frontal contre les leaders. Ces poids sont un **choix business** : le simulateur Power BI permet au client de les modifier. Pour les dériver de façon formelle, on peut utiliser la méthode AHP (comparaisons par paires entre critères).

## 2.7 L'entonnoir : le score présélectionne, Huff décide

Le score seul laisse passer de mauvais sites. Par exemple, l'hexagone classé 6ᵉ à Aïn-Chock a 17 concurrents à moins de 1 km et ne capterait que 7 000 habitants. On procède donc en deux étages :

1. **Présélection** : les 12 meilleurs hexagones par le score, espacés d'au moins 1,5 km.
2. **Décision** : pour chaque candidat, le modèle de Huff calcule le **gain net** de clientèle. On retient les 3 meilleurs gains nets, espacés d'au moins 2,5 km.
3. **Portefeuille** : on recalcule Huff avec les 3 agences ouvertes **ensemble**, puisqu'elles se prennent aussi des clients entre elles. Le gain net du portefeuille est de 74 265 habitants, contre 75 800 en additionnant les calculs site par site, soit un recouvrement de 2 %. L'espacement de 2,5 km suffit donc.

### Modèle de Huff

```
P(i → j) = (A_j / d_ij^λ) / Σ_k (A_k / d_ik^λ)          λ = 2, A = 1
```

- *i* = 361 hexagones d'origine (commune + un anneau extérieur), *j* = 738 agences + le site candidat.
- Plancher de distance à 250 m, pour ne pas diviser par ~0 à l'intérieur d'un hexagone. Plafond à 5 km : au-delà, une agence ne fait plus partie des choix du client.
- **Clients captés** = Σᵢ popᵢ × P(i → nouvelle agence)
- **Cannibalisation** = ce que les agences CIH existantes perdent : Σᵢ popᵢ × [P_CIH_avant(i) − P_CIH_après(i)]
- **Gain net** = captés − cannibalisation

**Limites de Huff.** Toutes les agences sont supposées aussi attractives (A = 1). Le modèle ignore la fidélité bancaire, et il compte des habitants et non des clients bancarisés. Il faut donc lire les résultats comme un **classement relatif** entre sites, pas comme une prévision de comptes ouverts.

## 2.8 Robustesse

On recalcule le rang des 3 zones recommandées sous 4 autres jeux de poids : offensif, prudent, flux, poids égaux ([robustesse_scenarios.csv](../data/gold/robustesse_scenarios.csv)).

| Zone | Réf. | Offensif | Prudent | Flux | Égaux |
|---|---|---|---|---|---|
| Moulay Rachid, Hay El Falah (#3) | 1 | 1 | 1 | 1 | 1 |
| Sidi Moumen, Hôpital (#2) | 15 | 16 | 12 | 27 | 18 |
| Sidi Moumen, Terminus (#1) | 21 | 18 | 17 | 62 | 35 |

**Lecture.**
- Moulay Rachid est n°1 du score quelle que soit la pondération : c'est le choix le plus sûr.
- Les deux sites de Sidi Moumen ne sont pas les mieux notés sur le papier. Ils ressortent grâce à l'étage Huff : très peu de concurrents directs, donc un gros gain net. Si le client privilégie les zones de flux (bureaux, commerces), ils reculent nettement.
- À l'échelle de la ville, le résultat est très stable : le top 10 reste dans l'est (Moulay Rachid, Sidi Othmane) sous tous les scénarios. Il faut ramener le poids de la demande à 0 pour que Sidi Belyout et Maârif y entrent.

C'est un arbitrage à présenter explicitement au comité de direction : conquérir des zones sous-servies, ou suivre les flux d'affaires ?
