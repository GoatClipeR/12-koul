# Desktop restaurant experience

## Final desktop polish — 2026-10-08

Visual development is frozen after this pass. The next work is the full chatbot end-to-end campaign, GitHub publication, and final academic report.

The supplied footage now plays at 78% opacity with no CSS blur and 94% saturation. Edge/bottom gradients and local cream backgrounds behind the title, composition, interaction hints, and concierge preserve readability while leaving the central characters visible. Cover sizing preserves the footage's aspect ratio. Playback, failure fallback, reduced-motion handling, and all backend/state contracts are unchanged.

The larger header logo is an SVG wrapper around the byte-for-byte original official PNG, with an exterior-only mask. White areas enclosed in the badge, eyes, teeth and shirt remain opaque; the separate tagline has transparent counters. No artwork was redrawn and no blend mode is used. `python3 frontend/tools/prepare-logo.py` reproduces the asset with the Python standard library. A generated extraction candidate was rejected because it changed artwork details; it is not used in the project.

Navigation retains the four original photographs and category behavior, with brighter inactive photography, a narrow gold active marker, pointer parallax, and matching keyboard focus feedback. Repeated slogans, category subtitles/numbers, the rotated seal, redundant ingredient link and duplicate visible meal feedback were removed. Existing ingredient springs and camera motion remain; category fades were tightened, and the 3D canvas now indicates grab/grabbing interaction.

Files changed or added in this final pass:

- `frontend/src/restaurant.css`
- `frontend/src/components/App.tsx`
- `frontend/src/3d/MealScene.tsx`
- `frontend/src/chat/KOOLChat.tsx`
- `frontend/public/brand/logo_12kool-transparent.svg` (new)
- `frontend/tools/prepare-logo.py` (new)
- `docs/desktop-redesign/README.md`

Verification completed:

- `npm test`: 26 Vitest tests plus four Node GLB/projection/motion checks passed. Existing tests cover video fallback, reduced motion, accepted state projection, additions/removals, cart and reset.
- `npm run build`: TypeScript and production Vite build passed. The production SVG and MP4 were checked against their source files; the SVG's embedded PNG matches the official original exactly.
- Native Brave visual checks using exact CSS iframe viewports at 1440 × 900 and 1920 × 1080: logo transparency, recognizable moving characters, readable menu/composition/chat, no layout collision. Playback telemetry advanced and looped through the 5.2-second clip at opacity 0.78.
- Live UI checks: all four categories; small salad with lettuce and tomato (35 MAD); explicit tomato removal reflected in both slots and 3D; pointer rotation and recenter; orange juice added (15 MAD), rendered in the real glass, shown as one cart line; cart-line removal; reset restored empty bowl, no price and empty cart.

Remaining limits: the existing shared Three.js/Lightformer chunk is 965.83 kB and triggers Vite's size advisory; dedicated 3D ingredient coverage remains limited to existing assets, with unmapped salad choices disclosed in text. This pass is a functional visual smoke test, not the forthcoming exhaustive Groq conversation evaluation. During the removal check, assistant prose understated the remaining ingredient count while the deterministic panel correctly displayed 0/2; this is recorded for that evaluation and business logic was left untouched.

## Supplied kitchen video integration (before final polish)

The supplied `frontend/public/video/12koul-kitchen.mp4` (3.6 MB, 2560 × 1440, about 5.2 seconds) is the direct shared background. It uses one persistent video node across category switches, autoplay, loop, muted audio, and inline playback. Optional category overrides remain available in `atmosphereVideos` but are empty until those clips are supplied, avoiding missing-file requests.

The video fills the environment using `object-fit: cover`, 44% opacity, restrained blur/desaturation, and foreground readability masks. It receives no pointer events; the menu, composer, and real R3F meal stay in front. Failed playback leaves the lighting fallback. Reduced motion removes the video; background tabs suspend it. Backend and business logic are unchanged.

The desktop review page now displays playback time, decoded dimensions, and opacity for QA only. Actual playback and layout were checked at 1440 × 900 and 1920 × 1080. The production output includes the unchanged MP4. Frontend tests: 26 Vitest + four GLB/projection/motion checks; production TypeScript/Vite build passes (existing shared Three.js chunk warning remains).

## Cinematic motion iteration (before footage delivery)

The experience now layers a full-viewport local-video environment, animated studio light, a physical dish entrance, interactive category photography, and synchronized concierge feedback. No footage was generated. Add clips using the names in [the video folder guide](../../frontend/public/video/README.txt); the category mapping lives in [Atmosphere.tsx](../../frontend/src/experience/Atmosphere.tsx). A missing category clip falls back to `12koul-kitchen.mp4`; when neither exists, the warm animated light environment remains visible. Videos are decorative, muted, inline, covered by readability masks, crossfaded, and paused when inactive. Reduced motion and background tabs suspend video playback.

Category scenes retain their canvas roots, run through a 1.2-second exit window, then pause. Entry combines a brief lens change, depth translation, restrained rotation, light interpolation, and a fade. There is no perpetual camera motion. Salad ingredients and other food selections use bounded damped springs with staggered starts, slight rotations, and small landing overshoot. Drinks retain departing liquid selections for removal/reset motion. All composition inputs still come from validated state.

The concierge's thinking indicator, transient meal confirmation, and scene marker share the accepted response. Confirmation text is derived from changes in the validated snapshot; rejected actions never announce a successful update. Recommendations get their own selectable emphasis without adding unselected ingredients to the dish. Pointer-responsive category photography and title entrances reinforce navigation.

This iteration was reviewed live at 1440 × 900, 1920 × 1080, and 2560 × 1440. Live API checks covered multi-ingredient salad creation, corn removal, drink addition with another active draft, category changes, and reset to an empty table/cart. Long assistant messages and drink framing were adjusted after visual inspection. Development hot reload encountered an R3F root teardown error while scene component structures were being edited; a fresh page load rendered and subsequent category changes worked. Use a fresh load to review the completed changes.

Final checks: 25 Vitest tests plus four GLB/projection/motion tests pass, and TypeScript/Vite build passes. New tests cover missing-video fallback, reduced motion, inactive/background playback, accepted-only feedback, spring convergence across frame rates, and delayed scene exit. Existing shared Three.js chunk-size warnings remain. Actual video appearance and seam quality cannot be reviewed until clips are supplied.

## Original desktop layout iteration

The frontend now uses an editorial menu rail, a shared warm food stage, a bottom KOOL AI composer, compact meal details, and native dialog drawers for the cart and menu. The official logo, fonts, colors, menu, backend, API client, conversation hook, action validation, price engine, and cart commands are preserved. No frontend dependencies were added.

## Rendering

- The salad retains the original eight GLB assets. Its read-only projection remains the only input to ingredient selection.
- Ingredients arrive with a deterministic per-piece stagger and settling motion; removal animates existing instances out. Ingredient height follows whether lettuce is present. Bowl size follows the validated size.
- Materials add seeded surface detail, ingredient-specific roughness, warm studio reflections, soft shadows, ambient occlusion, ACES tone mapping, and restrained bloom.
- Sandwich and plate scenes retain selections during exit animation. The sandwich reuses salad ingredient assets and adds a textured procedural bread surface. Drinks now have a real glass scene, colored from the latest validated drink in the cart.
- Browsing an unconfigured category shows an empty serving vessel. Category photography is navigation imagery, never the meal-state visualization.
- Visited canvas roots stay mounted, with inactive frame loops paused. Camera orbit and zoom are constrained; the recenter control restores the initial camera position. Reduced-motion preferences disable the composition and CSS transitions.
- Existing unmapped salad items remain disclosed in the scene caption and listed in the composition. Seven salad ingredient types have dedicated GLB representations; this change does not claim full asset coverage of the menu.

## Desktop review

Run the existing frontend and backend as described in the repository README. Open `/desktop-review.html` in the Vite development server to inspect the actual app in 1440 × 900, 1920 × 1080, and 2560 × 1440 iframe viewports. The review page scales the preview to fit the screen; the iframe retains the exact selected CSS viewport size. It uses the normal API, not fixture meal data, and is not included in the production Vite entry points.

Visual checks included empty vessels, salad additions/removal, long compositions, sandwich material detail, category changes, compact composer, and cart drawer. Iterations corrected unsupported topping height without lettuce, a clipped long composition, uniform bread shading, and the selected-dish completeness label when another draft is unfinished.

All three desktop viewport sizes were inspected. The original pass lost its browser window before live drink/reset checks; these were completed in the cinematic motion iteration above. The last plate-surface refinement has not been visually rechecked with a populated plate. Adding a drink selects the drink stage even when another unfinished draft remains active.

## Validation

- Frontend integration and API tests cover add → remove → add, explicit removal consent, backend prices and slots, malformed responses, network errors, busy guards, conversation DELETE success/failure, four-category cart flow, exact-line removal, and confirmation.
- The existing GLB container, geometry-budget, state-projection, and motion tests are retained.
- The final frontend run passes all 20 integration/API tests and four GLB/projection/motion tests.
- The complete backend suite passes (128 tests). Its existing `tools/requirements-eval.txt` dependency and tokenizer encoding were initialized locally to run the suite.
- TypeScript and Vite production build pass. Vite continues to warn about the shared Three.js dependency chunk exceeding 500 kB; category scenes are lazy loaded.
- Live browser requests exercised the existing Groq/FastAPI path, including salad composition and corn add/remove, sandwich composition, cart transfer and exact-line removal.

## Artwork

The category photographs and bread texture were created with the built-in image generation tool. Exact prompts and saved paths are recorded in [image-prompts.json](image-prompts.json) and [bread-prompt.json](bread-prompt.json). Saved assets: [salad](../../frontend/public/images/salad.png), [sandwich](../../frontend/public/images/sandwich.png), [plate](../../frontend/public/images/plat.png), [drink](../../frontend/public/images/drink.png), and [bread texture](../../frontend/public/images/bread-crust.png). The logo was not regenerated or modified.

This iteration is desktop only. It does not add payment, fulfillment, persistence, or new menu products.
