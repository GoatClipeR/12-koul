# Vertical slice 3D — grande salade 12-KOUL

## Visualiser

```sh
npm --prefix frontend run dev -- --host 127.0.0.1
```

Ouvrir `http://127.0.0.1:5173/salad.html`. L’entrée `index.html` et le smoke test
restent séparés. La scène charge uniquement le bol et les sept ingrédients demandés.
L’interface utilise Bricolage Grotesque, Figtree, les tokens du projet et le PNG
original du logo, sans le redessiner.

## Flux simple

```text
React UI → meal state → R3F → Three.js → GLB assets
```

En intégration future, la provenance du `meal state` doit rester :

```text
LLM → structured action → deterministic meal engine → meal state → React/R3F → scène
```

`SaladScene` reçoit un `MealState`, de même forme que le JSON du moteur existant.
`projectMeal` est une projection en lecture seule. Elle ne valide pas les règles
métier, ne calcule pas de prix et n’exécute aucune action du modèle.

| Changement accepté par le moteur | Projection visuelle |
| --- | --- |
| ADD_ITEM | Apparition du groupe associé à l’ID |
| REMOVE_ITEM | Retrait de ce groupe |
| SET_SIZE | Changement d’échelle du bol et de sa composition |
| CLEAR_MEAL | Disparition de la composition |

Une action rejetée doit conserver l’ancien état, donc l’ancienne scène. Ne jamais
passer directement du texte LLM à Three.js. Les IDs connus du menu mais sans asset
sont renvoyés dans `unmapped`, pas remplacés par un ingrédient inventé. La démo est
un brouillon valide mais **incomplet**, et non une grande salade confirmable :
1 base / 4 ingrédients / 1 topping / 1 sauce, contre 2 / 5 / 3 / 2 requis.

## Fichiers

- `frontend/salad.html` : entrée dédiée.
- `frontend/src/salad/main.tsx`, `salad.css` : composition éditoriale, liste des
  ingrédients, reset caméra, chargement différé et fallback d’erreur.
- `mealScene.ts` : type compatible, mapping IDs → assets, projection, état de démo.
- `SaladScene.tsx` : Canvas, caméra, éclairage, ombres, effets et animation du groupe.
- `Ingredients.tsx` : bol GLB, composant générique d’ingrédient instancié.
- `surface.ts` : microrelief déterministe généré localement, sans image distante.
- `frontend/public/models/salad/*.glb` : bol, laitue, tomate, concombre, poulet,
  maïs, croûtons et Caesar. Assets procéduraux originaux du projet.
- `frontend/tools/generate-salad-assets.mjs` : génération reproductible de ces huit
  GLB uniquement. Aucune dépendance supplémentaire.

## Direction visuelle et rendu

Bol céramique peu profond, feuilles plissées, quartiers de tomate avec chair et
pépins, rondelles de concombre avec peau et graines, poulet marqué au gril, grains
de maïs, croûtons et filet de sauce. Les proportions et placements sont stables ;
il ne s’agit pas d’une simulation physique.

Caméra perspective 32°, exploration orbitale limitée, studio chaud créé avec
Drei Lightformers, fill froid discret, ombres PCF compatibles avec Three.js 0.186
(pas de `PCFSoftShadowMap`), ombre de contact radiale approximative, générée localement (pas une occlusion physique). Le renderer reste en
`NoToneMapping` : ACES est appliqué **une seule fois** dans le postprocessing.
Bloom et Vignette légers, SMAA, DPR plafonné à 1.5. Fondus des ingrédients et interpolation des changements de taille, sans oscillation permanente ; `prefers-reduced-motion` désactive ces animations.

La scène a été observée dans Brave localement. C’est une première direction
procédurale : la validation artistique finale des textures et de l’apparence
alimentaire reste nécessaire. Ne pas confondre affichage fonctionnel et rendu
publicitaire final.

## Ressources et performance

Les GLB sont locaux et autonomes, sans textures externes. La sélection représente
358 672 octets, 9 168 triangles uniques et environ 66 620 triangles visibles
instanciés, 41 primitives dessinées avant ombres/effets.
La suite de tests imprime les tailles à jour ; les passes d’ombres/postprocessing
ajoutent du travail GPU, donc ce nombre n’est pas un compteur global de draw calls.

La scène utilise `React.lazy` ; les GLB sont chargés par `useGLTF` dans Suspense,
sans préchargement systématique de tout le menu. Le bundle 3D partagé reste
volumineux (avertissement Vite >500 Ko), malgré le découpage de la scène. À profiler
avant extension. Les placements/matrices sont calculés au montage, hors `useFrame`.
La boucle d’animation modifie des refs, sans allocation ni `setState` par frame.

Les géométries et matériaux originaux de `useGLTF` appartiennent à son cache
partagé : `dispose={null}` évite leur destruction lors d’un remontage de la vue.
Les matériaux clonés et textures de microrelief propres aux instances sont libérés
au démontage. Les objets GLB restent en cache durant la session, bornés à huit
assets. Les buffers des InstancedMesh sont libérés explicitement. La texture de contact
est libérée au démontage. ContactShadows a été retiré de cette scène : son implémentation
installée crée des render targets sans cleanup explicite, ce qui rendait les
remontages par état problématiques. Les effets conservent leur cycle de vie R3F. Une éviction de cache future devra libérer les ressources seulement
après le dernier consommateur.

Draco/Meshopt sont à envisager sur des meshes plus lourds ; KTX2 pour de vraies
textures PBR. Aucun décodeur supplémentaire n’est téléchargé pour ces petits GLB
non compressés. Higgsfield est **optionnel** pour proposer des assets à importer,
jamais le moteur de rendu ni une dépendance runtime. Three.js/R3F demeure le socle.

Le test logiciel WebGL de Stage 0 ne mesure pas les performances GPU réelles.
Aucun objectif FPS mobile n’est déclaré atteint. Profiler sur les appareils cibles,
avec les ombres et effets activés, avant de décider du budget final.

## Vérification

```sh
npm --prefix frontend run build
node --test frontend/tools/test-salad.mjs
python3 -B tools/run_phase1.py
```

Build TypeScript/Vite réussi. Tests frontend : projection add/remove/size/clear,
absence de mutation, mapping au menu, assets inconnus signalés, intégrité GLB,
budget de géométrie et poids. L’unité de taille ne remplace pas le contrôle métier
`SIZE_CONFLICT` du backend : elle teste seulement un changement de snapshot.
Suite Python existante et nouveaux tests du notebook : 80 réussis.

Aucun endpoint FastAPI, appel LLM ou changement du runner d’évaluation n’a été ajouté.


## Review de qualité — première salade uniquement

**TECHNICAL VERTICAL SLICE = VALIDATED** : projection du meal state, chargement GLB,
contrôles de snapshot et build/tests fonctionnels vérifiés.

**ART DIRECTION = NEEDS POLISH** : validation technique ne signifie ni rendu food
premium final ni performance mobile certifiée. Aucun nouveau travail d’assets ou
refactoring artistique dans la finalisation Phase 1.

**Verdict artistique : NEEDS POLISH.** Le bol et les sept ingrédients sont lisibles, la structure
React/R3F est exploitable et les contrôles de snapshot fonctionnent. Le rendu reste
nettement procédural ; il ne constitue pas encore une référence food premium finale.

### Observations et corrections

- Avant : quartiers de tomate épais comme des blocs, poulet en capsules identiques
  avec barres de grill en relief, sauce en long cordon suspendu. Après : tomate
  amincie, poulet déformé avec cuisson par couleurs de sommets, quatre filets courts,
  croûtons aux arêtes arrondies, bord de bol sans intersection visible du filet brun.
- Placement moins uniforme, inclinaisons légèrement variées et rayon contenu dans le bol.
- Une texture de microrelief par ingrédient, partagée entre ses sous-meshes ; relief
  plus marqué pour le pain et le poulet, plus léger pour légumes et sauce. Pas de
  translucence physique ajoutée : elle demanderait une validation spécifique.
- Fill relevé, key moins intense. ACES, SMAA, Bloom et Vignette conservés, sans effet
  supplémentaire. Ombre radiale économique, qui disparaît avec CLEAR_MEAL et suit
  l’échelle. Cette approximation ne suit pas chaque relief du bol.
- Message de chargement explicite pendant le chargement des GLB.
- Caméra rapprochée et abaissée, fov adapté au ratio portrait, zoom rapproché limité.
  Titre réduit sur desktop, composition en colonne sous 1000 px.
- Fondu alpha-hash des ingrédients, interpolation de taille réversible, état vide
  masqué. Les ingrédients déjà visités restent montés invisibles pour éviter les
  rechargements : cache borné aux sept ingrédients de cette slice. Leurs ressources
  propres sont libérées au démontage du Canvas. Aucun parsing de réponse LLM.
- useFrame : modifications scalaires/refs, pas d’allocation d’objet ni setState.
  Ingredient utilise memo ; géométries, textures et placements sont mémorisés.

### Vérifications réellement effectuées

Brave local : rendu desktop initial, puis viewports **390 × 844** et **1390 × 844**
dans `salad-review.html`. Les iframes imposent leur propre viewport CSS, sans simple
zoom de la page. Bol entier, titre et ingrédients lisibles dans les cadrages inspectés.
Les screenshots ont été inspectés dans l’outil navigateur, sans fichier de capture
ajouté au dépôt. Contrôles QA : état vide et ombre disparus, petite salade sans poulet
ni maïs, restauration de la grande composition. Les états finaux ont été observés ;
la régularité frame par frame des fondus n’a pas été mesurée.

`?review=1` active des contrôles **uniquement avec Vite en développement**. Ils
injectent des snapshots pour tester la projection, pas des actions utilisateur ni
une nouvelle logique métier. Le snapshot petite salade a été vérifié avec
`validate_state` existant. Aucun appel réseau métier. La page QA n’est pas une
entrée du build de production.

Tests : build TypeScript/Vite réussi ; quatre tests Node réussis (projection,
menu/assets, GLB et budget, convergence/inversion des fondus/reduced motion).
Aucun test live Groq relancé. Aucun changement Python, notebook, prompt ou scénario.

### Limites restantes

Feuilles encore répétitives, chair des tomates et concombres trop uniforme, cuisson
du poulet peu détaillée, sauce simplifiée sans adhérence calculée aux surfaces.
Le fond 3D est légèrement plus gris que le papier de l’interface après tone mapping.
Les fondus alpha-hash peuvent présenter un grain temporaire : à examiner en mouvement
sur appareils cibles. Reduced motion est vérifié dans le helper et par lecture du
code ; pas par émulation système dans le navigateur.

Disposal vérifié dans le code, **pas par mesure de mémoire GPU sur remontages répétés**.
Pas de profil React ni de mesure FPS, pas de test tactile sur smartphone réel. Le
chunk 3D partagé reste d’environ 1,15 Mo minifié (343 Ko gzip), et la scène différée
d’environ 103 Ko (32 Ko gzip). Le lazy loading existe ; ne pas masquer l’avertissement
Vite et ne pas déduire les performances mobiles d’un rendu desktop/software WebGL.

## Passage vers l’application future

Le [contrat d’architecture prévu](next-architecture.md) décrit l’origine future du
meal state. La slice actuelle reste une démonstration locale ; FastAPI n’est pas
implémenté. Restent à traiter : feuilles répétitives, textures de légumes uniformes,
poulet et sauce simplifiés, ombre approximative, performances non mesurées sur
appareil mobile et bundle 3D volumineux. Ces limites ne justifient pas à ce stade
un changement de moteur ou une nouvelle phase d’assets.
