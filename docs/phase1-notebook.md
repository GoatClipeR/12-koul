# Notebook Phase 1 — KOOL AI

## Référence et exécution

Cahier des charges lu : `TP_Chatbot_Specialise.pdf`, Pr. H. Ayad, Mundiapolis,
pages 1–2 pour la Phase 1 (source locale : Downloads). Le notebook suit A–E et
ne développe pas les endpoints FastAPI de Phase 2.

Ouvrir `notebook/phase1.ipynb` dans Jupyter / VS Code, puis exécuter les cellules
dans l’ordre. Alternative Python standard, depuis la racine :

```sh
python3 -B tools/run_phase1.py
```

Ce lanceur exécute les huit cellules Python et sauvegarde leurs sorties dans le
notebook. Aucun paquet Jupyter n’est requis pour ce mode. Les tableaux s’affichent
en Markdown enrichi sous Jupyter, et en texte avec le lanceur standard.

## Contenu et couverture

| Exigence | Livrable |
| --- | --- |
| A : identité, domaine, public, besoins, 3 exemples, limites | Présentation KOOL AI / restauration 12-KOUL |
| B : modèle et secrets | Groq `openai/gpt-oss-120b`, abstraction applicative documentée, aucune clé dans les cellules |
| C : prompt | Chargement exact de V1/V2/V3, rôle, ton, langues, format, ambiguïté, limites et injection |
| D : conversation | Fonction message + historique + état, boucle de démonstration, `/reset` testé |
| E : situations | Les 14 scénarios existants ; 42 combinaisons prévues |
| Tableau TP | Question, comportement attendu, réponse obtenue, appréciation, amélioration proposée |
| Comparaison | Trois tableaux réels ; métriques structurelles et 42 appréciations sémantiques assistées séparées |
| Analyse | Conclusion provisoire, limites et travail restant explicites |

**Deux situations de contexte explicites :** `history` appartient à la suite figée ;
le notebook ajoute un dialogue salade en deux tours, hors de cette suite. Tour 1 :
grande salade, poulet, tomate. Tour 2 : ajout du maïs à ce même repas. Les réponses
sont des fixtures **MOCK**, transmises à la fonction de conversation et au moteur
existants. Les assertions vérifient les deux lots acceptés, la conservation exacte
du repas, l’historique et l’état envoyés au second tour, puis le reset sans appel
fournisseur. Le premier état n’est pas muté.

Cette démonstration complète la couverture pédagogique ; sa compréhension par un
modèle réel reste en attente. Elle n’ajoute aucune ligne au fichier Groq et ne change
ni les 14 scénarios, ni leur comparaison V1/V2/V3. Elle ne prouve pas à elle seule
la satisfaction sémantique complète de l’exigence de contexte du TP.

## Résultats, sans interférence avec Groq

`tools/phase1_notebook.py` lit `notebook/real-results.local.json` **en lecture seule**.
Chaque exécution prend un snapshot ; il n’y a ni polling ni appel réseau. Un fichier
absent/illisible, une combinaison absente, un échec fournisseur et une réponse
reçue ont des statuts distincts. Les 14 questions figurent dans chaque tableau,
même quand leurs résultats ne sont pas encore disponibles.

Le notebook ne lance jamais `direct_groq_eval.py`. La fabrique applicative
`configured_provider()` est définie mais n’est pas appelée. Aucun mode `RUN_REAL`
n’est présent. `report` conserve le rapport mock pour la compatibilité avec les
tests existants ; `real_report` contient le snapshot réel séparé. Les résultats
mock ne remplissent jamais un trou dans les tableaux Groq.

Le JSON complet reste la référence pour les actions, états, prix et indicateurs
de sécurité détaillés. Les métadonnées sélectionnées donnent fournisseur, modèle,
date, version des scénarios, hashes, stratégie de contexte et paramètres de génération.
Les sorties enregistrées du notebook sont datées par ces métadonnées ; les réexécuter
pour consulter un checkpoint plus récent. Aucun statut de fin n’est inféré à partir
de la seule présence du fichier.

## Appréciation pédagogique

La revue assistée des 42 réponses est disponible dans
[semantic-evaluation.md](semantic-evaluation.md). V1 : 8 PASS / 3 PARTIAL / 3 FAIL ;
V2 : 11 / 2 / 1 ; V3 : 11 / 3 / 0. Préférence provisoire V3 : elle attend le choix
de base là où V2 ajoute la roquette sans attendre. Ce jugement ne vient pas des
lots acceptés ; les explications sensibles et la langue de history restent faibles.
Une validation humaine indépendante reste à faire.

`docs/semantic-evaluation.json` contient les verdicts rédigés et leurs raisons.
`read_semantic_review` ne les charge que pour le hash exact du fichier réel et les
42 clés correspondantes. En cas de fichier absent, modifié ou de revue incomplète,
les appréciations restent en attente. Les annotations PENDING du JSON brut ne sont
pas réécrites ; aucun résultat réel n’est modifié.

Avant remise : renseigner les noms du binôme, valider humainement la revue assistée et sa
courte analyse, puis évaluer réellement le dialogue salade complémentaire. Les prompts restent
inchangés ; aucune nouvelle évaluation n’est lancée.

## Validation

- Huit cellules compilées et exécutées hors ligne par le lanceur fourni.
- Suite Python : 80 tests réussis, dont les tests existants de conversation et du notebook.
- Nouveaux tests : lecture sans écriture, checkpoint partiel, échecs sans substitution
  mock, échappement HTML des tableaux et syntaxe des cellules.
- Aucun appel Groq déclenché par ces opérations.

Vérification de finalisation du 7 octobre 2026 : huit cellules compilées et
exécutées par `tools/run_phase1.py` (exécution Python standard, pas un kernel
Jupyter), 80 tests Python et quatre tests frontend réussis, build TypeScript/Vite
réussi. L’avertissement du bundle 3D >500 Ko demeure. Le rendu de la salade
restaurée a été observé dans Brave, viewport de contrôle desktop 1390 × 844.
Ce contrôle ne mesure pas les performances mobiles.

Lors de la finalisation précédente, le snapshot partiel consulté portait le timestamp `2026-10-07T22:42:10.396830+00:00` :
30/42 lignes, 30 réponses modèle et 28 lots d’actions acceptés, avec
`completed=false`. Ce constat en lecture seule ne certifie ni la fin du processus
ni la qualité sémantique des réponses. Le fichier peut évoluer indépendamment.
Les sources backend, prompts, menu, outils Groq, sources frontend et GLB ont été
comparés par hash avant/après : aucune modification durant cette finalisation.

## Suite préparée, non implémentée

Voir [architecture future](next-architecture.md) pour le trajet UI → API → modèle
→ moteur déterministe → état → scène. Le statut de la salade est **TECHNICAL VERTICAL
SLICE = VALIDATED**, **ART DIRECTION = NEEDS POLISH** ; détails et limites dans
[la documentation 3D](3d-architecture.md). Aucun développement FastAPI ici.

## Actualisation après fin du run réel

Le run est enregistré terminé à `2026-10-07T23:28:29.573868+00:00` : 42 réponses
complètes, aucun échec HTTP, 429 ou 413 ; 40 lots acceptés (12/14, 14/14, 14/14).
Le notebook affiche les résultats réels et les appréciations justifiées de la revue.
Le dialogue salade complémentaire reste MOCK et n’entre pas dans ces 42 réponses.

Vérifications de cette actualisation : huit cellules compilées/exécutées, 80 tests
backend existants et quatre tests de provenance/présentation de revue réussis.
Ces derniers vérifient les clés, le hash, l’absence de substitution, les messages
reproduits et la distinction lot accepté / FAIL sémantique ; ils ne prouvent pas
la justesse des jugements humains. Aucun code backend ou 3D modifié.
