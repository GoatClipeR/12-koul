# 12-KOUL — Stage 0 report (preparation & validation)

## Result: Stage 0 complete. Nothing beyond preparation was built.

| # | Deliverable | Status | Where |
|---|---|---|---|
| A | Repository structure | done | `backend/ frontend/ notebook/ docs/ tools/` |
| B | Final `menu.json` | done, validated (75 items) | `backend/app/data/menu.json` |
| C | Price data (MAD) | done | in `menu.json`; summary in `docs/menu-spec.md` |
| D | Allergen data | done (28/75 items carry ≥1 of 5 tracked allergens; all items declare a list) | `menu.json`, `docs/menu-spec.md` |
| E | Exact salad rules | done, enforced by the validator | `menu.json`, `tools/validate_menu.py` |
| F | Design tokens from the logo | done | `frontend/src/design/tokens.css`, `tokens.json` |
| G | Font comparison | done, recommendation below | `docs/stage0/font-comparison.png` |
| H | Initial 3D technical smoke test | passed | `frontend/smoke.html`, `src/smoke/` |
| I | WebGL smoke test | passed (WebGL2 via software GL) | `docs/stage0/webgl-smoke.png` |
| J | Skills confirmation | see below | — |
| K | Higgsfield availability | **not callable** | see below |

## Menu validation
`python tools/validate_menu.py` → OK. Negative test confirmed: a 6-ingredient large salad and a `null` allergen list are both rejected.
Slice assets referenced by menu items: 7 (lettuce, tomato, cucumber, chicken, corn, croutons, Caesar).

## Design tokens (sampled from the uploaded logo, median per hue family)
awning red `#D43935` · gold `#EBB34A` · sun-mid `#DF9D5E` · sun-deep `#CE8049` · wood `#4D2514` · wood-deep `#3E1F14` · navy `#334D6F` · plaid `#577694` · white `#FFFFFF`.
Derived for UI (flagged `derived` in tokens.json): red-deep `#A82A27`, wood-night `#2A140B` (page bg), paper `#FFF9EE` (ticket).
All key text/background pairs pass WCAG AA (lowest: red on paper 4.52, white on red 4.73) — see `docs/stage0/contrast.txt`.

## Fonts (rendered against the logo banner)
Recommendation: **A · Bricolage Grotesque** (display, variable weight/width/optical size) + **Figtree** (body, tabular numerals for prices).
Alfa Slab One (B) is the closest to the banner lettering but is single-weight and reads diner/retro rather than premium; Rokkitt (C) is too light for the stage; Archivo wide (D) wraps awkwardly at display sizes. Œ, É, Ç render correctly in all candidates.

## 3D / WebGL smoke test (a toolchain check, NOT the visual quality gate)
- Stack: three 0.186, @react-three/fiber 9, drei 10, postprocessing (SMAA + Bloom + ACES tone mapping + Vignette) — renders without error.
- WebGL2 available in headless Chromium (SwiftShader). Max texture 8192, float textures OK.
- GLB round trip OK (export → GLTFLoader, 18,432 triangles, 413 KB uncompressed); Draco, KTX2 and Meshopt loaders construct correctly.
- 300 instanced meshes + "mutate refs in useFrame" animation pattern + procedural canvas texture + disposal on unmount: OK.
- Software-GL frame rate (0.7 fps) is meaningless for GPU performance; real performance must be measured on your devices.
- Findings to act on later: `PCFSoftShadowMap` was removed in three 0.186 (use PCFShadowMap or VSM); `THREE.Clock` deprecation warning from the R3F version; bundle is 1.55 MB (469 KB gzip) before code-splitting; `gl.info` must use `autoReset=false` to count draw calls across post-processing passes.

## Skills / tools confirmed
- `ui-3d-pro` (R3F rules, disposal, fallbacks, anti-slop) — usable.
- `frontend-design` (tokens, plan, anti-generic checklist) — usable.
- Three.js viewer connector — available (needs opt-in); optional look-dev aid.
- Canva connector — 2D only (image generation, background removal); could produce a style moodboard; no 3D.
- No GLB-optimization or animation skill exists.

## Higgsfield
Connector is connected but exposes **zero callable tools** (re-checked this turn by tool search and resource listing). Its UI bundle declares tool names such as `generate_3d`, but they are not callable here, so nothing was tested and no credits were used. Baseline stays procedural + CC0 + GLB. If tools appear later, one asset only will be tested in Stage 4a and shown to you first.

## Environment findings that affect later stages
- Sandbox cannot reach `api.groq.com` (blocked: `host_not_allowed`) and has no `GROQ_API_KEY`. Backend, engine and unit tests will use a fake provider here; **real-model evaluation (notebook Phase 1) must be run on your machine** and the results brought back.
- Headless Chromium + software WebGL works in the sandbox, so I can screenshot 3D scenes for look-dev.
- Python 3.12 and Node 22 available; FastAPI is not installed yet (pip is allowed, installed in Stage 2).

## Assumptions needing your confirmation (also in docs/menu-spec.md)
1. Sandwich: bread 1, protein 1, sauce 1 required; cheese 0–1; vegetables 0–3; extras 0–2.
2. Plat: protein 1, side 1, sauce 1 (all required). Drinks: exactly 1 per drink line.
3. No duplicate item within a slot.
4. `SET_SIZE` is rejected with `SIZE_CONFLICT` if the current selection doesn't fit the new size.
5. Font pair A + Figtree; token values above.
