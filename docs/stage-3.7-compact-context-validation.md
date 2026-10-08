# Stage 3.7 — Compact context validation

8 octobre 2026. **GROQ LIVE = NOT RUN. Verdict : NEEDS FIXES.**

## Périmètre et méthode

Aucun changement de production. Prompts V1/V2/V3, provider, moteurs, validation,
runner d’évaluation, contexte compact et SaladScene inchangés. Pas d’évaluation des
42 scénarios ni de nouvelle catégorie. `.env` est absent et GROQ_API_KEY est absente
du shell ; aucun appel réseau Groq n’a été tenté, aucune clé affichée ou enregistrée.

Diagnostic reproductible : `tools/check_compact_context.py`, exclusivement hors
ligne, construit une vraie application FastAPI avec MockProvider scripté. Il passe
par les routes, V3, le compactage et le moteur existants. **Le provider de test ne
lit ni ne comprend le format** : ses sorties sont écrites à l’avance. Aucune réussite
sémantique du modèle réel ne peut être conclue. Les états retournés sont en revanche
réellement produits par le moteur. Les fixtures et leurs actions sont visibles dans
le script, indépendant du runner d’évaluation existant.

Mesures : `o200k_harmony`, contenu texte de chaque message ; réserve locale
`512 + 16 × nombre de messages`. Sortie = JSON complet message/actions scripté,
et non le seul message assistant. Les tokens de raisonnement cachés et les règles
exactes de débit Groq ne sont pas mesurés. La réserve est une convention prudente,
pas un usage facturé. 8 000 TPM est le quota **précédemment observé**, pas une taille
de fenêtre de contexte vérifiée actuellement. Plusieurs requêtes dans la même
minute peuvent dépasser ce quota même si chacune reste sous 8 000.

## Avant / après et conservation du format

Au premier tour A : 33 409 → 19 433 caractères, **11 211 → 5 631 tokens de contenu**,
soit 11 755 → 6 175 avec réserve. Le chiffre historique 11 222 ajoutait seulement
11 tokens de cadrage aux 11 211 tokens de contenu.

Le Stage 3.6 sérialise le JSON sans espaces inutiles, factorise les enums en
`$defs`/`$ref` et représente les 75 produits en colonnes/lignes avec noms bilingues
en sous-tableaux décrits explicitement. Aucun filtrage du menu ni résumé. Les
champs optionnels absents restent absents, distincts de null. Les formes non
représentables reviennent à des objets complets. La validation des réponses reste
celle du contrat original, et non un nouveau parseur permissif.

La reconstruction locale vérifie l’égalité du menu, du schéma développé, des règles,
des prix, des métadonnées, de l’état et de l’autorisation. Un test supplémentaire
vérifie Unicode, texte avec guillemets/retours ligne, langue supplémentaire dans
le nom et distinction champ absent/null. Ces tests prouvent la conservation des
données, **pas leur interprétation par le LLM**.

## A–E et conversation de dix tours

A, B, C sont successifs dans le même repas. D et E sont des questions informatives
dans cette conversation ; leur fixture ne modifie pas la sélection. Les dix tours
produisent 20 messages utilisateur/assistant ; le dixième appel transmet les 18
messages précédents, intégralement. Aucune paire n’est supprimée dans ce parcours.

| Tour | Message utilisateur | Entrée contenu | Entrée + réserve | Sortie scriptée | Contenu entrée + sortie | Avec réserve + sortie | HTTP local | Durée locale ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | Je veux une grande salade avec poulet et tomate. | 5631 | 6175 | 88 | 5719 | 6263 | 200 | 16.491 |
| 2 | Ajoute du maïs. | 5694 | 6270 | 33 | 5727 | 6303 | 200 | 12.204 |
| 3 | Enlève la tomate. | 5729 | 6337 | 34 | 5763 | 6371 | 200 | 11.409 |
| 4 | Je veux une grande salade mais je ne sais pas quelles bases choisir. | 5727 | 6367 | 61 | 5788 | 6428 | 200 | 11.098 |
| 5 | Tu as quoi comme boissons ? | 5744 | 6416 | 37 | 5781 | 6453 | 200 | 10.975 |
| 6 | Écris mon devoir de mathématiques. | 5762 | 6466 | 27 | 5789 | 6493 | 200 | 10.56 |
| 7 | Ajoute de la sauce. | 5786 | 6522 | 15 | 5801 | 6537 | 200 | 10.666 |
| 8 | Revenons à ma composition : passe ma salade en petite taille. | 5806 | 6574 | 37 | 5843 | 6611 | 200 | 11.238 |
| 9 | Enlève le maïs. | 5845 | 6645 | 35 | 5880 | 6680 | 200 | 11.254 |
| 10 | Ajoute de la tomate. | 5836 | 6668 | 36 | 5872 | 6704 | 200 | 11.015 |

Toutes les durées sont celles de TestClient + provider local scripté (une exécution,
non benchmark), **pas une latence Groq**. Pour chaque tour, statut HTTP provider,
durée provider, usage réel et tokens de sortie réels : **N/A, NOT RUN**.

| Cas | Réponse écrite dans la fixture | Actions acceptées / résultat moteur |
| --- | --- | --- |
| A | Je propose une grande salade poulet et tomate, à compléter. | SET_CATEGORY salad, SET_SIZE large, ADD_ITEM salad.ingredient.grilled_chicken et salad.ingredient.tomato ; grande salade, deux ingrédients, 55 MAD |
| B | Je propose le maïs. | ADD_ITEM salad.ingredient.corn ; poulet/tomate/maïs |
| C | Je propose de retirer la tomate. | REMOVE_ITEM salad.ingredient.tomato, avec remove_item_id et révision explicites ; poulet/maïs |
| D | Vous pouvez choisir laitue et roquette comme bases. | RECOMMEND_ITEM salad.base.lettuce et salad.base.arugula ; aucune base sélectionnée automatiquement |
| E | Le menu propose notamment le jus d’orange. | RECOMMEND_ITEM drink.drink.orange ; repas inchangé |

Les IDs de ces fixtures sont validés contre le menu : aucun item inconnu accepté.
Ce constat ne prédit pas l’absence d’invention dans une réponse Groq future. La
fixture E est une recommandation partielle du menu, pas une preuve d’exhaustivité.
Lors de la préparation du diagnostic, un ID de base inexistant dans une première
fixture a été rejeté HTTP 422 ; il a été remplacé par la roquette effectivement
présente. Ce rejet local ne provenait pas de Groq.

Tours 6–7 : refus hors domaine puis clarification de sauce, actions vides. Tour 8 :
retour à la composition et SET_SIZE small, accepté car poulet/maïs tiennent dans
les slots. Tour 9 : retrait autorisé du maïs. Tour 10 : ajout tomate. État final :
**small, poulet grillé + tomate, bases/toppings/sauces vides, 35 MAD, incomplet**.
Aucune confirmation de commande. Les tests vérifient cet état et l’historique exact.

## Seuils d’historique observés localement

La production possède déjà une fenêtre de **40 messages / 16 000 caractères**, avec
suppression des anciennes paires après enregistrement d’un tour. Elle est inchangée.
Aucun trimming ou résumé nouveau n’a été ajouté. Seuls les textes assistant sont
retenus dans l’historique ; les anciennes actions ne sont pas recopiées comme JSON,
et l’état courant est injecté séparément. Cette fenêtre n’est pas un budget tokens.

### Sorties longues répétitives

Fixture synthétique « salade » répété 500 fois (3 500 caractères), message utilisateur
« Bonjour. », actions vides ; ne représente pas une conversation réaliste.

| Tour | Messages historiques envoyés | Caractères historiques | Entrée contenu | Entrée + réserve | Sortie scriptée | Entrée + sortie |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0 | 0 | 5622 | 6166 | 511 | 6133 |
| 2 | 2 | 3508 | 6126 | 6702 | 511 | 6637 |
| 3 | 4 | 7016 | 6630 | 7238 | 511 | 7141 |
| 4 | 6 | 10524 | 7134 | 7774 | 511 | 7645 |
| 5 | 8 | 14032 | 7638 | 8310 | 511 | 8149 |
| 6 | 8 | 14032 | 7638 | 8310 | 511 | 8149 |
| 7 | 8 | 14032 | 7638 | 8310 | 511 | 8149 |
| 8 | 8 | 14032 | 7638 | 8310 | 511 | 8149 |
| 9 | 8 | 14032 | 7638 | 8310 | 511 | 8149 |
| 10 | 8 | 14032 | 7638 | 8310 | 511 | 8149 |

L’entrée brute reste à 7 638 grâce à la fenêtre existante ; elle n’excède pas 8 000
sur ce jeu. Entrée + réserve dépasse au tour 5 ; contenu entrée + sortie atteint
**8 149 au tour 5**. Réserve incluse, entrée + sortie dépasse dès le tour 4 (8 285).
Après le tour 5, les 17 540 caractères cumulés dépassent la fenêtre ; la première
paire est retirée, ce qui explique le plateau à partir du tour 6. Cette perte de
contexte existante est explicitement signalée, pas interprétée comme une solution.

### Historique dense en tokens

Fixture volontairement adversariale « é! » répété 1 000 fois (3 000 caractères),
actions vides, sans clé ni donnée personnelle. Le ratio tokens/caractère diffère.

| Tour | Messages historiques | Caractères historiques | Entrée contenu | Entrée + réserve | Sortie scriptée | Entrée + sortie |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0 | 0 | 5622 | 6166 | 2010 | 7632 |
| 2 | 2 | 3008 | 7625 | 8201 | 2010 | 9635 |
| 3 | 4 | 6016 | 9628 | 10236 | 2010 | 11638 |
| 4 | 6 | 9024 | 11631 | 12271 | 2010 | 13641 |
| 5 | 8 | 12032 | 13634 | 14306 | 2010 | 15644 |
| 6 | 10 | 15040 | 15637 | 16341 | 2010 | 17647 |

**Entrée seule >8 000 au tour 3 : 9 628 tokens**, avec seulement 6 016 caractères
historiques. Aucun trimming n’est intervenu à ce seuil. Entrée + sortie dépasse
8 000 dès le tour 2 (9 635). Il n’existe donc pas de nombre de tours universellement
sûr ; longueur et densité des textes sont déterminantes.

## Sorties et risque TPM

Les quatre cas courts demandés sont représentés : ADD (tour 2, 33 tokens de sortie),
hors domaine (tour 6, 27), ambiguïté (tour 7, 15), recommandation (tour 4, 61).
Ces chiffres sont **calculés sur les fixtures**, pas des mesures du modèle.

Stress de sortie autorisé par le contrat : message de 3 999 caractères et 64
RECOMMEND_ITEM pour un produit existant, sans mutation. Le moteur accepte cette
sortie synthétique ; sa répétitivité n’est pas une réussite sémantique. Mesure :
**5 625 entrée + 3 891 sortie = 9 516 tokens** (10 060 avec réserve), dès le premier
appel sans historique. Ainsi, le contrat actuel permet mathématiquement une sortie
qui dépasse la marge disponible, même avec une entrée compacte.

Le provider actuel ne transmet pas de limite explicite de génération dans le
payload. Il renvoie le contenu texte et ne restitue pas `usage` au client FastAPI.
Les plafonds locaux (message 4 000 caractères, 64 actions, taille maximale de
réponse brute) ne sont pas des réservations de tokens de sortie côté fournisseur.
Le comptage du raisonnement et la réservation de quota restent à vérifier lors du
live ; aucune règle fournisseur actuelle n’est déduite de ces mesures hors ligne.

## Tests, reproduction et fichiers

**99 tests backend réussis** : 97 conservés + 2 tests dans
`backend/tests/test_compact_validation.py`. Ils couvrent la fidélité des valeurs
particulières, dix tours d’historique exact, les limites existantes de fenêtre et
un dépassement token avant troncature. Les tests Stage 3.6 de reconstruction,
ADD → REMOVE → ADD et reset restent passants.

**17 frontend réussis**, TypeScript/build OK. Warning du bundle 3D >500 kB inchangé.
Aucune nouvelle inspection visuelle nécessaire ou prétendue : frontend inchangé.

```sh
cd /Users/mohamedb/Downloads/12-koul
PYTHONPATH=. TIKTOKEN_CACHE_DIR=/tmp/koul-tiktoken-cache /tmp/koul-backend-venv/bin/python -B tools/check_compact_context.py
TIKTOKEN_CACHE_DIR=/tmp/koul-tiktoken-cache /tmp/koul-backend-venv/bin/python -B -m unittest discover -s backend/tests
npm --prefix frontend test
npm --prefix frontend run build
```

Le diagnostic émet du JSON local avec entrées, réponses scriptées, actions,
états, tailles et durées. Il ne charge pas de credentials et n’a aucun chemin live.
Fichiers ajoutés uniquement : ce rapport, le diagnostic et ses deux tests.

## Statut réel et recommandation

**GROQ LIVE = NOT RUN**, 0 requête réelle. Compréhension du tableau, résolution des
références de schéma, grounding réel, actions du modèle, latence, usage d’entrée,
sortie/raisonnement et comportement 429/413 restent non validés. A–E devront être
repris avec les credentials locaux, consentement de retrait exact et pacing prudent,
sans relancer l’évaluation V1/V2/V3.

**NEEDS FIXES** avant extension : l’intégrité du format est protégée et les courts
parcours déterministes fonctionnent, mais le modèle réel n’est pas testé et les
risques de quota sont démontrés localement. Il faudra décider séparément d’un budget
d’entrée/sortie, de la gestion du débit agrégé et d’une stratégie explicite pour
l’historique. Aucune de ces stratégies n’est implémentée dans cette étape.
