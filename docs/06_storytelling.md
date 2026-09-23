# 6. Deck de restitution (trame SCR)

La trame suit la structure Situation → Complication → Résolution (pyramide de Minto). Deux règles : **la conclusion vient en premier**, et **chaque titre de slide est une phrase-message**. Tous les chiffres viennent de `data/gold/`.

---

### Slide 1 : Synthèse (la conclusion d'abord)
**Titre : « Ouvrir les 3 agences dans la ceinture est de Casablanca : ~74 000 habitants de clientèle nette captable »**

- La ceinture est concentre **31 % de la population** de la commune, mais seulement **6 % des agences**.
- Nous recommandons trois zones, toutes à moins de 600 m du tramway : **Sidi Moumen Terminus** et **Hôpital Sidi Moumen** (Bd Mohamed Zefzaf), et **Hay El Falah** à Moulay Rachid (Av. du Commandant Idriss Elharti).
- Commencer par Hay El Falah, n°1 du score quelle que soit la pondération.

---

### Slide 2 : Situation
**Titre : « Casablanca : 3,2 millions d'habitants, 738 agences, un marché dominé par trois banques »**

- 3 215 935 habitants dans la commune (RGPH 2024), 16 arrondissements, 738 agences bancaires de 18 marques.
- Attijariwafa bank, Bank of Africa et Banque Populaire détiennent **52 % des agences**. CIH Bank en compte 50 (6,8 %).
- Visuel : barres des agences par marque, CIH en orange.

---

### Slide 3 : Complication
**Titre : « Les agences sont au centre, les habitants à l'est : 23 fois plus d'habitants par agence à Sidi Moumen qu'au Maârif »**

| | Population | Agences | Habitants par agence |
|---|---|---|---|
| Centre (Sidi Belyout, Maârif, Anfa) | 344 000 (11 %) | 299 (41 %) | 1 150 |
| Ceinture est (Sidi Moumen, Moulay Rachid, Sidi Othmane) | 1 008 000 (31 %) | 47 (6 %) | 21 500 |

- Visuel : [carte_demande_offre.png](../figures/carte_demande_offre.png)
- La tension : les quartiers les plus peuplés sont les moins servis, et un mauvais emplacement immobilise une agence déficitaire pendant des années.

---

### Slide 4 : Approche
**Titre : « Une méthode en entonnoir : 273 zones notées, 12 présélectionnées, 3 retenues »**

1. Casablanca découpée en **273 hexagones** d'environ 0,74 km².
2. Chaque hexagone reçoit un **score** sur 4 critères : demande 35 %, concurrence 25 %, accessibilité 20 %, attractivité 20 %.
3. Les **12 meilleurs** sont soumis au **modèle de Huff**, qui estime la clientèle réellement captée, nette de la cannibalisation des agences CIH existantes.
4. On garde les **3 meilleurs gains nets**, distants d'au moins 2,5 km, puis on vérifie le gain des 3 agences ouvertes ensemble.

- Visuel : [indicateurs.png](../figures/indicateurs.png)

---

### Slide 5 : Résolution, la carte
**Titre : « Trois zones prioritaires dans l'est, toutes à moins de 600 m du tramway »**

- Visuel : [carte_score.png](../figures/carte_score.png)

---

### Slide 6 : Résolution, les chiffres
**Titre : « Ensemble, les 3 agences apportent 74 000 habitants de clientèle nette »**

| | #1 Sidi Moumen Terminus | #2 Hôpital Sidi Moumen | #3 Hay El Falah (Moulay Rachid) |
|---|---|---|---|
| Axe de référence | Bd Mohamed Zefzaf | Bd Mohamed Zefzaf | Av. du Commandant Idriss Elharti |
| Habitants dans ~1 km | 173 578 | 169 914 | 214 942 |
| Concurrents à < 1 km | **3** | 5 | 7 |
| Tram le plus proche | 591 m | 250 m | 113 m |
| Agence CIH la plus proche | 1,1 km | 1,8 km | 1,2 km |
| Clientèle captée (Huff) | 35 224 | 25 444 | 19 653 |
| Cannibalisation CIH | −2 815 | −1 023 | −682 |
| **Gain net (site seul)** | **32 409** | **24 420** | **18 971** |
| Part CIH dans un rayon de 5 km | 6,5 % → 9,8 % | 5,9 % → 7,7 % | 4,6 % → 5,9 % |

- **Portefeuille** (les 3 ouvertes ensemble) : 78 691 captés, −4 426 cannibalisés, **74 265 de gain net**. Les 3 agences ne se prennent que 2 % de clients entre elles.
- Visuel : [huff_candidats.png](../figures/huff_candidats.png)

---

### Slide 7 : Robustesse
**Titre : « Hay El Falah est n°1 sous toutes les hypothèses ; les deux sites de Sidi Moumen dépendent de la stratégie »**

- Hay El Falah (Moulay Rachid) est n°1 du score sous les 5 pondérations testées.
- Les sites de Sidi Moumen sont gagnants si la banque veut conquérir des zones sous-servies : très peu de concurrents, donc le plus gros gain net. Ils reculent (rang 27 et 62) si elle privilégie les zones de flux.
- À l'échelle de la ville, le top 10 reste dans l'est sous tous les scénarios. Il faut annuler le poids de la demande pour que le centre-ville y entre.
- **Décision attendue du comité** : conquête de zones sous-servies, ou présence dans les zones d'affaires ?

---

### Slide 8 : Feuille de route
**Titre : « Une ouverture en trois vagues, en commençant par la zone la plus sûre »**

| Étape | Échéance | Action |
|---|---|---|
| 0 | T+1 mois | Visite terrain des 3 zones, contrôle de l'échantillon d'agences (règle Q11) |
| 1 | T+6 mois | **Hay El Falah (Moulay Rachid)** : n°1 du score dans tous les scénarios, à 113 m du tram |
| 2 | T+12 mois | **Hôpital Sidi Moumen** : 24 000 de gain net, peu de cannibalisation |
| 3 | T+18 mois | **Sidi Moumen Terminus** : plus gros gain (32 000), mais la plus forte cannibalisation (agence CIH à 1,1 km) ; à confirmer avec les résultats des deux premières |

---

### Slide 9 : Qualité des données
**Titre : « Des données ouvertes contrôlées par 16 règles de qualité ; la population recalée sur le recensement officiel »**

- 98 libellés de banques ramenés à 18 marques ; 25 non-banques retirées (WafaCash, Western Union…) ; 10 doublons supprimés.
- La population Kontur est juste au total (−1,7 %), mais fausse par arrondissement (de −69 % à +125 %). **Elle a été calée sur les 16 chiffres officiels du RGPH 2024**, et une règle vérifie la concordance avec le fichier du HCP.
- Les GAB sont trop peu cartographiés (55 pour 767 agences), donc exclus. 73 % des agences ont été modifiées dans OSM depuis moins de 3 ans, surtout par des mises à jour de masse : un contrôle terrain reste nécessaire.

---

### Slide 10 : Limites et prochaines étapes
**Titre : « Pour passer de l'aide à la décision à la décision, trois données internes du client »**

Limites :
- La population reste une estimation à l'intérieur des arrondissements (Kontur 2023, plafonné dans les zones les plus denses).
- Pas de données de revenus : la « demande » compte des habitants, pas des clients bancarisés.
- Huff suppose toutes les agences aussi attractives et ignore la fidélité bancaire.
- La couverture OSM des agences est bonne (84 % avec marque) mais n'a pas été vérifiée sur le terrain.

Prochaines étapes :
1. **Données internes CIH** : adresses de résidence des clients actuels, pour calibrer λ et la zone de chalandise réelle.
2. **Revenus et taux de bancarisation** par quartier (enquêtes HCP), pour pondérer la demande.
3. **Flux piétons** (données mobiles) autour des 3 stations, pour choisir le local exact.

---

## Script de la démo vidéo (3 minutes)

| Temps | À l'écran | À dire |
|---|---|---|
| 0:00 | Onglet Recommandation | « Une banque veut ouvrir 3 agences à Casablanca. Où ? » |
| 0:20 | Onglet Concurrence | « Les agences sont au centre, les habitants à l'est : 23 fois plus d'habitants par agence à Sidi Moumen qu'au Maârif. » |
| 0:50 | Simulateur, poids de référence | « Chaque hexagone reçoit un score sur 4 critères. » |
| 1:10 | Curseur Attractivité à 60, puis Demande à 0 | « Même en changeant les poids, l'est reste en tête : il faut ignorer complètement la population pour que le centre remonte. » |
| 1:50 | Fiche zone Sidi Moumen Terminus, flux Huff | « Le modèle de Huff estime 32 000 habitants de clientèle nette, après cannibalisation. » |
| 2:20 | Onglet Qualité | « Kontur se trompait jusqu'à 125 % par arrondissement : je l'ai recalé sur le recensement officiel. » |
| 2:45 | Onglet Recommandation | « Trois zones, une feuille de route, et les limites dites clairement. » |
