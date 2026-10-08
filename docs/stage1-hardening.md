# Stage 1 hardening — completion and self-audit

Status: **READY FOR FINAL EVALUATION**. Stage 2 has not started.

## Findings addressed
| Audit finding | Correction | Evidence |
|---|---|---|
| Redirect credential disclosure | Disable all authenticated redirects, including same-origin; reject initial HTTP URL | Tests cover 301/302/303/307/308 × same-host HTTPS, cross-host HTTPS, same-host HTTP and cross-host HTTP; only initial HTTPS request reaches fake transport |
| Unchecked model factual claims | Authoritative display.message/facts generated from deterministic state, menu and quote; model prose explicitly untrusted diagnostics | False price, medical and policy claims cannot enter display output |
| Escaping transport/parser exceptions | Structured provider errors, bounded parser and final exception boundary | IncompleteRead, recursion, malformed/truncated/empty bodies, invalid UTF-8, timeout, connection/HTTP/unexpected failures tested |
| Evaluation crash on reparsing | Shared bounded safe_loads, invalid output retained as failed scenario | Malformed first response still yields 42 serializable records |
| Weak metrics | Exact expected actions/state/error and confirmation completeness; separate lexical diagnostics and semantic-review placeholders | Empty recommendation/confirmation fails; contradictory keywords never award semantic success |
| Destructive intent gap | Trusted, exact, state-bound grants; information/composition modes | Price question cannot clear/remove/confirm; stale/wrong-target/model-created grants rejected |
| Confirmation before final mutation | Confirmation unique and last; final state completeness checked atomically | Post-confirm actions rejected; remove-then-confirm rolls back if incomplete; replacement then confirmation succeeds |
| Resource bounds | History count/aggregate limits, response bytes, JSON depth/numeric limits, attempt/overall deadlines, capped outstanding workers/backoff | Pathological inputs, slow transport, capacity saturation and retry budget tests |
| Menu runtime trust | Single reusable validator shared by MenuService and CLI | Invalid prices, allergens, IDs, slots, metadata and JSON fail initialization |
| Evaluation reproducibility | UTC timestamp, scenario version, prompt/menu SHA-256, provider/model and safe configuration | Metadata assertions; no keys or authorization headers stored |
| Secret hygiene | Ignore .env and .env.* except example; empty example credentials and obvious dummy test values | Current-file pattern scan found no apparent credentials; no .env present |
| Provisional font metadata | Record approved font status without changing font/color values | Bricolage Grotesque + Figtree and original tokens preserved |

No requested code correction was intentionally skipped. Real-model evaluation and
historical secret guarantees remain unavailable by design/scope, not reported as passed.

## Exact source/artifact file inventory
Created:
- backend/app/services/action_policy.py
- backend/app/services/json_guard.py
- backend/app/services/menu_validation.py
- backend/app/services/presentation.py
- backend/tests/test_hardening.py
- docs/stage1-hardening.md

Modified:
- .env.example
- .gitignore
- README.md
- backend/app/schemas/actions.py
- backend/app/services/assistant.py
- backend/app/services/evaluation.py
- backend/app/services/meal_engine.py
- backend/app/services/menu.py
- backend/app/services/llm/prompts.py
- backend/app/services/llm/providers.py
- backend/app/prompts/prompt_v3.txt
- backend/tests/test_evaluation.py
- docs/stage1.md
- frontend/src/design/tokens.json
- notebook/phase1.ipynb
- notebook/mock-results.json
- tools/validate_menu.py

The frontend build regenerated ignored frontend/dist artifacts. No application UI,
FastAPI endpoints, Three.js implementation, menu items/prices or logo was changed.
The price engine and existing meal representation are preserved.

## Authorization and confirmation contract
`run_turn` and `apply_response` require caller-issued grants for CLEAR_MEAL,
CLEAR_CATEGORY, REMOVE_ITEM and CONFIRM_ORDER. Grants cover exact actions/targets and
initial-state hash. They are local trusted objects, never model output or unchecked
request fields. Natural-language text alone does not confer permission. Information
mode forbids mutations; composition mode permits additions/category/size selection.
Results distinguish information, composition, destructive_mutation and confirmation.

`apply_action` remains a trusted single-command domain primitive. Future adapters must
route untrusted model batches through apply_response/run_turn. A future API must own
session state, grant issuance and replay handling; these are not implemented now.

CONFIRM_ORDER must be last and unique. Final state must be valid and every draft
complete. Any failure rolls back the entire batch. Confirmation validates composition,
not external order submission. Callers must not interpret accepted model prose as
verified facts; authoritative output is display.message/display.facts.

## Regression results
- **53 automated test methods passed**: all 22 baseline tests retained plus 31 new
  hardening tests. The existing evaluation test was updated to require unmeasured
  semantic scores, replacing the old expectation that lexical probes count as measured
  semantic quality. No test was removed to obtain a pass.
- **22 independent in-memory audit checks passed**, using fixed approved counts/prices
  and rollback from existing nonempty states.
- **Menu CLI passed**: all 75 items validated using the same initialization validator.
- **Notebook passed**: all four code cells executed; actual mock output regenerated.
- **Mock evaluation: 42/42 contract checks passed** (14 per prompt); semantic scores
  remain pending human review, with no inferred ranking of V1/V2/V3.
- **Frontend TypeScript/Vite build passed**. Existing smoke chunk remains 1551.72 kB
  (469.44 kB gzip), producing the existing >500 kB warning. No browser rendering was run.
- Current-file credential-pattern scan: no apparent keys/private keys found. Git metadata
  is absent, so historical scanning cannot be guaranteed and no history was reconstructed.

Commands:
```bash
python3 -B -m unittest discover -s backend/tests -q
python3 -B tools/validate_menu.py
python3 -B tools/run_phase1.py
python3 -B -m backend.app.services.evaluation --output notebook/mock-results.json
npm --prefix frontend run build
```

## Final self-audit and limitations
- Authenticated redirects cannot forward credentials: every redirect is blocked before
  a destination request is issued. Direct HTTP transport URLs are rejected.
- Built-in provider transport/parser failures tested above yield structured errors with
  safe codes/status/attempt information; exception strings and response bodies are not
  copied into errors. Raw model content remains untrusted diagnostic material.
- Invalid model output cannot abort the tested evaluation paths; one bad record does
  not suppress later records or final JSON serialization.
- Lexical flags cannot become semantic scores. A correct action contract can coexist
  with harmful prose; human review remains explicit and mandatory for model quality.
- Price questions receive no implicit destructive authorization. Caller mistakes in
  granting permissions are outside the model validator's trust boundary.
- Confirmation cannot precede another action, and incomplete final state cannot confirm.
- Caller-facing transport deadlines are enforced with bounded daemon workers. Python
  cannot kill a blocked transport; it may run until returning. Outstanding work is capped
  at four and saturation fails closed. This is not a process-isolated cancellation system.
- Invalid menus fail startup. The validator enforces structure and approved rules, not
  real-world restaurant factual accuracy; menu.json remains the supplied source of truth.
- The compatible provider has not been tested against a live service. Final evaluation
  must still check actual model behavior, refusal, ambiguity, language and injection
  handling. No live results or superior-prompt claims are fabricated.
- `.env` and current source/artifact scan are clean; absent repository history prevents
  any claim about historical secrets.

No Stage 2 work was performed.
