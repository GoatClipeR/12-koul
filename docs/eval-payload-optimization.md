# Evaluation payload reduction — scoped-eval-v1

## Confirmed cause and measurement
The user's full V1 diagnostic returned HTTP 413: TPM Limit 8000, Requested 10966.
The minimal Python request returned HTTP 200. This work changes evaluation context
serialization/retrieval, not credentials, endpoint, model or production architecture.

Tokenizer: tiktoken 0.12.0, o200k_harmony. OpenAI's GPT-OSS tokenizer implementation
uses this encoding: https://github.com/openai/gpt-oss/blob/main/gpt_oss/tokenizer.py .
We count message content locally and reserve 512 + 16 tokens/message for server framing.
These are not claimed to equal Groq's exact TPM accounting: for V1 normal_order the
original content is 10565 local tokens, while the user observed 10966 requested by Groq.
Component token counts are independently encoded and not strictly additive at boundaries.
The JSON report includes exact local character/token measurements for every component
of all 42 before/after message sets. No live calls are made by the report tool.

## Proposed changes, now implemented
- No edits to V1/V2/V3 prompt text, scenario definitions, history, expected answers,
  starting state, grants, action validators, meal/price engine or production providers.
- The same retrieval/projection is applied to all three versions. Retrieval accepts only
  current user text, conversation history and current state. It cannot read expected
  actions, mock replies, scenario IDs or reference answers.
- Categories are retrieved by conservative French/English aliases. All categories with
  existing drafts are retained. Salad/drink/etc. requests receive their full category
  item options. Mixed drafts retain every selected category. Ambiguous chicken without
  a category gets a category overview rather than an invented category selection.
- A general recommendation without a category gets the overview and may ask for a
  category. The existing recommendation fixture explicitly asks for a beverage, so all
  11 drink options are present. Unknown/out-of-domain/security requests with no matching
  category receive no item detail catalogue; global rules and menu metadata stay present.
- All four categories' exact rules and pricing models remain global, including both
  salad sizes and prices. No required business rule is dropped in any scenario.
- Items are grouped by category/slot, with a shared column legend. Every scoped item's
  full ID, French/English name, price, allergens, tags, spice, vegetarian/vegan flags
  and drink group survive exactly. Only 3D asset references and repeated category/slot
  fields are removed. Category slot labels, slot_order and localized size labels are
  omitted because structure/slot keys/size keys already supply that information.
- The full original item/category/size enums appear once through JSON Schema $defs/$ref.
  Expanding references reproduces the original schema exactly. Even security requests
  retain the full ID enum to keep the action contract unchanged; unrelated detailed
  records are absent. Opaque IDs must not be used to invent missing facts.
- Compact JSON removes formatting whitespace. A shared scope/table legend explains the
  projection; missing detail is not a claim that a product is unavailable.

## Breakdown — V1 normal_order
| Component | Before characters | Before tokens | After characters | After tokens |
|---|---:|---:|---:|---:|
| System prompt | 472 | 118 | 472 | 118 |
| Item catalogue | 19021 | 6891 | 1121 | 345 |
| Composition/pricing rules | 1079 | 433 | 846 | 281 |
| Category labels | 1298 | 466 | 207 | 65 |
| Menu metadata | 645 | 189 | 609 | 161 |
| Action schema | 7613 | 2389 | 3489 | 950 |
| Meal state | 43 | 11 | 40 | 10 |
| Authorization policy | 203 | 45 | 196 | 40 |
| History (empty serialized list) | 2 | 1 | 2 | 1 |
| User input | 33 | 11 | 33 | 11 |
| Scope/table legend | 2 | 1 | 401 | 88 |

JSON key/wrapper punctuation and BPE boundary differences are represented in the complete
message totals, not attributed twice to components. The empty-list/empty-object entries
above describe standalone breakdown values, not additional messages sent to Groq.
Full V1 content: **10565 -> 2078 tokens**; budgeted including framing: **11109 -> 2622**.

## All 42 combinations
| Version | Before budgeted input range | After budgeted input range |
|---|---:|---:|
| V1 | 11103–11245 | 2273–3264 |
| V2 | 11226–11368 | 2396–3387 |
| V3 | 11749–11891 | 2919–3910 |

Hard input budget: 6000 tokens including framing reserve. The largest actual compact
case is V3 size_conflict: 3366 content + 544 reserve = 3910. Completion cap is 1024 for
all compact evaluation requests, so this case budgets 4934 input+completion tokens.
The cap is a uniform generation-setting change, recorded in evaluation metadata;
truncated completions remain failures, not silent successes.

A budget violation or unavailable tokenizer fails before any evaluation request is sent.
The runner preflights every combination before modifying its output report. No content
is silently truncated to pass the budget. Original --full diagnostic remains available
and reproduces the old payload; --compact uses the new evaluated request exactly.

## Verification and next one-call check
76 tests passed, including eight new payload tests. They cover all 42 budgets, unchanged
prompt/history/state/grants, identical contexts across versions, schema equivalence,
retention of scoped facts and every global business rule, category retrieval, budget
failure before transport, and the compact diagnostic. Existing transport/validation
regressions remain in the suite; no test was removed.

Use a local virtual environment; the production Python core still needs no dependencies:
```zsh
python3 -m venv .venv
.venv/bin/python -m pip install -r tools/requirements-eval.txt
.venv/bin/python -B tools/report_eval_payloads.py
.venv/bin/python -B -m unittest discover -s backend/tests -q
# In the terminal with GROQ_API_KEY already exported, make exactly ONE request:
.venv/bin/python -B tools/diagnose_groq.py --compact --prompt v3 --scenario size_conflict
```

First use of the tokenizer may download its vocabulary; subsequent calls use its cache.
This implementation was verified in a temporary environment without changing production
Python dependencies. The local compact diagnostic found no GROQ_API_KEY and made zero
requests. No 42-call live evaluation ran; saved real/mock evaluation results were not
rewritten. HTTP 200 for a compact request remains to be confirmed locally.

An 8000 TPM account limit also applies across successive requests: fitting each request
does not authorize firing 42 requests without pacing. Plan pacing/rate-limit handling
before the later authorized full run. Do not infer prompt superiority from size or
contract tests. Future real comparisons must all use the same scoped-eval-v1 strategy.
