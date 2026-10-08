# Stage 3.8 — Token budget and history

8 octobre 2026. **Prototype hors production. GROQ LIVE = NOT RUN. Verdict : NEEDS FIXES.**

## 1. Problème initial et informations à conserver

Le contexte compact Stage 3.6 conserve toutes les données : environ 5 631 tokens de
contenu / 6 175 avec réserve au premier tour. Stage 3.7 démontre que l’historique et
les sorties peuvent néanmoins dépasser le quota précédemment observé de 8 000 TPM.
Le quota TPM est un débit agrégé, pas une fenêtre de contexte. Ni une limite par
requête, ni un contrôle a posteriori ne suffisent à garantir ce quota global.

| Information | Source / traitement |
| --- | --- |
| Catégorie active, brouillons de toutes les catégories, taille et IDs par slot | MEAL_STATE déterministe, toujours conservé intégralement |
| Prix, slots, compatibilité, limites du restaurant | Menu compact et moteurs, jamais reconstruits depuis la prose |
| Autorisation du retrait exact, état auquel elle se rapporte | ACTION_POLICY construit par le code pour le tour courant, jamais hérité d’un ancien texte |
| Règles de rôle, grounding et sécurité | Texte V3 inchangé |
| Préférences, exclusions encore valables, langue, questions non résolues, décisions conversationnelles | Pas toutes représentées dans meal_state : conserver leur texte et leur chronologie |
| Propositions assistant antérieures | Ne prouvent pas une mutation ; peuvent néanmoins expliquer une réponse comme « la deuxième », donc ne pas les supprimer aveuglément |

La croissance vient de messages de plus en plus nombreux et/ou longs, et du cadrage
par message. Le menu et V3 restent essentiellement fixes ; l’état grandit seulement
avec les sélections. Un changement d’état n’autorise pas à effacer une contrainte
qui se trouvait dans le même message utilisateur.

La fenêtre de production actuelle (40 messages / 16 000 caractères, suppression de
paires anciennes) reste inchangée. Le prototype utilise un journal complet séparé
pour étudier jusqu’à 30 tours : il ne passe **pas** les messages par cette fenêtre.
Il ne prétend pas récupérer les informations déjà perdues par une session réelle.

## 2. Budget proposé et justification

Configuration explicite du prototype, ajustable par `Budget(...)` :

| Paramètre | Valeur de départ | Justification |
| --- | ---: | --- |
| MAX_CONTEXT_TOKENS | 6 500 | Le premier tour prudent consomme 6 175 ; laisse une réserve modeste pour l’état, la politique et les tours récents. Les courts parcours Stage 3.6 étaient <6 500. |
| MAX_OUTPUT_TOKENS | 1 024 | Les fixtures courtes Stage 3.7 utilisaient 15–88 tokens ; 1 024 laisse une marge pour JSON/actions et explication, sans réserver les sorties synthétiques excessives. Ce n’est pas une mesure du raisonnement réel. |
| SAFETY_MARGIN | 476 | Solde de 8 000 − 6 500 − 1 024 ; réserve explicite pour l’incertitude, à recalibrer avec l’usage réel. |
| REQUEST_LIMIT | 8 000 | Plafond observé précédemment, non revérifié chez Groq pendant cette étape. |
| RECENT_PAIRS | 2 | Préserve deux échanges complets intacts pour les corrections et références immédiates ; toutes les informations plus anciennes restent reconstructibles dans l’archive. |

Entrée estimée = tokens BPE `o200k_harmony` + **512 + 16 × nombre de messages**.
L’entrée inclut déjà cette réserve de cadrage ; la marge de 476 est supplémentaire.
Admission : entrée ≤6 500 et entrée + sortie réservée + marge ≤8 000. Les valeurs
incohérentes/non positives sont rejetées. Les tailles par défaut sont une hypothèse
prudente pour tester l’admission, **pas un réglage de production validé** : le stress
mixte montre justement qu’elles bloquent parfois trop tôt.

La marge de sortie de 1 024 ne garantit pas de contenir toutes les 64 actions que le
contrat permet. Une limite de génération fournisseur pourrait produire un JSON
tronqué : celui-ci doit rester rejeté par la validation existante. On ne modifie
ni ce contrat ni ses actions pour faire réussir artificiellement les tests.

## 3. Architecture du prototype et stratégie déterministe

`tools/history_budget_prototype.py`, importé seulement par diagnostics/tests :

1. Construire V3 + MENU_CONTEXT compact complet + MEAL_STATE + ACTION_POLICY avec
   les fonctions existantes. Le message courant demeure intact.
2. Si l’historique intégral tient, transmettre exactement ses messages, sans archive.
3. Sinon garder les deux dernières paires utilisateur/assistant intactes. Archiver
   les anciennes paires dans une table de textes exacts, dédupliquée par égalité
   stricte, et une séquence de références avec compteurs de répétition.
4. Remplacer ces anciens messages par **un message de données de rôle user**, typé
   `untrusted_history_archive_v1`. Jamais un message système, jamais une autorisation.
5. Recompter le payload final. Si le budget ne tient toujours pas :
   `CONTEXT_BUDGET_EXCEEDED`, **BLOCKED_NO_SEND**, sans mutation d’état ou du journal.

Il s’agit d’un archivage structuré réversible, pas d’un résumé libre et pas d’une
extraction sémantique par mots-clés. Seules les copies textuelles identiques et les
enveloppes répétées sont supprimées ; le nombre, le rôle et l’ordre de chaque
occurrence restent enregistrés. L’expansion de l’archive redonne exactement le
journal initial. Pas d’inférence de langue, de préférence ou de consentement depuis
un ancien message ; les textes correspondants restent disponibles intégralement.

Ce choix évite de déclarer arbitrairement « redondant » un message qui contient
une exclusion alimentaire ou une décision. En contrepartie, les messages uniques
longs ne se compressent pas assez : le prototype refuse leur envoi. Sans extraction
sémantique fiable ou accord utilisateur sur une perte de contexte, on ne peut pas
garantir à la fois admission universelle et conservation intégrale.

Un garde local `check_output` rejette une sortie au-delà du budget avant application
d’actions dans le diagnostic. **Il ne peut pas annuler les tokens déjà générés ou
facturés**. Le prototype n’envoie aucune requête réseau et n’installe pas de limite
de génération chez le provider. Il faudrait valider une limite côté fournisseur
et une gestion du débit agrégé avant tout déploiement.

## 4. Validation A–J

Toutes les actions sont **scriptées localement**, puis passées au moteur existant.
Aucun modèle ne les a déduites de l’archive. Le journal long de base contient 30
paires répétitives ; les cas G/H/J ajoutent une paire de contexte ancien. État de
salade initial : grande, poulet grillé + tomate, autres slots vides.

| Cas | Entrée estimée | Sortie réservée | Total avec marge | Messages envoyés | Anciens messages archivés | État avant → après |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| A short | 6251 | 1024 | 7751 | 4 | 0 | Grande poulet/tomate → identique ; aucune archive |
| B long | 6304 | 1024 | 7804 | 7 | 56 | Vide → vide ; archive réversible |
| C state preserved | 6353 | 1024 | 7853 | 7 | 56 | Grande poulet/tomate → strictement identique |
| D remove | 6368 | 1024 | 7868 | 7 | 56 | Grande poulet/tomate → poulet ; retrait autorisé exact |
| E add | 6352 | 1024 | 7852 | 7 | 56 | Grande poulet/tomate → poulet/tomate/maïs |
| F size | 6352 | 1024 | 7852 | 7 | 56 | Grande poulet/tomate → petite poulet/tomate |
| G topic return | 6371 | 1024 | 7871 | 7 | 58 | Question hors domaine archivée → retour, repas identique |
| H language | 6363 | 1024 | 7863 | 7 | 58 | Demande anglaise conservée → ajout maïs scripté |
| I reset fresh | 6166 | 1024 | 7666 | 2 | 0 | Reset DELETE → état vide, historique vide, aucune archive |
| J old injection | 6374 | 1024 | 7874 | 7 | 58 | Ancienne injection conservée comme donnée → aucune autorisation créée, repas identique |

Le total inclut toujours 476 de marge. Les messages envoyés incluent système,
message courant et éventuellement archive ; « archivés » ne signifie pas oubliés.
Quatre messages récents restent verbatim dans chaque cas long. Le JSON du diagnostic
contient aussi les snapshots complets avant/après et le nombre de tokens des
sorties scriptées, inférieures au budget réservé.

Tests additionnels : configurations invalides rejetées ; sortie synthétique trop
longue rejetée ; refus explicite d’un contexte dense sans perte de données ; journal
et meal_state non mutés par l’archivage ; reconstruction exacte avec préférence
« No sauce until I choose » et question ouverte conservées ; suppression de la
conversation via le DELETE existant et nouveau plan sans historique.

Sécurité J : l’ancien texte n’entre jamais dans V3 ni ACTION_POLICY, ne devient pas
un message de rôle system et ne crée aucun grant. CLEAR_MEAL proposé sans grant
reste rejeté par le moteur. **Ce test ne prouve pas qu’un LLM ne suivra jamais une
ancienne injection réencodée**. La non-réactivation sémantique reste à valider en
live, comme la compréhension de langue et des références conversationnelles.

## 5. Stress 10 / 20 / 30 tours

Chaque ligne ci-dessous planifie un nouveau message après N paires conservées en
entier. Pour les lignes bloquées, le coût affiché est celui du candidat refusé,
**aucune requête ne serait envoyée**. État avant/après inchangé dans ces sondes.

| Famille | Tours historiques | Décision | Entrée candidate | Total candidat |
| --- | ---: | --- | ---: | ---: |
| normal_repeated | 10 | ADMITTED_OFFLINE | 6353 | 7853 |
| out_of_domain | 10 | ADMITTED_OFFLINE | 6374 | 7874 |
| meal_requests | 10 | ADMITTED_OFFLINE | 6380 | 7880 |
| long_repeated | 10 | BLOCKED_NO_SEND | 6896 | 8396 |
| unique_long | 10 | BLOCKED_NO_SEND | 24540 | 26040 |
| normal_repeated | 20 | ADMITTED_OFFLINE | 6353 | 7853 |
| out_of_domain | 20 | ADMITTED_OFFLINE | 6374 | 7874 |
| meal_requests | 20 | ADMITTED_OFFLINE | 6380 | 7880 |
| long_repeated | 20 | BLOCKED_NO_SEND | 6896 | 8396 |
| unique_long | 20 | BLOCKED_NO_SEND | 42760 | 44260 |
| normal_repeated | 30 | ADMITTED_OFFLINE | 6353 | 7853 |
| out_of_domain | 30 | ADMITTED_OFFLINE | 6374 | 7874 |
| meal_requests | 30 | ADMITTED_OFFLINE | 6380 | 7880 |
| long_repeated | 30 | BLOCKED_NO_SEND | 6896 | 8396 |
| unique_long | 30 | BLOCKED_NO_SEND | 60980 | 62480 |

Les répétitions exactes tiennent avec un coût stable grâce aux compteurs ; les
contraintes uniques restent toutes présentes et conduisent à un refus explicite.
Les demandes longues répétées échouent malgré la déduplication : les deux paires
récentes intouchées consomment encore trop. Elles ne sont pas supprimées pour
obtenir un résultat favorable.

Stress séquentiel mixte : taille, ajout de maïs, retrait autorisé, hors domaine,
retour au repas avec demande plus longue, puis répétition du cycle. Les étapes
admises sont appliquées au moteur et leur paire rejoint le journal ; les refus
ne modifient ni repas ni journal. Toutes les tentatives prévues sont exécutées.

| Tentatives prévues et exécutées | Admises localement | Bloquées sans envoi | Premier blocage |
| ---: | ---: | ---: | --- |
| 10 | 7 | 3 | Tentative 8 : entrée candidate 6 538 >6 500 |
| 20 | 7 | 13 | Tentative 8 : entrée candidate 6 538 >6 500 |
| 30 | 7 | 23 | Tentative 8 : entrée candidate 6 538 >6 500 |

Aucun candidat admis n’excède 6 500 d’entrée / 8 000 de budget total. Cela garantit
**la borne du plan local pour les envois autorisés**, pas que toutes les conversations
continuent. Seulement sept tours du parcours mixte sont acceptés ; les 10/20/30
conversations ne sont donc pas déclarées réussies de bout en bout.

## 6. Tests et reproduction

**104 tests backend réussis** (99 conservés + 5 tests prototype couvrant A–J,
configuration, stress et sécurité). **17 tests frontend réussis**, TypeScript/build
OK. Le contrôle de sortie ajouté au prototype a également été vérifié par une
réexécution des cinq tests ciblés. Warning de taille du bundle 3D inchangé.

```sh
cd /Users/mohamedb/Downloads/12-koul
PYTHONPATH=. TIKTOKEN_CACHE_DIR=/tmp/koul-tiktoken-cache /tmp/koul-backend-venv/bin/python -B tools/check_history_budget.py
TIKTOKEN_CACHE_DIR=/tmp/koul-tiktoken-cache /tmp/koul-backend-venv/bin/python -B -m unittest discover -s backend/tests
npm --prefix frontend test
npm --prefix frontend run build
```

Fichiers ajoutés uniquement :
- `tools/history_budget_prototype.py` : planification/admission/archivage réversible.
- `tools/check_history_budget.py` : mesures A–J et stress, snapshots et budgets JSON.
- `backend/tests/test_history_budget.py` : cinq tests hors ligne.
- Ce rapport.

## 7. Groq et décision de production

**GROQ LIVE = NOT RUN**. `.env` et GROQ_API_KEY absents au contrôle. Zéro appel réel,
aucun HTTP provider, usage d’entrée/sortie ou résultat sémantique inventé. Les trois
cas ciblés ajout/modification/suppression après historique long restent à tester
lorsque les credentials locaux seront disponibles, sans relancer les 42 scénarios.

**Pas d’activation en production.** Les tests démontrent la conservation et
l’admission déterministes, mais pas une stratégie suffisamment utilisable et
comprise par le provider réel :

1. Le journal complet est indispensable avant archivage ; la fenêtre actuelle a
   déjà pu supprimer des informations. L’intégration au stockage RAM demanderait
   un changement explicite, sans prétendre restaurer ce qui est perdu.
2. Compréhension réelle de l’archive, continuité de langue, traitement des questions
   non résolues et résistance à une injection ancienne restent non validés.
3. Le refus au huitième tour du stress mixte est trop restrictif pour considérer
   le parcours long comme stabilisé. Modifier uniquement les chiffres risquerait
   de consommer la marge de sortie ; supprimer du texte risquerait de perdre des
   contraintes. Un éventuel registre de préférences explicitement validées par
   l’utilisateur est une piste, pas une fonctionnalité implémentée.
4. Une limite de génération effective, l’usage du raisonnement, le rejet des sorties
   tronquées et le débit de toutes les conversations doivent être pris en compte
   côté provider/application. Le contrôle local de sortie ne protège pas le TPM
   déjà consommé. Le quota fournisseur actuel et la marge restent à recalibrer.

**Verdict final : NEEDS FIXES.** Prototype déterministe conservateur validé localement,
mais garantie end-to-end et continuité d’usage non établies. Aucun changement de
prompts, provider, moteurs, règles, actions, runner, SaladScene ou catégories.
