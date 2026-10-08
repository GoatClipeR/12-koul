# Architecture future — préparation uniquement

Ce document conserve la préparation réalisée avant la Phase 2. Depuis, le backend
FastAPI local, les trois endpoints, la mémoire de conversation et l’intégration V3
ont été implémentés et testés hors ligne : voir le [README actuel](../README.md)
pour les contrats HTTP effectivement disponibles. Le branchement UI chat/3D reste
à réaliser. Les paragraphes prospectifs ci-dessous décrivent la cible initiale.

## Trajet d’un message

```text
User
 ↓
React Chat UI
 ↓ POST /chat
FastAPI
 ↓ message + historique + contexte du repas et du menu
Provider LLM
 ↓ réponse structurée
Structured actions
 ↓ parsing, validation du contrat et autorisations applicatives
Deterministic meal engine
 ↓ état accepté + devis déterministe
Meal state
 ↓ réponse API
React state
 ↓ projection des IDs du menu
R3F / Three.js
 ↓ assets GLB
3D scene
```

Le LLM propose des actions et du texte. **Il ne manipule jamais directement
Three.js**, la caméra, les matériaux, les assets ou le state React. Les instructions
du modèle ne deviennent jamais du code à exécuter dans le navigateur.

## Responsabilités prévues

| Couche | Responsabilité |
| --- | --- |
| React Chat UI | Saisie, historique visible, attente, erreurs et nouvelle conversation |
| FastAPI | Validation des entrées, isolation des conversations, orchestration et erreurs fournisseur |
| Provider | Appel au modèle avec les secrets conservés côté serveur |
| Contrat d’actions | Parser les réponses, rejeter les formes inconnues, vérifier les autorisations |
| Moteur déterministe existant | Menu, quotas, compatibilité de taille, prix, état et confirmation |
| React state | Recevoir l’état accepté du serveur et partager ce snapshot avec les vues |
| SaladScene | Projection visuelle en lecture seule, sans règles métier ni parsing de réponse LLM |

Le serveur restera la source de vérité du repas. Une réponse invalide ou un lot
rejeté conservera l’état précédent ; un échec fournisseur ne créera aucune action
mock. Le texte affiché devra distinguer une proposition du modèle d’une modification
effectivement acceptée. La confirmation ne signifiera pas un paiement ou un envoi
en cuisine.

## Interface envisagée, à spécifier avant implémentation

Le TP prévoit `GET /health`, `POST /chat` et
`DELETE /chat/{conversation_id}`. Une mémoire serveur par conversation suffit.
Le POST transmettra le message et l’identifiant de conversation ; le serveur
retrouvera lui-même l’historique et le repas, sans considérer un état envoyé par
le client comme autorité métier.

La réponse devra distinguer message, résultat de validation, état accepté, devis
et éventuelle erreur. Les autorisations d’actions protégées viendront de
l’application, jamais d’un texte LLM. Le format HTTP exact reste à définir en
Phase 2 ; le contrat structuré et les règles existants restent inchangés.

Le reset devra effacer historique et repas de la conversation concernée, puis
mettre à jour React et la scène. Les requêtes d’une même conversation devront
être ordonnées et les réponses devenues obsolètes après un reset ignorées.
Deux conversations devront rester isolées. Timeouts et erreurs afficheront un
message compréhensible tout en conservant le dernier état accepté.

## Préparation et validations à venir

Réutiliser le moteur, le menu et la projection `projectMeal` existants. Conserver
Three.js/R3F et les GLB ; un ID sans asset reste signalé comme non représenté,
sans inventer un ingrédient. Le chargement différé 3D existe déjà.

La salade est **TECHNICAL VERTICAL SLICE = VALIDATED** et **ART DIRECTION = NEEDS
POLISH**. Cela ne valide pas encore l’intégration réseau ni les performances sur
téléphone réel. Voir [les limites 3D](3d-architecture.md).

Lors du démarrage autorisé de Phase 2, vérifier le dialogue multi-tour de bout en
bout, le reset, les messages vides, l’isolation, les erreurs et timeouts, les lots
rejetés sans mutation et la synchronisation du repas avec la scène. Aucun de ces
tests futurs n’est présenté comme exécuté ici. L’évaluation Groq séparée reste
intacte ; ses métriques structurelles ne choisissent pas le prompt de production.

## Stage 3 — expérience React principale

L’entrée `frontend/index.html` charge maintenant l’expérience restaurant. Pas de
réponse simulée dans le code applicatif : chaque message part vers FastAPI.

```text
KOOLChat → useConversation → chatApi.sendMessage → POST /chat
→ provider V3 → actions → moteur existant → état/devis/faits
→ vérification du contrat HTTP → état React
→ Composition + MealScene → SaladScene existante
```

### Composants et responsabilités

- `src/components/App.tsx` : header, catégories futures désactivées, repas discret,
  nouveau chat et composition de la page.
- `src/chat/KOOLChat.tsx` : historique affiché, saisie labellisée, Entrée/Maj+Entrée,
  chargement, erreurs et retry. Suggestions du modèle distinctes des faits serveur.
- `src/api/chatApi.ts` : POST/DELETE centralisés, schémas Zod du contrat consommé,
  contrôle ID/révision/statut, timeout 130 s (supérieur au maximum provider 120 s).
- `src/state/useConversation.ts` : UUID en mémoire, dernier snapshot backend,
  révision, une requête à la fois. Aucune mutation optimiste du repas.
- `src/meal/Composition.tsx` : noms reçus dans `display.facts.selected_items`,
  progression, complétude et devis serveur. Aucun catalogue ou prix en dur.
- `src/3d/MealScene.tsx` : chargement différé de la seule SaladScene, état vide,
  fallback et signalement des produits sans asset. Le point de dispatch est prêt
  pour des scènes futures, mais aucun composant Sandwich/Plat/Drinks fictif n’existe.

### Progression et vérité métier

L’API ne transmet pas le catalogue des quotas. Pour les salades à taille connue,
le nombre de places est déduit des IDs sélectionnés **plus** le nombre manquant
fourni par `quote.missing`, par slot. Cela reflète les règles actuelles exactes du
moteur (min=max) sans recopier 1/2/1/1 ou 2/5/3/2 dans React. Avant la taille,
aucun quota n’est inventé. Si le backend évolue vers des quotas optionnels min/max,
il devra exposer explicitement ces bornes : cette projection devra alors évoluer.

Le prix affiché est `quote.total` en MAD, seulement si le serveur fournit une ligne
et un montant. Une sélection sans taille n’a pas de prix inventé. Le bouton de
validation dépend de `quote.orderable`, transmet `confirm_composition=true` et la
révision affichée ; aucune commande externe. Le reset DELETE doit réussir avant
l’effacement local, puis un nouvel UUID est créé.

Sur erreur réseau/timeout, l’état affiché est conservé. Un retry réutilise la révision
connue : si la première demande avait abouti, le serveur refuse le doublon par 409.
L’API ne dispose pas encore de GET de resynchronisation : une nouvelle conversation
peut être nécessaire après ce cas. Un échec de validation de réponse n’introduit
aucun nouveau repas local. Un tour rejeté valide conserve le repas et fait avancer
la révision serveur. L’historique local n’est pas persisté après rechargement.

### Responsive et accessibilité

Desktop : chat gauche, scène centrale/droite, composition sous la scène.
Sous 800 px : scène en haut, composition puis chat. Navigation compacte, retour
à la ligne des slots sur 390 px. Polices Bricolage Grotesque/Figtree, logo officiel
et couleurs du projet. Focus visible, formulaire labellisé, log et erreurs annoncés,
texte React échappé, boutons désactivés pendant la requête, reduced motion respecté.

La page locale `experience-review.html` (hors build production) permet d’inspecter
390 × 844, 768 × 1024 et 1390 × 844 dans un iframe unique pour éviter trois contextes
WebGL simultanés. Aucun mock n’est inclus dans cette page.

### Lancement et tests

Backend : commandes du README, port 8000. Frontend :

```sh
npm --prefix frontend install
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173
npm --prefix frontend test
npm --prefix frontend run build
```

API par défaut : `http://127.0.0.1:8000`. Override optionnel dans
`frontend/.env.local` : `VITE_API_BASE_URL=http://127.0.0.1:8000` (aucun secret).
Si le port frontend change, ajouter cette origine à CORS_ORIGINS côté serveur.
URLs : `/` (expérience), `/experience-review.html` (QA), `/salad.html` (slice préservée).

Tests React/API avec fixtures générées depuis les vrais contrats FastAPI et moteur,
provider de test uniquement : affichage chat, POST, loading, erreurs, réponse
invalide, timeout, reset réussi/échoué, renouvellement d’ID, prix, progression,
confirmation explicite, projection d’un changement de taille/retrait reçu.
La scène est remplacée par un composant témoin dans les tests React ; les quatre
tests de projection/assets/animation existants restent distincts. Les tests DOM ne
mesurent pas WebGL ou les performances mobiles.

### Limites conservées

Stage 3.5 ajoute le retrait explicite via × dans la composition : POST /chat reçoit
`remove_item_id` et la révision affichée. Le serveur vérifie sa présence dans le
brouillon actif avant de construire une autorisation exacte liée à l’état. La
politique et le moteur existants valident ensuite les actions du modèle. Un texte
seul reste insuffisant ; ni CLEAR_MEAL ni CLEAR_CATEGORY ne sont autorisés. Un changement de taille doit
être accepté par le moteur ; les conflits ne suppriment rien automatiquement.
Les autres catégories restent à venir ; un brouillon non-salade ne crée pas une
nouvelle scène. Les GLB et SaladScene n’ont pas été reconstruits.

Le chemin Groq applicatif complet reste à valider en live sous la limite TPM ;
aucun appel d’évaluation n’a été relancé. Le mode mock du backend est signalé comme
tel ; il ne constitue pas une preuve de compréhension réelle. Aucun paiement,
authentification, cuisine, nouvelle technologie d’assets ou nouvelle catégorie.

### Vérification Stage 3 — 8 octobre 2026

- Backend : 93 tests unittest réussis, sans appel Groq.
- Frontend : 12 tests Vitest et 4 tests Node existants réussis ; TypeScript et build Vite réussis.
- Inspection navigateur des dispositions 390 × 844, 768 × 1024 et 1390 × 844 via la page QA locale. Correction du défilement du chat pour ne plus déplacer toute la page, et réduction de la hauteur du hero desktop.
- Parcours réellement observé dans Brave via les routes FastAPI et un provider de test temporaire explicitement mock : grande salade poulet/tomate, puis ajout de maïs ; conservation des ingrédients, progression 2/5 → 3/5, devis moteur 55 MAD. Le frontend ne contient pas de réponses simulées.
- Rendu desktop observé avec bol, poulet, tomate et maïs après le deuxième tour. Le navigateur a aussi présenté un fallback WebGL pendant la session ; ce contrôle ne constitue pas une mesure de stabilité GPU ni de performances sur appareil mobile.
- Le reset est couvert par les tests automatisés ; sa tentative manuelle n’a pas permis de confirmer le résultat visuellement.
- Le chargement 3D reste différé, mais Vite signale encore un chunk partagé d’environ 1,15 Mo minifié (343 Ko gzip). Aucun benchmark mobile n’a été réalisé.
- Aucun appel réel Groq ni modification des prompts, scénarios, moteur ou provider pendant cette étape. Le provider temporaire de QA est arrêté après vérification.

La QA Stage 3.5 et ses limites sont consignées dans [stage-3.5-integration-qa.md](stage-3.5-integration-qa.md).

### Stage 3.6 — encodage du contexte applicatif

FastAPI active désormais un encodage compact sans perte après `build_messages` :
menu complet en tableau de colonnes, enums du schéma factorisées et JSON compact.
Prompt V3, historique, règles et validation inchangés. Le provider et le chemin
évaluation ne changent pas. Voir [le rapport Stage 3.6](stage-3.6-production-integration-check.md)
pour les mesures (5 631 tokens de contenu au premier tour), les 97 tests backend,
le statut Groq **NOT RUN** et le risque persistant des historiques longs.
