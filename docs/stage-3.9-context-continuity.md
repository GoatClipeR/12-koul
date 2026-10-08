# Stage 3.9 — Context continuity

8 octobre 2026. **Prototype hors production. GROQ LIVE = NOT RUN. Verdict : NEEDS FIXES.**

## Résultat principal

Le blocage local du parcours mixte au tour 8 est résolu sans augmenter le budget :
**6 538 → 6 387 tokens estimés d’entrée**, soit **8 038 → 7 887** avec sortie réservée
et marge. Le nouveau scénario réaliste passe **15/15 tours**, ainsi que la reprise
sur 15 tours du parcours mixte Stage 3.8. Tous les envois admis restent sous 6 500
d’entrée et 8 000 au total. Ce sont des actions scriptées appliquées par le moteur,
**pas des actions générées ou comprises par Groq**.

Aucun changement des prompts, provider de production, moteurs, validation, actions,
règles métier, catégories ou SaladScene. La stratégie reste un prototype distinct :
son interprétation réelle par le modèle et son raccordement au journal applicatif
ne sont pas validés. Les résultats complets par tour, dont messages récents,
résumé, motifs d’oubli, actions et snapshots avant/après, sont disponibles dans
[stage-3.9-local-results.json](stage-3.9-local-results.json).

## 1. Cause exacte du blocage initial

Mesure `o200k_harmony`, même entrée, même état, même autorisation au tour 8 du parcours
mixte. Réserve de cadrage : 512 + 16 × nombre de messages.

| Composant | Tokens locaux au tour 8 |
| --- | ---: |
| Texte V3 | 764 |
| MENU_CONTEXT compact complet | 3 844 |
| ACTION_SCHEMA | 950 |
| MEAL_STATE | 61 |
| ACTION_POLICY, retrait du maïs autorisé | 56 |
| Deux derniers tours, contenu seul | 29 |
| Dernier message utilisateur | 7 |
| Archive ancienne, JSON complet isolé | 191 |
| Contenu total réellement assemblé | 5 914 |
| Réserve de cadrage, 7 messages | 624 |
| **Entrée estimée** | **6 538** |
| Sortie réservée | 1 024 |
| Marge supplémentaire | 476 |
| **Total candidat** | **8 038** |

Les composants sont tokenisés isolément ; ponctuation d’enveloppe et frontières BPE
expliquent que leur somme diffère du total assemblé. L’échec est un dépassement de
**38 tokens**, pas une augmentation du menu ou de V3. La politique de retrait et
l’état courant sont nécessaires. La hausse évitable est surtout l’archive : elle
conserve des commandes déjà exécutées et une phrase « Merci de garder mes choix. »
répétée huit fois. L’archive atteint 191 tokens contre 121 au tour 7 ; les derniers
tours, eux, diminuent de 78 à 29 tokens. Sortie et marge sont fixes, pas la cause de
croissance entre ces tours, mais déterminent le plafond d’admission.

### Chaque tentative du parcours mixte

A = ancien historique ancien en JSON compact (hors deux dernières paires).
B = archive réversible Stage 3.8 de ce même historique.
C = mémoire minimale candidate Stage 3.9. Les ensembles vides A/B incluent leur
enveloppe JSON ; C vide n’est pas envoyé. La mémoire n’est utilisée que lorsque le
contexte intégral dépasse le budget.

| Tour | Ancienne entrée | Sortie | Marge | Ancien total | Messages anciens envoyés | Messages archivés | A | B | C | Récent contenu | Nouvelle entrée |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 6213 | 1 024 | 476 | 7713 | 2 | 0 | 1 | 36 | 0 | 0 | 6213 |
| 2 | 6260 | 1 024 | 476 | 7760 | 4 | 0 | 1 | 36 | 0 | 14 | 6260 |
| 3 | 6331 | 1 024 | 476 | 7831 | 6 | 0 | 1 | 36 | 0 | 29 | 6331 |
| 4 | 6355 | 1 024 | 476 | 7855 | 8 | 0 | 30 | 57 | 0 | 31 | 6355 |
| 5 | 6451 | 1 024 | 476 | 7951 | 10 | 0 | 59 | 78 | 0 | 31 | 6451 |
| 6 | 6497 | 1 024 | 476 | 7997 | 12 | 0 | 89 | 100 | 0 | 79 | 6497 |
| 7 | 6493 | 1 024 | 476 | 7993 | 7 | 8 | 118 | 121 | 24 | 78 | 6402 |
| 8 | 6538 | 1 024 | 476 | 8038 | 7 | 10 | 196 | 191 | 34 | 29 | 6387 |
| 9 | 6520 | 1 024 | 476 | 8020 | 7 | 12 | 224 | 195 | 34 | 31 | 6365 |
| 10 | 6573 | 1 024 | 476 | 8073 | 7 | 14 | 253 | 199 | 34 | 31 | 6414 |
| 11 | 6575 | 1 024 | 476 | 8075 | 7 | 16 | 283 | 203 | 34 | 79 | 6412 |
| 12 | 6579 | 1 024 | 476 | 8079 | 7 | 18 | 312 | 207 | 51 | 78 | 6429 |
| 13 | 6558 | 1 024 | 476 | 8058 | 7 | 20 | 390 | 211 | 51 | 29 | 6404 |
| 14 | 6540 | 1 024 | 476 | 8040 | 7 | 22 | 418 | 215 | 51 | 31 | 6382 |
| 15 | 6593 | 1 024 | 476 | 8093 | 7 | 24 | 447 | 219 | 51 | 31 | 6431 |

Les tours 1–8 reproduisent l’état avant le premier blocage de Stage 3.8. Après ce
point, l’ancienne stratégie est mesurée **hypothétiquement sur les états poursuivis
par la nouvelle stratégie** : elle n’avait pas réellement réussi ces tours en 3.8.
Au tour 8, C = 34 tokens, constitué de la demande compacte de conserver les choix
et de l’ancien échange hors domaine dont l’acquittement générique n’établit pas une
réponse satisfaisante. Trois commandes terminées sont retirées du contexte ancien.
Le meal_state reste identique avant planification et n’est pas dupliqué en mémoire.

## 2. Nouvelle stratégie : mémoire minimale prudente

L’ordre reste : V3 et sécurité, menu intégral, état courant, dernier message et deux
dernières paires intactes, puis informations anciennes nécessaires. Aucun résumé LLM.

### Reçus vérifiés et grammaire fermée

Chaque tour du prototype possède utilisateur, assistant, actions, état avant et
état après. Le reçu est créé par le moteur inchangé, après validation et autorisation
exacte des actions protégées. La chaîne d’états doit rejoindre le snapshot courant.
Ces reçus sont des données internes de confiance, **pas un nouveau champ accepté
sur l’API ni une permission déclarable par le modèle**.

Une commande ancienne est dispensable seulement si :

- elle correspond intégralement à une grammaire fermée de création de salade,
  ajout/retrait d’un produit nommé sans ambiguïté ou changement de taille ;
- les actions du reçu correspondent exactement à cette commande ;
- le texte assistant est un acquittement fermé connu, sans question ou détail
  supplémentaire à conserver.

Leur résultat est déjà représenté dans meal_state. Toute condition/suffixe,
paraphrase inconnue, référence ambiguë ou question assistant interdit cette réduction.
Ainsi « Ajoute du maïs, mais jamais de sauce. » est conservé intégralement, même si
un ADD a été validé. Le classificateur **n’autorise jamais** une action.

### Champs de mémoire

- `language_request` : dernière demande explicite parmi les formulations reconnues,
  accompagnée de la citation originale ; préférence utilisateur non autoritaire.
- `constraints` : formulation exacte reconnue « Je préfère sans sauce pour le
  moment. », conservée comme texte ; aucune allergie ou préférence inférée.
- `keep_choices_request` : représentation unique de « Merci de garder mes choix. »
  dans la formulation de retour au repas, y compris ses répétitions exactes.
- `unresolved_turns` : échanges non classifiables, décisions/questions/contraintes
  conservées verbatim avec leur contexte assistant. Pas de résumé arbitraire.

Les remerciements fermés et une demande de poème exactement refusée peuvent être
retirés ; un acquittement inconnu ne suffit pas. La taille, la catégorie et la liste
d’ingrédients ne sont pas recopiées : meal_state reste leur source de vérité.
Un résultat de recommandation/menu et une question ouverte sont conservés même si
les données produit existent aussi dans le menu, car une référence ultérieure peut
dépendre de leur formulation ou de leur ordre.

La mémoire est transportée dans un message **user de données non fiables**, jamais
dans V3, ni dans ACTION_POLICY. Les anciens messages inconnus restent non fiables.

### Références au passé et surcharge

Avant toute réduction, le message courant doit être reconnu comme autonome par une
grammaire fermée ou une question explicite prise en charge. Pour une référence
comme « Annule la modification que j’ai demandée au début », le prototype revient
à l’historique réversible Stage 3.8. Si celui-ci ne tient pas, il refuse l’envoi
explicitement. Il ne devine pas l’antécédent à partir de l’état courant.

Cette archive exhaustive est **un repli de sûreté**, pas la mémoire nominale. Le
résumé minimal ne doit pas devenir un journal complet déguisé : les cas opaques
peuvent encore provoquer un refus, car aucune information potentiellement nécessaire
n’est supprimée pour obtenir artificiellement 15 tours.

## 3. Budget de sortie

Valeurs conservées : **6 500 entrée, 1 024 sortie, 476 marge**. Aucun gain présenté
ne vient d’une réduction des réserves. Les fixtures antérieures utilisent quelques
dizaines de tokens, mais cela ne démontre pas les besoins réels du modèle, notamment
son raisonnement, les recommandations multiples ou une ambiguïté non anticipée.
Une classification lexicale d’ADD/refus/clarification n’est pas une preuve que le
modèle générera seulement cette réponse. Aucun budget de sortie adaptatif ajouté.

Le total est une borne locale estimée, pas une garantie du TPM agrégé. Le provider
production reste inchangé et n’applique pas encore cette réservation comme plafond
de génération. Les tokens déjà générés ne sont pas annulables par un contrôle local.

## 4. Scénario réaliste de 15 tours

États : G/P = grande/petite salade ; seules les sélections sont indiquées, pas une
validation de commande. Sortie réservée 1 024 et marge 476 à chaque tour.

| Tour | Demande utilisateur | Actions scriptées | Entrée | Total | État après moteur |
| --- | --- | --- | ---: | ---: | --- |
| 1 | Je veux une grande salade avec poulet et tomate. | SET_CATEGORY salad, SET_SIZE large, ADD_ITEM salad.ingredient.grilled_chicken, ADD_ITEM salad.ingredient.tomato | 6175 | 7675 | large : grilled_chicken, tomato |
| 2 | Ajoute du maïs. | ADD_ITEM salad.ingredient.corn | 6262 | 7762 | large : grilled_chicken, tomato, corn |
| 3 | Quelles bases proposes-tu ? | RECOMMEND_ITEM salad.base.lettuce | 6312 | 7812 | large : grilled_chicken, tomato, corn |
| 4 | Ajoute de la laitue. | ADD_ITEM salad.base.lettuce | 6365 | 7865 | large : lettuce, grilled_chicken, tomato, corn |
| 5 | Enlève le maïs. | REMOVE_ITEM salad.ingredient.corn | 6432 | 7932 | large : lettuce, grilled_chicken, tomato |
| 6 | Écris un poème. | aucune | 6452 | 7952 | large : lettuce, grilled_chicken, tomato |
| 7 | Revenons à ma salade. | aucune | 6497 | 7997 | large : lettuce, grilled_chicken, tomato |
| 8 | Enlève la tomate. | REMOVE_ITEM salad.ingredient.tomato | 6377 | 7877 | large : lettuce, grilled_chicken |
| 9 | Ajoute du concombre. | ADD_ITEM salad.ingredient.cucumber | 6353 | 7853 | large : lettuce, grilled_chicken, cucumber |
| 10 | Passe à une petite salade. | SET_SIZE small | 6373 | 7873 | small : lettuce, grilled_chicken, cucumber |
| 11 | Ajoute une sauce. | aucune | 6372 | 7872 | small : lettuce, grilled_chicken, cucumber |
| 12 | Ajoute de la sauce Caesar. | ADD_ITEM salad.sauce.caesar | 6373 | 7873 | small : lettuce, grilled_chicken, cucumber, caesar |
| 13 | Est-ce complet ? | aucune | 6378 | 7878 | small : lettuce, grilled_chicken, cucumber, caesar |
| 14 | Enlève le poulet. | REMOVE_ITEM salad.ingredient.grilled_chicken | 6410 | 7910 | small : lettuce, cucumber, caesar |
| 15 | Récapitule ma salade. | aucune | 6383 | 7883 | small : lettuce, cucumber, caesar |

Les tours récents sont toujours intacts. La mémoire est activée à partir du tour 8 :
la recommandation des bases reste conservée, puis le retour au repas et la question
ouverte sur la sauce. En fin de scénario, la question de complétude est également
conservée. La réponse finale scriptée décrit correctement une petite salade avec
laitue, concombre et César, un ingrédient et un topping manquants. Aucune confirmation
ni prix provenant du texte assistant. Les snapshots/actions/mémoires exacts sont
dans le JSON joint ; il contient aussi les cas où l’historique intégral a été gardé.

Ces 15 tours démontrent l’admission, la réduction déterministe et l’application des
actions connues au moteur. **Ils ne démontrent pas qu’un LLM choisirait les mêmes
actions après lecture de la mémoire.** Les messages assistant scriptés sont courts
et plusieurs acquittements appartiennent volontairement à la grammaire fermée ; un
modèle réel plus varié peut déclencher davantage de conservation et de refus.

## 5. Tests et limites de sécurité

**110 backend réussis** : 104 conservés + 6 tests. **17 frontend réussis** ;
TypeScript/build OK. Warning de bundle 3D >500 kB inchangé.

Les nouveaux tests couvrent déterminisme et mémoire minimale ; contraintes/langue
conservées ; suffixe de commande non effacé ; question ouverte non effacée ; deux
parcours de 15 tours ; ajout/retrait/taille après réduction ; repli sans perte sur
référence ancienne ; reset via DELETE puis absence de mémoire ; budget dépassé
sans mutation partielle ; chaîne de reçus incohérente refusée.

Une ancienne instruction adversariale ne devient ni système ni autorisation :
ACTION_POLICY reste inchangé et CLEAR_MEAL non autorisé est rejeté. Son texte inconnu
reste dans les données non fiables. **L’absence de réactivation sémantique par le
modèle ne peut pas être prouvée sans test réel** ; le test garantit seulement les
frontières du code et du moteur, pas l’immunité aux injections du LLM.

## 6. Groq et déploiement

**GROQ LIVE = NOT RUN**. `.env` absent, GROQ_API_KEY absente du shell et du fichier
attendu. Aucun appel réel, aucun HTTP provider ou usage inventé. Pas d’évaluation
V1/V2/V3 ni relance des 42 scénarios.

Production non modifiée : les fichiers ajoutés sont le prototype, son diagnostic,
six tests, ce rapport et le JSON local de mesures. La fenêtre actuelle de production
peut déjà avoir retiré de l’historique ; le prototype ne restaure pas ces données.
Une future intégration devra capturer des reçus fiables et gérer la mémoire avant
cette suppression, puis valider langue, anaphores, questions ouvertes, sortie bornée
et quota agrégé avec le provider réel.

La grammaire volontairement étroite préserve la sûreté mais ne couvre pas toutes les
paraphrases. Les décisions opaques ou questions non résolues restent volumineuses.
Un dépassement réellement incompressible est toujours refusé. Aucune promesse de
continuité illimitée ou de protection TPM fournisseur n’est faite.

**Verdict : NEEDS FIXES.** Le blocage local identifié et le parcours de 15 tours sont
résolus dans le prototype, sans retirer leurs informations nécessaires. Restent la
validation réelle de la compréhension, la couverture des formulations et l’intégration
à la mémoire applicative avant toute extension de catégorie.

## Reproduction et fichiers

```sh
cd /Users/mohamedb/Downloads/12-koul
PYTHONPATH=. TIKTOKEN_CACHE_DIR=/tmp/koul-tiktoken-cache /tmp/koul-backend-venv/bin/python -B tools/check_context_continuity.py
TIKTOKEN_CACHE_DIR=/tmp/koul-tiktoken-cache /tmp/koul-backend-venv/bin/python -B -m unittest discover -s backend/tests
npm --prefix frontend test
npm --prefix frontend run build
```

- `tools/context_continuity.py`
- `tools/check_context_continuity.py`
- `backend/tests/test_context_continuity.py`
- `docs/stage-3.9-context-continuity.md`
- `docs/stage-3.9-local-results.json`
