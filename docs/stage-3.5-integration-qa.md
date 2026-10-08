# Stage 3.5 — Integration QA

8 octobre 2026. Verdict : **NEEDS FIXES** avant extension aux catégories.

## Diagnostic et correction REMOVE_ITEM

L’action existe déjà dans le schéma d’actions, le contexte transmis au provider,
le moteur et le parseur frontend. Le moteur sait retirer un produit présent et
rejette les incohérences. La politique protège REMOVE_ITEM par une autorisation
exacte liée au hash de l’état ; elle interdit de déduire cette autorisation du
texte utilisateur ou du modèle. L’API Stage 2 n’exposait que le consentement de
confirmation : le parcours de retrait manquait.

Correction limitée à l’intégration : `ChatRequest.remove_item_id` facultatif,
révision obligatoire, présence dans le brouillon actif vérifiée avant appel LLM,
autorisation serveur pour ce seul ID. Révision périmée → 409 ; ID absent ou
consentements contradictoires → 422 sans appel LLM. Le moteur et la politique
restent inchangés ; une autre suppression proposée par le modèle est rejetée.

Le contrôle × sur chaque produit envoie « Enlève [nom]. » avec cet ID et la
révision. Le résultat reste soumis au provider puis au moteur ; le frontend ne
retire rien de façon optimiste. Un retry ne renouvelle pas automatiquement le
consentement. La saisie seule « Enlève la tomate » reste sans autorisation : utiliser
×. Ce choix respecte le contrat de sécurité existant, sans analyse lexicale qui
transformerait une instruction adversariale en autorisation.

## Tests automatisés

- **94 backend** réussis (93 conservés + 1 parcours avec plusieurs assertions).
- **17 frontend** réussis : 13 Vitest + 4 Node existants.
- TypeScript et build Vite réussis.
- Nouveau test backend : grande salade poulet/tomate/maïs → retrait explicite
  tomate → ajout tomate, actions, historique/politique et état vérifiés ; refus
  sans consentement, mauvais ID, mauvaise révision, consentement contradictoire,
  tentative de retirer un autre produit et prix moteur 55 MAD.
- Nouveau test frontend : réponses fixtures obtenues via FastAPI et moteur avec
  MockProvider, POST avec consentement exact, progression 3/5 → 2/5 → 3/5,
  composition et projection réelle `projectMeal` sans tomate puis avec tomate.
  Le composant WebGL est remplacé dans ce test DOM : ce n’est pas un test GPU.

## Contrôles manuels navigateur

Brave, interface réelle sur http://127.0.0.1:5174/experience-review.html.
FastAPI temporaire local avec provider **mock scripté**, jamais présenté comme
Groq. Les routes, schémas et moteur sont ceux de l’application. Aucun mock ajouté
au code applicatif React.

| Contrôle | Observation |
| --- | --- |
| Backend arrêté | Message « Impossible de joindre le restaurant », retry disponible ; aucun repas fabriqué |
| Retry après démarrage | POST réussi, poulet/tomate, 2/5, devis moteur 55 MAD |
| Retrait explicite tomate | POST réussi, 1/5 ; poulet seul visible dans la scène |
| Ajout tomate | POST réussi, retour 2/5 ; tomate et poulet visibles |
| Nouveau retrait | Tomate absente, constatée aussi dans le rendu mobile |
| Reset | DELETE 200 ; historique vide, prix —, sélection vide et scène initiale |
| Message vide/espaces + Entrée | Bouton désactivé, aucun nouveau message envoyé |
| Timeout manuel | Non reproduit ; timeout backend et frontend couverts par tests automatisés |

Dispositions revues à 390×844, 768×1024 et 1390×844 : scène et composition lisibles,
slots sur deux colonnes en petit format, quatre en tablette/desktop. Les petits
formats restent une page verticale avec chat sous la composition ; ce contrôle
n’est pas une mesure sur téléphone physique.

## FastAPI → Groq réel : bloqué avant tout appel

Le fichier `.env` est absent dans le workspace. `GROQ_API_KEY` est également
absente de l’environnement du shell. **0 appel Groq**, aucun HTTP provider, aucune
réponse réelle et aucun timeout réel à rapporter. Un chemin de configuration a été
demandé ; aucun secret n’a été affiché ou enregistré.

Le premier payload applicatif V3 exact a été construit hors ligne avec le même
FastAPI/run_turn : **33 409 caractères**, dont **33 361 système**, 2 messages,
**11 222 tokens estimés** avec `o200k_harmony` et marge de messages. Ce chiffre est
une estimation locale, pas l’usage autoritatif Groq. Il dépasse le plafond de
8 000 TPM observé précédemment : le payload applicatif complet reste un blocage
probable même après restauration des credentials. Aucun nouveau 413 n’a été
observé pendant cette QA. Les payloads et le provider n’ont pas été modifiés.

Pour reprendre après configuration locale (ne jamais coller la clé dans le chat) :

```sh
cd /Users/mohamedb/Downloads/12-koul
/tmp/koul-backend-venv/bin/python -m uvicorn backend.app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

Vérifier `LLM_PROVIDER=groq`, `LLM_MODEL=openai/gpt-oss-120b` et l’URL HTTPS Groq
dans le fichier local. Le frontend standard port 5173 est autorisé par défaut ;
pour 5174, ajouter explicitement cette origine à CORS_ORIGINS.

Faire un seul premier tour, examiner le résultat puis attendre au moins 65 secondes
avant le suivant si réussi. Ne pas relancer les 42 scénarios. Le backend masque
intentionnellement les détails provider dans sa réponse publique : un diagnostic
local contrôlé sera nécessaire pour mesurer l’usage/HTTP provider sans secrets.

## Performance et limites

Build : chunk 3D partagé **1 148,65 kB minifié / 342,61 kB gzip**, SaladScene
**103,28 / 31,94 kB**, application **106,10 / 31,40 kB**. Warning Vite >500 kB
conservé et documenté ; pas de nouvelle optimisation prématurée.
Assets existants : 358 672 octets GLB et 66 620 triangles visibles selon le test
statique. Ce ne sont pas des mesures de FPS. FPS et profiling mobile non mesurés ;
console navigateur non auditée exhaustivement. Rendu WebGL observé dans les trois
formats ; un message fallback figure aussi dans l’arbre d’accessibilité du canvas
et ne prouve pas à lui seul une panne GPU lorsque le rendu est visible.

Le serveur mock temporaire est arrêté après QA. La boucle application avec moteur
est démontrée localement ; la boucle **avec V3 et Groq réel** reste non validée.
Prompts, scénarios, runner, provider, meal engine et SaladScene inchangés.
