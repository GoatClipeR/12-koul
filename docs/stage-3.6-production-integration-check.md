# Stage 3.6 — Production integration check

8 octobre 2026. **Groq réel : NOT RUN. Recommandation : NEEDS FIXES.**

## État initial

Stage 3.5 : 94 tests backend, 17 frontend, TypeScript/build réussis. Retrait explicite
par item_id + révision, ADD → REMOVE → ADD, reset et QA responsive validés avec
provider de test. V3 est figé. Le chemin applicatif injectait le menu entier et un
schéma d’actions contenant trois copies de la liste complète des IDs de produits.
Aucun `.env` ni GROQ_API_KEY dans l’environnement accessible au contrôle Stage 3.6.

## Analyse du premier contexte

Entrée : « Je veux une grande salade avec poulet et tomate. » ; état vide,
historique vide, politique composition réelle de `run_turn`. Mesure locale avec
`tiktoken/o200k_harmony` disponible en cache. Les nombres ci-dessous concernent le
contenu texte des messages, pas les octets de l’enveloppe HTTP. Aucun secret ne
figure dans ces messages ou dans la mesure.

| Composant | Caractères avant | Tokens avant | Caractères après | Tokens après |
| --- | ---: | ---: | ---: | ---: |
| Texte exact V3 | 3 395 | 764 | 3 395 | 764 |
| Métadonnées menu, limites et règles globales | 645 | 189 | 609 | 161 |
| Catégories, tailles, slots, labels et tarification | 2 331 | 885 | 2 068 | 652 |
| 75 produits, tous champs inclus | 19 021 | 6 891 | 9 490 | 3 025 |
| ACTION_SCHEMA | 7 613 | 2 389 | 3 489 | 950 |
| MEAL_STATE | 43 | 11 | 40 | 10 |
| ACTION_POLICY | 203 | 45 | 196 | 40 |
| Historique | 0 | 0 | 0 | 0 |
| Message utilisateur | 48 | 11 | 48 | 11 |
| **Messages complets** | **33 409** | **11 211** | **19 433** | **5 631** |

Chaque composant est tokenisé séparément dans la table. Les totaux complets incluent
les clés d’enveloppe, ponctuation et frontières BPE ; ils ne sont donc pas la somme
exacte des lignes isolées. Avant optimisation, MENU_CONTEXT complet représente
7 974 tokens et ACTION_SCHEMA 2 389 : ce sont les postes dominants.

L’estimation précédente de **11 222** ajoutait 11 tokens de cadrage léger aux
11 211 tokens de contenu. Pour ne pas confondre ces méthodes :

| Mesure | Avant | Après |
| --- | ---: | ---: |
| Contenu BPE | 11 211 | 5 631 |
| Ancienne estimation, +4/message +3 | 11 222 | 5 642 |
| Réserve prudente, +512 +16/message | 11 755 | 6 175 |

Réduction du contenu : **49,8 %**, sans suppression de produit ou de règle.
L’usage autoritatif et les tokens de sortie restent à mesurer chez Groq.

## Modifications et justification

Nouveau module `backend/app/services/llm/production_context.py` :

1. JSON sérialisé avec séparateurs compacts, sans changer les valeurs.
2. Enums répétées du schéma factorisées en `$defs` avec `$ref` locaux JSON Schema.
   Les huit variantes, champs requis, additionalProperties, limites et IDs restent
   identiques après expansion des références. La validation effective reste celle
   de `schemas/actions.py`, inchangée.
3. Produits encodés en tableau `columns`/`rows`, noms bilingues en sous-tableau
   explicitement décrit par `nested_columns`. L’ordre des produits et les valeurs
   sont préservés. Une ligne courte omet les champs optionnels finaux : absence
   n’est pas convertie en null. Pour une forme future non représentable, retour à
   la liste d’objets originale, sans suppression silencieuse.

Les métadonnées, champs asset/group, règles de toutes les catégories, prix,
allergènes et tags sont conservés. Aucun filtrage lexical de menu, aucun résumé
sémantique, aucune troncature d’historique. Les mots de V3 ne sont pas modifiés.
Le test reconstruit menu et schéma et vérifie l’égalité profonde de tout le contexte,
y compris MEAL_STATE et ACTION_POLICY ; préfixe du prompt et historique inchangés.

`run_turn` dispose d’une option `compact_context=False` ; **seul FastAPI l’active**.
Le builder historique, les chemins notebook/évaluation et les fichiers du runner
restent inchangés. Le provider reçoit toujours la même interface `complete(messages)`
et produit le même contrat message/actions. Ni provider, ni meal_engine,
price_engine, action validation, prompts V1/V2/V3 ou SaladScene n’ont été modifiés.
La production ne dépend pas de tiktoken : il sert uniquement aux mesures/tests.

Cette équivalence des données ne prouve pas que le modèle lira le nouveau format
avec une qualité identique. La vérification ciblée live reste obligatoire.

## Résultats locaux

**97 tests backend réussis** : 94 existants + 3 nouveaux tests :

- Reconstruction sans perte du menu/schéma et conservation exacte prompt,
  historique, état, politique ; absence de mutation des entrées.
- Repli sans perte pour une forme de produit non représentable par les colonnes.
- FastAPI → MockProvider → validation → état : ADD → REMOVE → ADD, prix 55 MAD,
  autorisation exacte du retrait, reset et historique vierge après reset.
  Budget prudent ≤6 500 tokens pour cette courte conversation.

**17 tests frontend réussis** (13 Vitest + 4 Node), TypeScript et build Vite réussis.
Les tests d’intégration UI/projection d’ajout/retrait et reset sont conservés.
Pas de nouvelle QA visuelle Stage 3.6 : frontend et scène sont inchangés.

Une seconde exécution locale via FastAPI utilise les trois messages du test live
prévu, avec réponses explicitement scriptées par MockProvider :

| Tour | Résultat HTTP local | Tokens contenu | Avec réserve | État accepté |
| --- | ---: | ---: | ---: | --- |
| Grande salade poulet/tomate | 200 | 5 631 | 6 175 | Grande salade, poulet + tomate |
| Ajoute du maïs | 200 | 5 691 | 6 267 | Poulet + tomate + maïs |
| Enlève la tomate, consentement exact fourni | 200 | 5 726 | 6 334 | Poulet + maïs |

Ces HTTP 200 sont **FastAPI avec provider de test**, aucun n’est un HTTP Groq.
Les chiffres varient avec le texte effectivement reçu et l’état. Le plafond 6 500
est une assertion de régression pour ces courts parcours, pas une garantie globale
ni un limiteur de débit ajouté à la production.

Commandes exécutées depuis la racine :

```sh
TIKTOKEN_CACHE_DIR=/tmp/koul-tiktoken-cache /tmp/koul-backend-venv/bin/python -B -m unittest discover -s backend/tests
npm --prefix frontend test
npm --prefix frontend run build
```

## Groq réel — NOT RUN

Contrôle : `.env` absent ; clé GROQ_API_KEY absente du shell et du fichier attendu.
**0 requête Groq**, aucun statut HTTP provider, temps de réponse, timeout, usage
réel ou action réelle à rapporter. Aucun contournement, aucune clé créée, aucune
évaluation des 42 scénarios relancée.

Après fourniture locale des credentials, reprendre seulement les trois tours du
tableau, via FastAPI configuré avec V3 et le provider Groq existant. Le troisième
porte `remove_item_id=salad.ingredient.tomato` et la dernière révision affichée.
Mesurer HTTP applicatif/provider, durée, usage et état. Espacer d’au moins 65 secondes
les appels, arrêter au premier échec et examiner sa cause sans changer le payload
silencieusement. Utiliser les commandes backend et `.env.example` du README.

## Risques restants et recommandation

- Les courts tours mesurés passent sous le quota observé de 8 000 TPM avec une
  marge d’entrée ; les tokens de sortie, requêtes concurrentes et règles exactes
  de comptabilisation provider peuvent consommer cette marge. Pas de garantie HTTP 200.
- Le plafond historique de 16 000 caractères est inchangé. Exemple synthétique :
  quatre messages de 4 000 caractères peuvent porter le contexte à environ
  **13 635 tokens de contenu / 14 243 avec réserve**. Une limite en caractères ne
  constitue pas un budget en tokens. Aucune suppression d’historique ajoutée pour
  cacher ce problème ; une stratégie explicite devra être décidée pour les longues
  conversations et le débit partagé.
- Aucun contrôle sémantique réel du nouveau tableau/références schema tant que
  le test Groq ciblé n’a pas été exécuté. Les tests prouvent conservation des
  données et fonctionnement déterministe, pas compréhension du modèle.
- Warning bundle 3D >500 kB inchangé ; performances mobiles toujours non mesurées.

**NEEDS FIXES** : réduction sûre des données implémentée et régressions locales
passées, mais la boucle avec Groq réel reste NOT RUN et les longues conversations
peuvent encore dépasser le quota. Aucune extension de catégories à cette étape.
