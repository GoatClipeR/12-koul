# Local-only direct Groq evaluation

Run from the repository root using Python 3.9+ (standard library only):

```zsh
set +x
read -rs "GROQ_API_KEY?Groq API key (hidden): "
print
export GROQ_API_KEY
python3 -B tools/direct_groq_eval.py
unset GROQ_API_KEY
```

Only GROQ_API_KEY is read. The runner never reads LLM_BASE_URL or other LLM environment
settings, loads dotenv files, or instantiates/calls the production provider abstraction.
It uses HTTPSConnection directly with fixed host api.groq.com, path
/openai/v1/chat/completions, and model openai/gpt-oss-120b. No redirects are followed.
The API key is not part of prompts, metadata, report fields or console output. Exceptions
and upstream error bodies are not logged. A response echoing the literal key is discarded.

The existing 14 scenarios, prompt files, system/menu/state/policy message builder,
action schema, authorization checks, atomic meal engine, price engine, scoring and
review-record functions are reused unchanged. Each scenario uses a fresh original
fixture state. There are 42 prompt/scenario combinations; no synthetic model replies
are substituted when Groq fails. The thin direct runner repeats only orchestration
and compatible report assembly, not business rules or scenario definitions.

Requests use temperature 0 and response_format json_object. At most two attempts per
combination, with bounded retries for connection/timeout/413/429/5xx
failures. Every attempt waits 65 seconds after the preceding attempt completes;
429 responses extend that wait to 120 seconds. An initial 65-second cooldown
also applies. The full 6000 input budget plus 1024 completion cap reserves
7024 tokens per attempt, below the observed 8000 TPM limit. Avoid other Groq
requests on this account during the evaluation. A clean 42-case run takes at
least 45.5 minutes plus request and processing time. Attempts, errors, elapsed
time, and per-prompt counts are checkpointed; CLI progress contains no credentials. A 30-second request/read deadline and socket timeout apply to each attempt;
platform DNS resolution can exceed socket timeouts. Responses are bounded to 1 MB;
JSON depth/numeric limits are shared with the existing safe parser. Malformed, truncated,
non-stop or empty completions do not mutate state and are recorded as failures.

Results are atomically checkpointed after every combination to
`notebook/real-results.local.json` (already ignored). Existing results are overwritten
only after a configured run begins producing records; a missing key leaves them intact.
`metadata.execution_path` is DIRECT_GROQ_EVAL and `production_provider_used` is false.
Timestamp, scenario version/hash, menu/prompt hashes, per-row message hashes and generation
settings are recorded. Partial runs have `metadata.completed=false`.

Console output contains only execution counts and the result destination. Counts separate:
- HTTP attempts, including retries;
- HTTP 200 responses versus non-200/transport failures;
- usable model-content responses versus failed calls/invalid envelopes;
- combinations with/without model responses and complete stop responses;
- accepted deterministic action batches.

Receiving a model response does not mean its JSON/actions or behavior passed. A valid
response safely refusing an intentionally invalid fixture can fail exact fixture match
while preserving all deterministic invariants. Contract results, lexical diagnostics,
behavior/grounding and human review remain separate. Semantic comparison and best-prompt
selection require inspection of real responses, never keyword or mock scores alone.

Offline regression tests (dummy credentials and fake transport only):
```bash
python3 -B -m unittest backend.tests.test_direct_groq_eval -v
python3 -B -m unittest discover -s backend/tests -q
```

## One-call HTTP diagnosis (before any further 42-call run)

```bash
python3 -B tools/diagnose_groq.py
```

Run in the terminal where GROQ_API_KEY is already exported. This uses the exact
http.client transport used by the runner, with just model, user message `OK`, and
max_tokens=100. It makes one request, without retries, and never writes evaluation
results. No key means zero requests. Diagnostic HTTP 200 is reported independently
of completion parsing: a reasoning model can exhaust 100 output tokens.

Opt-in diagnostics report the fixed URL, model, payload bytes/fields, HTTP status,
redacted bounded response/error text, and redacted exception type/message. No request
headers are logged. Proxy and certificate environment variables are reported only as
presence booleans. http.client does not use proxy environment variables; curl can.

After minimal HTTP 200, this optional command reproduces ONE unchanged full scenario:
```bash
python3 -B tools/diagnose_groq.py --full --prompt v1 --scenario normal_order
```

The inspected failed report contained 42 HTTP 413 responses, not transport failures.
The first scenario's serialized payload sizes were 35210/35868/38546 bytes for V1/V2/V3,
versus 100 bytes for the minimal diagnostic. The old transport discarded non-200
bodies, so the exact server limit/message cannot be recovered retrospectively. A new
full-payload diagnostic can reveal whether the size rejection concerns token budget
or another request limit. No prompt, scenario, generation setting for evaluation,
production provider, meal engine or validation rule was changed to conceal the failure.
Do not rerun the entire evaluation until the minimal request is HTTP 200 and the
full-payload size rejection is understood/resolved.

## Compact payload strategy (supersedes original full-context runner instructions)

The direct runner now uses scoped-eval-v1 and requires the evaluation-only tokenizer:
`python -m pip install -r tools/requirements-eval.txt` in a local virtual environment.
The production provider/core remain untouched. See `docs/eval-payload-optimization.md`
and the per-component 42-case report `docs/eval-payload-sizes.json`.

`tools/diagnose_groq.py --compact --prompt v3 --scenario size_conflict` sends ONE optimized
request. `--full` retains the old full-context diagnostic. The minimal default remains
unchanged. Compact calls include max_completion_tokens=1024 and a checked input budget;
all prompt versions use identical context projection and generation settings.
Do not rerun the 42 live evaluations until the compact one-call check succeeds and
the conservative per-minute pacing above is applied. Payload reduction alone does not remove aggregate TPM limits.
