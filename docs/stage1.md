# Stage 1 — hardened core and KOOL AI evaluation

## Scope and audit baseline
Stage 0 supplied the menu, specifications, design tokens, logo and React/R3F smoke test.
Stage 1 added the framework-independent domain services, providers, prompts, tests and
Phase 1 notebook. The independent review found correct composition/pricing but weak
provider security, authorization, confirmation and evaluation boundaries. The hardening
report records the corrections. No Stage 2 endpoints or production UI/3D system exists.

## Architecture
User/history + trusted caller policy -> provider -> strict response schema -> action
policy -> atomic meal engine -> deterministic pricing -> deterministic display facts.
Model text is untrusted diagnostic data. `accepted` means the action batch passed,
not that model prose is factually correct. Use `display.message` and `display.facts`
for authoritative UI content, not `response.message` or `raw_response`.

MenuService loads menu.json through the same reusable validator used by the CLI.
Invalid JSON, malformed data, duplicate IDs, wrong composition rules, invalid prices,
allergens and diet contradictions fail before service creation. All access returns
copies; no secondary product catalogue exists.

## State
```json
{
  "active_category": "salad",
  "categories": {
    "salad": {
      "type": "salad", "size": "small",
      "slots": {"base": ["salad.base.lettuce"], "ingredient": [], "topping": [], "sauce": []}
    }
  }
}
```
Empty state: `{"active_category": null, "categories": {}}`. Non-salad sizes are null.
An empty unsized salad is valid but incomplete. Switching categories preserves drafts.
One draft per category; repeated same-category cart lines use separate states with
`price_cart`. Stable IDs can drive future asset mappings without Three.js dependencies.

## Actions and authorization
Responses contain exactly `message` (1–4000 characters) and `actions` (0–64).
`action_schema(menu)` publishes the JSON Schema; the runtime validator also checks
IDs/categories/sizes. Unknown fields, including price and authorization, are forbidden.

| Type | Other required fields | Policy |
|---|---|---|
| ADD_ITEM | item_id | Composition mode |
| SET_CATEGORY | category | Composition mode; preserves drafts |
| SET_SIZE | size | Composition mode; salad only; no implicit removal |
| RECOMMEND_ITEM | item_id | Informational; never selects item |
| REMOVE_ITEM | item_id | Exact caller grant |
| CLEAR_CATEGORY | category | Exact caller grant |
| CLEAR_MEAL | none | Exact caller grant |
| CONFIRM_ORDER | none | Exact caller grant; final and unique |

`authorize_actions(state, actions, menu)` is a trusted application/CLI operation,
not a natural-language classifier. It produces an immutable process-local capability
containing exact protected actions (including target IDs/categories and multiplicities)
and a hash of initial state. Missing, forged-dictionary, wrong-target or stale-state
grants are rejected. Never deserialize grants from untrusted client/model data.
The caller owns authorization decisions and capability lifetime; this is not a signed
network token or persisted session mechanism. In `information` mode only empty action
lists and recommendations are allowed, even when a grant exists. The default
`composition` mode allows additions/category/size selection but no protected actions.

`apply_action` is a trusted, single-command domain primitive used by tests and explicit
application commands. Untrusted model proposals must use `apply_response` or `run_turn`.
Do not expose the primitive as an unguarded model/API execution path.

Any action after CONFIRM_ORDER causes CONFIRM_MUST_BE_FINAL. Otherwise confirmation
runs after all preceding transitions and requires every draft complete. A failure
rolls back the whole batch. Confirmation validates composition only: no order,
payment or kitchen submission occurs. A future external order system must implement
its own authenticated, replay-safe submission contract and final-state approval.

## Business rules and pricing
Small salad exact base/ingredient/topping/sauce counts: 1/2/1/1, 35 MAD.
Large: 2/5/3/2, 55 MAD. Sandwich requires bread/protein/sauce; cheese 0–1,
vegetables 0–3, extras 0–2. Plat requires protein/side/sauce. A drink line has one drink.
Duplicate selections and excess slots are rejected. SET_SIZE rejects SIZE_CONFLICT
without removing anything. All transitions return copies and reject invalid states.

Salads use size price; other lines sum item prices. Incomplete valid drafts are
estimates (`orderable: false`), not order totals eligible for submission. An unsized
salad total is null. Empty state totals zero but is not orderable. price_cart rejects
empty/incomplete/invalid inputs. Currency and prices are menu-derived integer MAD.

Stable DomainError codes include UNKNOWN_ITEM, UNKNOWN_CATEGORY, UNKNOWN_SLOT,
WRONG_CATEGORY, WRONG_SLOT, SLOT_FULL, DUPLICATE_ITEM, NOT_IN_MEAL, SIZE_REQUIRED,
INVALID_SIZE, SIZE_NOT_ALLOWED, SIZE_CONFLICT, INCOMPLETE_MEAL, CART_EMPTY,
NO_ACTIVE_MEAL, INVALID_STATE, INVALID_ACTION, UNKNOWN_ACTION, INVALID_ACTION_FIELDS,
INVALID_JSON, INVALID_RESPONSE, ACTION_NOT_AUTHORIZED, INVALID_AUTHORIZATION,
INVALID_POLICY, CONFIRM_MUST_BE_FINAL, INVALID_HISTORY and HISTORY_TOO_LARGE.

## Providers and resource limits
MockProvider is fixture replay, not NLP. CompatibleProvider uses an HTTPS
chat/completions transport with every automatic redirect blocked, including same-host
redirects. No Authorization header is sent to a redirect destination or HTTP URL.
Credentials come only from environment configuration; errors expose stable codes,
attempt counts and HTTP status where available, never exception messages or bodies.
Unexpected third-party provider exceptions are also caught at the application boundary.

Bounds: current message 1000 characters; at most 40 history messages, each up to 4000
characters, combined at most 16000. Oversized history is rejected before copying.
Action JSON: 100000 bytes and depth 16. HTTP envelope: 1000000 bytes and depth 24.
Numeric tokens are at most 128 characters; non-finite numbers and duplicate keys fail.
The same JSON parser is shared by action validation, provider envelopes and evaluation.

Default attempt timeout: 20 seconds; total caller-facing deadline: 30 seconds.
Both must be positive, finite and at most 120 seconds. Retries: 0–3, default 1, with
bounded exponential backoff. Only transient network failures, 429 and 5xx retry.
No retry after the watchdog expires because transport work may still be unwinding.
At most four transport workers may remain outstanding; there is no queued backlog.
Saturation returns PROVIDER_BUSY. Python cannot forcibly cancel blocked threads;
a timed-out call may continue in the background until its socket/transport returns,
but its result is discarded and it cannot mutate meal state. The bounded worker
limit prevents repeated timeouts from creating unbounded threads. Custom providers
implementing complete() are trusted plugins; the built-in HTTP adapter supplies the
transport deadline, while run_turn catches their raised exceptions.

## Prompts and factual presentation
V1 specializes the role and language. V2 strengthens menu/schema grounding. V3 adds
ambiguity, injection resistance, dietary limitations, caller authorization and final
confirmation. All versions receive menu/state/schema/policy context. Missing grants
must be obtained by the caller; writing “confirm” is not itself an authorization token.

System prompts cannot guarantee factual prose or resist every injection. The
architecture guarantees allowed state transitions and deterministic display facts.
The model can still emit incorrect raw prose, which must stay out of authoritative UI
copy. Deterministic display uses a caller-selected locale (fr by default, en supported);
future conversational UI can request/review richer prose without treating it as fact.

## Evaluation
14 scenarios × 3 prompts. Records contain inputs/history, raw response, actions,
expected actions/state/error, authorized fixture actions, actual validation/state/quote,
contract result and separate semantic-review placeholders. Required actions are now
checked, so empty responses fail recommendation and confirmation contracts.
Malformed responses fail their scenario and do not stop later scenarios.

Four distinct layers: schema/structural validation, deterministic business rules,
lexical diagnostic flags, and semantic human review. Lexical flags never contribute
to semantic success. Mock results say CONTRACT_PASS/FAIL; real results are FAIL or
PENDING_REVIEW under the automated contract, never automatic semantic PASS. Human
review must adjudicate safe alternative real-model actions and all seven quality
metrics. Metadata contains UTC timestamp, scenario version, menu/prompt SHA-256 hashes,
model/provider and relevant non-secret configuration. No live result is supplied.

The notebook and JSON report contain actual regenerated mock executions. The notebook
uses plain Python; tools/run_phase1.py captures real cell outputs without Jupyter.
The test suite executes its code cells as well. For live evaluation use the documented
CLI or opt-in cell, then fill semantic_evaluation.scores and reviewer notes.
