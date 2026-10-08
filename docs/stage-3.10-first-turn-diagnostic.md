# Stage 3.10 — Diagnostic du premier tour

## Périmètre et méthode

Uniquement le défaut de création différée du brouillon. Modèle réel Groq
`openai/gpt-oss-120b`, température 0, format JSON, route `/chat` de FastAPI via
`TestClient` ASGI et transport HTTPS réel du provider existant. Aucun mock pour
les observations live. La clé est lue depuis `.env` dans l'environnement du
processus ; aucune clé ni aucun header d'authentification n'est enregistré.
Sélection `LLM_PROVIDER=groq` limitée au processus de diagnostic.

Plafond global : cinq requêtes HTTP réelles, retries désactivés dans le processus
pour ne pas dépasser ce plafond, espacement de 65 secondes après chaque réponse.
Deux reproductions dans deux conversations neuves, puis une conversation de trois
tours après correction. Le dernier tour combine retrait et recommandation pour
couvrir les deux actions sans dépasser cinq appels. Ce n'est pas un test isolé
supplémentaire de recommandation. Aucune évaluation des 42 scénarios relancée.

## Cause et localisation

Les deux reproductions avant correction renvoient exactement le même JSON avec
`actions: []`. Le message demande les bases, ingrédients, toppings et sauces
manquants avant de proposer la moindre mutation. Le repas reste vide, HTTP 200,
`accepted=true`, `error=null`.

- **A — Modèle :** l'absence d'actions existe déjà dans le contenu brut retourné
  par Groq. Ce n'est pas une perte après génération.
- **B — Parsing :** `CompatibleProvider.complete` retourne le contenu de
  `choices[0].message.content`. `validate_response` conserve le tableau vide ;
  le nouveau test vérifie également la conservation d'un lot non vide à travers
  le provider, FastAPI et le moteur.
- **C — Validation :** aucun rejet lors des reproductions. `validate_state`
  vérifie les maximums ; `completeness` contrôle les minimums. Le moteur permet
  les brouillons partiels et interdit leur confirmation prématurée.
- **D — Autorisation :** `SET_CATEGORY`, `SET_SIZE` et `ADD_ITEM` ne sont pas des
  actions protégées. Le mode initial est bien `composition`. Aucun grant ne
  manque pour construire ce brouillon. Le retrait reste soumis au grant exact
  par item et révision ; cette protection n'a pas changé.
- **E — Initialisation :** état vide et historique vide attendus, message utilisateur
  transmis une seule fois. Pas de branche spéciale bloquant le premier tour.
  Le tour suivant passe par les mêmes fonctions, avec l'historique précédent et
  l'état validé ; dans le test antérieur, cet historique permettait au modèle de
  récupérer l'intention non appliquée. La réponse du modèle était la différence
  fonctionnelle, pas un autre chemin d'application des actions.
- **F — UI/API :** inspection de `KOOLChat`, `useConversation`, `chatApi` et
  `ChatRequest` : seul un `trim` des espaces externes s'applique à ce message.
  Aucun remplacement spécifique au premier tour. Cette vérification est une
  inspection de code, pas une nouvelle saisie live dans l'interface principale.

La cause observable est donc une décision du modèle de différer toutes les
mutations jusqu'à clarification de la composition. Le déclencheur textuel
identifié dans V3 est la règle « Respecte les min/max exacts, sans doublons » :
elle ne distinguait pas explicitement les minimums de confirmation et les choix
partiels enregistrables. La règle de clarification « sans action spéculative »
pouvait renforcer cette interprétation. Les détails internes du raisonnement
du modèle ne sont pas prouvables ; la reproduction et le changement contrôlé
ci-dessous testent cette explication, sans attribuer un bug au provider.

## Correction minimale

Insertion après « Respecte les min/max exacts, sans doublons. » :

> En mode composition, propose dès ce tour les choix explicites et non ambigus,
> même si le brouillon est incomplet. Les minimums conditionnent la confirmation,
> pas l’enregistrement des choix partiels ; demande ensuite les choix manquants
> sans les inventer.

Cette précision correspond au comportement préexistant du moteur. Aucun exemple
lexical salade/poulet/tomate, aucune détection hardcodée et aucun ajout d'actions
par le backend. Les actions continuent de venir du modèle. Le mode information,
les ambiguïtés réelles, les maximums, la sécurité, le grounding et les autorisations
restent soumis aux règles inchangées.

V1/V2, provider, schéma d'actions, format compact, moteurs, budget/history,
scénarios d'évaluation et SaladScene : inchangés. Le V3 corrigé n'est pas
strictement le même artefact que le V3 de l'évaluation historique des 42 réponses ;
ces résultats historiques n'ont pas été réécrits ni présentés comme une validation
de cette révision.

## Tests locaux

- `TIKTOKEN_CACHE_DIR=/tmp/koul-tiktoken-cache /tmp/koul-backend-venv/bin/python -B -m unittest discover -s backend/tests` : **112 tests passent**.
- `npm test` dans `frontend` : **17 tests passent** (13 Vitest + 4 Node).
- `npm run build` dans `frontend` : **TypeScript et build passent**. Avertissement
  préexistant sur un chunk 3D supérieur à 500 kB ; aucune optimisation hors sujet.
- Nouveau test `test_first_turn.py` : conservation du JSON/action batch vide ou
  non vide via le provider compatible, contexte initial en composition, message
  inchangé, acceptation d'un brouillon incomplet sans le rendre commandable.
  Il protège le contrat déterministe, pas la sémantique d'un modèle simulé.
- Le premier passage de la suite a détecté une valeur de taille de prompt figée
  dans `test_context_continuity.py` : 6538 devient 6596 (+58 tokens estimés).
  Seule cette attente est actualisée ; les assertions de budget et les quinze
  tours de continuité restent intacts et passent.

## Résultats réels avant/après

Provider réel : `openai/gpt-oss-120b`. Les tokens ci-dessous viennent de Groq,
incluant les tokens de raisonnement dans la sortie. Durée = transport provider.

| Essai | HTTP API / Groq | Entrée | Sortie | Total | Durée | Actions |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Avant 1, neuve | 200 / 200 | 5733 | 367 | 6100 | 1.961 s | [] |
| Avant 2, neuve | 200 / 200 | 5733 | 367 | 6100 | 1.594 s | [] |
| Après 1, neuve | 200 / 200 | 5791 | 482 | 6273 | 1.676 s | SET_CATEGORY:salad, SET_SIZE:large, ADD_ITEM:salad.ingredient.grilled_chicken, ADD_ITEM:salad.ingredient.tomato |
| Après 2, même conversation | 200 / 200 | 5883 | 381 | 6264 | 1.661 s | ADD_ITEM:salad.ingredient.corn |
| Après 3, même conversation | 200 / 200 | 5960 | 470 | 6430 | 1.635 s | REMOVE_ITEM:salad.ingredient.tomato, RECOMMEND_ITEM:drink.drink.coca_cola |

Les cinq lots sont acceptés ; aucun rejet de validation, 429, 413 ou timeout.
Avant : deux repas vides. Après : grande salade poulet/tomate dès le premier
tour, puis maïs ajouté, puis tomate retirée. Le choix conseillé reste une
recommandation, sans ajout automatique. Bases, toppings et sauces restent vides,
donc la salade reste incomplète et ne peut pas être confirmée.

### Réponses structurées brutes et états validés

Ces extraits sont les contenus JSON réels de Groq, sans header ni clé.

#### Appel 1

Utilisateur : Je veux une grande salade avec poulet et tomate.

```json
{
  "message": "Super choix ! Pour votre grande salade, il faut 2 bases, 5 ingrédients, 3 toppings et 2 sauces. Vous avez déjà choisi le poulet grillé et la tomate. Pouvez‑vous me dire :\n- Les 2 bases que vous voulez (ex. laitue, épinards, roquette, chou rouge) ?\n- 3 autres ingrédients parmi les options disponibles (ex. concombre, maïs, avocat, œuf, mozzarella, etc.) ?\n- Vos 3 toppings préférés (ex. croûtons, noix, graines de sésame, etc.) ?\n- Vos 2 sauces favorites (ex. César, algérienne, miel‑moutarde, citron‑herbes, ranch).",
  "actions": []
}
```

État après validation :
```json
{"active_category": null, "categories": {}}
```

#### Appel 2

Utilisateur : Je veux une grande salade avec poulet et tomate.

```json
{
  "message": "Super choix ! Pour votre grande salade, il faut 2 bases, 5 ingrédients, 3 toppings et 2 sauces. Vous avez déjà choisi le poulet grillé et la tomate. Pouvez‑vous me dire :\n- Les 2 bases que vous voulez (ex. laitue, épinards, roquette, chou rouge) ?\n- 3 autres ingrédients parmi les options disponibles (ex. concombre, maïs, avocat, œuf, mozzarella, etc.) ?\n- Vos 3 toppings préférés (ex. croûtons, noix, graines de sésame, etc.) ?\n- Vos 2 sauces favorites (ex. César, algérienne, miel‑moutarde, citron‑herbes, ranch).",
  "actions": []
}
```

État après validation :
```json
{"active_category": null, "categories": {}}
```

#### Appel 3

Utilisateur : Je veux une grande salade avec poulet et tomate.

```json
{
  "message": "Grande salade sélectionnée. Il nous manque 2 bases, 3 ingrédients, 3 toppings et 2 sauces. Quels choix souhaitez‑vous ajouter ?",
  "actions": [
    {
      "type": "SET_CATEGORY",
      "category": "salad"
    },
    {
      "type": "SET_SIZE",
      "size": "large"
    },
    {
      "type": "ADD_ITEM",
      "item_id": "salad.ingredient.grilled_chicken"
    },
    {
      "type": "ADD_ITEM",
      "item_id": "salad.ingredient.tomato"
    }
  ]
}
```

État après validation :
```json
{"active_category": "salad", "categories": {"salad": {"type": "salad", "size": "large", "slots": {"base": [], "ingredient": ["salad.ingredient.grilled_chicken", "salad.ingredient.tomato"], "topping": [], "sauce": []}}}}
```

#### Appel 4

Utilisateur : Ajoute du maïs.

```json
{
  "message": "Maïs ajouté. Il manque encore 2 bases, 2 ingrédients, 3 toppings et 2 sauces. Quels choix souhaitez‑vous ajouter ?",
  "actions": [
    {
      "type": "ADD_ITEM",
      "item_id": "salad.ingredient.corn"
    }
  ]
}
```

État après validation :
```json
{"active_category": "salad", "categories": {"salad": {"type": "salad", "size": "large", "slots": {"base": [], "ingredient": ["salad.ingredient.grilled_chicken", "salad.ingredient.tomato", "salad.ingredient.corn"], "topping": [], "sauce": []}}}}
```

#### Appel 5

Utilisateur : Enlève la tomate. Et conseille-moi une boisson.

```json
{
  "message": "Tomate retirée. Pour votre boisson, je vous recommande un Coca‑Cola rafraîchissant.",
  "actions": [
    {
      "type": "REMOVE_ITEM",
      "item_id": "salad.ingredient.tomato"
    },
    {
      "type": "RECOMMEND_ITEM",
      "item_id": "drink.drink.coca_cola"
    }
  ]
}
```

État après validation :
```json
{"active_category": "salad", "categories": {"salad": {"type": "salad", "size": "large", "slots": {"base": [], "ingredient": ["salad.ingredient.grilled_chicken", "salad.ingredient.corn"], "topping": [], "sauce": []}}}}
```

## Risques restants et verdict

**READY FOR CATEGORY EXPANSION**, pour ce blocage de premier tour : il est
reproduit avant la clarification et absent lors du premier tour corrigé ; ajout,
retrait autorisé et recommandation fonctionnent ensuite. Ce verdict ne vaut pas
validation exhaustive de toutes les conversations ni des catégories à construire.

Limites : deux reproductions avant et un seul premier tour après correction,
un modèle, température 0, aucun test utilisateur. Une répétition future peut
produire une autre réponse ; aucune garantie statistique ne découle de cinq appels.
La recommandation est testée conjointement avec le retrait, pas dans un quatrième
tour isolé. Aucun nouveau test visuel SaladScene ni parcours chat navigateur live.

Le texte du modèle dit notamment « Grande salade sélectionnée » et « Maïs ajouté »
au lieu de présenter systématiquement des propositions. Les actions sont bien
acceptées ici, mais ce ton affirmatif reste une limite préexistante : le frontend
doit continuer à distinguer texte non fiable et faits déterministes. Aucun
changement hors sujet n’a été tenté pour corriger ce point.

Les mesures historiques de taille du contexte ont changé de +58 tokens d’entrée
sur le premier tour (5733 → 5791). Aucun budget ni historique n’a été modifié.

## Fichiers modifiés

- `backend/app/prompts/prompt_v3.txt` : clarification générale minimale.
- `backend/tests/test_first_turn.py` : régression provider/API/brouillon partiel.
- `backend/tests/test_context_continuity.py` : actualisation de la seule mesure figée.
- `docs/stage-3.10-first-turn-diagnostic.md` : ce rapport.
- `notebook/first-turn-diagnostic.local.json` : observations réelles et hashes avant/après, fichier local ignoré.

Les résultats bruts et les hashes sont dans [l’artefact local](../notebook/first-turn-diagnostic.local.json).
