# 12-KOUL — Rapport final

## 1. Présentation

12-KOUL est un prototype universitaire de restaurant assisté par KOOL AI : Salad
Bar, Sandwich, Plats et Boissons. L’utilisateur compose dans le chat, voit son
repas et prépare un panier. Il s’agit d’une simulation, sans commande externe.

## 2. Objectif

Livrer les quatre catégories sur l’architecture existante, conserver Salad et
rendre les prix, suppressions, confirmations et erreurs déterministes. La finition
n’a pas relancé la campagne de 42 scénarios ni créé une seconde intégration LLM.

## 3. Architecture

Utilisateur → React → `POST /chat` → provider Groq/V3 → actions structurées →
validation du schéma et des autorisations → moteur de repas + panier applicatif →
prix backend → réponse validée Pydantic → React → R3F.

Les décisions directes des boutons panier sont également validées côté backend,
avec la révision de conversation. Elles ne sont pas des intentions devinées dans
le texte. Le modèle ne manipule jamais Three.js ni le DOM.

## 4. Chatbot spécialisé

Domaine : compositions et recommandations du menu 12-KOUL. Les réponses générales,
produits inventés, prix arbitraires et demandes sensibles ne sont pas des capacités
autorisées. Le texte du modèle reste marqué non fiable ; les faits issus du moteur
font autorité. Le provider mock de base ne produit qu’un accueil, sans prétendre
comprendre une commande.

## 5. Prompt V3

V3 reste celui du diagnostic du premier tour : les choix explicites et non ambigus
peuvent constituer immédiatement un brouillon incomplet. **Aucun changement final
à V1/V2/V3.** Une modification envisagée de la phrase boisson a été retirée : un
produit par brouillon reste correct, chaque brouillon boisson étant maintenant
transféré immédiatement dans une ligne séparée.

Le contexte applicatif `CART_CONTEXT`, présent uniquement en mode panier, décrit
ces lignes et le transfert automatique. Il ne modifie ni le schéma d’actions ni
les règles de slots. Les huit actions existantes sont conservées.

## 6. Gestion du contexte

Contexte compact existant : JSON compact, définitions de schéma factorisées,
menu complet tabulaire. L’historique réel est transmis au provider. Le panier est
inclus dans le contexte du mode panier. Aucun prix ni état n’est inféré du texte
libre de l’assistant. Conversations et paniers sont isolés en mémoire par identifiant.

Le chemin HTTP conserve sa fenêtre de 40 messages / 16 000 caractères. Les
prototypes de mémoire déterministe précédents sont des outils locaux et ne sont
pas présentés ici comme une summarization HTTP déployée. Un panier volumineux ou
un historique long reste un risque de dépassement TPM.

## 7. Validation déterministe

Le moteur générique et `price_engine.py` sont conservés :

- Sandwich : pain, protéine et sauce obligatoires ; fromage 0–1, légumes 0–3,
  extras 0–2, selon `menu.json`.
- Plats : protéine, accompagnement et sauce obligatoires.
- Boisson : un produit par brouillon, immédiatement ajouté à sa propre ligne de
  panier. Les boissons répétées ont des identifiants de ligne distincts.
- Salad : quotas et prix existants inchangés.

Le service applicatif `cart.py` utilise `validate_response`, `check_policy`,
`apply_action`, `quote` et `price_cart`. Il traite une copie du repas/panier et ne
publie que le résultat complet validé. Un lot partiellement invalide ne modifie
rien. Une suppression LLM exige l’autorisation exacte ; deux boissons identiques
nécessitent la suppression UI de la ligne exacte. Maximum 40 lignes.

`quote` concerne les brouillons et `cart.total` les lignes réellement ajoutées.
Exemple testé : salade 35 + sandwich 38 + plat 55 + Coca-Cola 10 + orange 15 =
**153 MAD**. Retirer la salade donne **118 MAD**. Les calculs proviennent du backend.

## 8. FastAPI

`GET /health`, `GET /menu`, `POST /chat`, `DELETE /chat/{conversation_id}`.
Entrées/sorties Pydantic, timeouts provider bornés, erreurs publiques sans secrets,
CORS local, contrôle de révision et exclusion des accès concurrents à une conversation.

Le frontend envoie `cart_mode: true`. Le mode historique est préservé pour les
anciens clients/tests. Une conversation panier ne peut pas repasser implicitement
en mode historique. `cart_command` permet l’ajout d’un brouillon complet, la
suppression d’une ligne et la confirmation finale simulée. Les cibles et la révision
sont validées. La confirmation finale demande un panier non vide, sans brouillon
restant. Aucun endpoint de paiement ou de cuisine n’existe.

## 9. React

Navigation des quatre catégories, chat commun, composition par slot, progression,
prix de la catégorie fourni par le backend, panier, total, suppression, confirmation,
loading, retry et reset. Les boissons disposent de boutons qui passent par le chat
et la validation du modèle. Le catalogue affiché provient du même `menu.json` ;
aucun calcul de prix n’est effectué dans React.

QA native dans Brave avec l’application réellement servie par Vite et FastAPI,
provider de test explicitement signalé, dans des viewports de **390×844, 768×1024,
1390×844**. Il ne s’agit pas de mesures sur appareils physiques.

Parcours constatés : salade complète et composition mobile ; sandwich et plat ;
ajout des compositions au panier ; deux boissons ; panier de 118 MAD ; confirmation
« aucune commande envoyée en cuisine » ; suppression du Coca-Cola (108 MAD) ; reset
avec disparition de l’historique et retour du panier à zéro. Les tests React
couvrent aussi le parcours réunissant les quatre catégories dans un même panier.

Corrections visuelles ciblées : slots optionnels présentés comme optionnels avec
leur maximum menu, prix affiché pour la catégorie sélectionnée, accès direct au
chat en mobile. Aucun redesign général.

## 10. Three.js / React Three Fiber

SaladScene et ses assets restent inchangés. Ajout de `SandwichScene` et `PlatsScene`,
avec géométries procédurales, matériaux standard rugueux, éclairage chaud, ACES,
ombres de contact, contrôles orbitaux et chargement différé. Les éléments apparaissent
uniquement selon les slots du meal state validé. Boissons : illustration CSS légère.

Les scènes Sandwich et Plats ont été réellement vues dans le navigateur. Ce sont
des représentations stylisées simples, pas des assets photographiques. La QA a
rencontré une erreur de démontage d’une racine React lors d’un changement de scène ;
le conteneur conserve désormais les canvases déjà visités montés et masque les
inactifs. Un test protège cette stabilité. Cela conserve jusqu’à trois contextes
3D : performances mobiles physiques non mesurées. Un avertissement de dépréciation
`THREE.Clock` a été observé dans les dépendances ; pas de refonte hors périmètre.

Le fallback WebGL conserve la composition textuelle. Le plus gros chunk 3D reste
supérieur à 500 kB ; les scènes sont séparées et chargées à la demande. Aucun FPS
avancé ou benchmark matériel n’est revendiqué.

## 11. Menu

`backend/app/data/menu.json` demeure la seule source de vérité des produits,
identifiants, slots, prix et allergènes suivis. Aucun produit, prix, disponibilité
ou valeur nutritionnelle ajouté pour faciliter la démonstration. Les représentations
visuelles ne constituent pas une preuve de disponibilité ou d’absence d’allergènes.

## 12. Tests

Dernière exécution : **122 tests backend passent**, plus **4 tests de revue
sémantique** ; **20 tests frontend passent** (16 Vitest + 4 Node) ; **TypeScript
et build Vite passent**. Tous les tests existants ont été conservés.

Commandes :

```sh
TIKTOKEN_CACHE_DIR=/tmp/koul-tiktoken-cache /tmp/koul-backend-venv/bin/python -B -m unittest discover -s backend/tests
/tmp/koul-backend-venv/bin/python -B -m unittest tools.test_semantic_review
cd frontend
npm test
npm run build
```

Les chemins `/tmp` correspondent à l’environnement local de validation ; le README
fournit les commandes avec un virtualenv standard. Les corrections finales n’ont
modifié ni `meal_engine.py`, ni `price_engine.py`, ni les sources de SaladScene.

Tests ajoutés : catégories complètes/incomplètes, limites Sandwich, retrait autorisé,
prix, deux boissons, boissons répétées, suppression exacte, atomicité, indépendance
des conversations, limite panier, panier multicatégorie, confirmation, reset et
révisions périmées. Tests React : quatre catégories vers panier, total backend,
suppression de ligne et conservation des racines de scènes.

## 13. Évaluation réelle Groq

Archives Phase 1 : 42 réponses réelles, V1 8 PASS / 3 PARTIAL / 3 FAIL,
V2 11 / 2 / 1, V3 11 / 3 / 0. Ces résultats historiques n’ont pas été régénérés.

Finalisation : **trois nouvelles requêtes réelles seulement**, espacées de 65 secondes,
via FastAPI ASGI TestClient et le provider HTTPS Groq existant. Aucun mock dans ces
observations. Les opérations intermédiaires d’ajout au panier sont déterministes,
sans appel LLM.

| Demande | HTTP | Entrée | Sortie | Total tokens | Durée API |
| --- | --- | ---: | ---: | ---: | ---: |
| Sandwich poulet / baguette / algérienne | 200 | 5899 | 476 | 6375 | 1,689 s |
| Plat poulet / frites / barbecue | 200 | 6062 | 340 | 6402 | 1,313 s |
| Coca-Cola + jus d’orange | 200 | 6200 | 337 | 6537 | 1,698 s |

Les deux compositions sont complètes et ajoutées au panier. Les boissons produisent
chacune `SET_CATEGORY drink` puis `ADD_ITEM` et deux lignes indépendantes. Panier
final réel : **quatre lignes, 118 MAD**. Aucun 413, 429 ou timeout sur ces trois appels.
Preuve locale ignorée par Git : `notebook/final-integration.local.json`, sans clé
ni header d’authentification. Aucun parcours utilisateur navigateur→Groq nouveau
n’est revendiqué : la QA navigateur utilise le provider de test, la QA réelle
passe par les routes ASGI.

## 14. Limites

- Simulation universitaire locale, pas d’authentification, base de données, paiement
  ou envoi en cuisine. Redémarrage = perte des conversations et paniers.
- Petite vérification réelle, pas de nouvelle évaluation statistique du chatbot.
- Risque TPM pour les longs échanges/paniers et requêtes rapprochées.
- Le retrait textuel seul reste soumis à validation explicite UI ; boissons identiques
  supprimées par identifiant de ligne pour éviter les choix arbitraires.
- Une composition ajoutée au panier est un instantané ; pour la refaire, supprimer
  cette ligne puis créer une nouvelle composition.
- Représentations 3D nouvelles simplifiées ; direction artistique Salad déjà signalée
  comme perfectible. FPS sur mobile réel et charge multi-utilisateur non mesurés.
- Le texte LLM peut rester imparfait ; prix, slots, état, panier et confirmation
  déterministes ne reposent jamais sur ses affirmations libres.

## 15. Lancement du projet

Voir le [README](../README.md) pour installation, `.env.example`, lancement séparé
FastAPI/Vite, exemples HTTP et tests. `GROQ_API_KEY` est nécessaire pour le mode
réel. La clé locale n’a pas été imprimée, copiée dans le frontend ou ajoutée au rapport.
Le fichier `.env.example` ne contient aucune clé réelle.

## État de livraison

Fonctionnalités de démonstration livrées : quatre catégories, panier, prix backend,
suppression, reset, confirmation simulée, Groq réel et documentation. Aucun blocage
fonctionnel observé dans les parcours testés. Les limites de charge, TPM, fidélité
artistique et mesures sur mobile réel restent celles décrites ci-dessus.
