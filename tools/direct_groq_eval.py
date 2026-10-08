"""Local-only Stage 1 runner. Fixed Groq endpoint; no production provider execution.

Run: python3 -B tools/direct_groq_eval.py
Only GROQ_API_KEY is read. Results are checkpointed after every combination.
"""
import hashlib
import http.client
import json
import os
import re
import socket
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.menu import MenuService
from backend.app.services.evaluation import scenarios, score_scenario, comparison
from backend.app.services.evaluation_review import review_record, CRITERIA
from backend.app.services.llm.prompts import PROMPT_DIR
from tools.eval_payload import build_eval_messages, payload_measure, scope_categories, STRATEGY_VERSION, INPUT_BUDGET, COMPLETION_BUDGET, PayloadBudgetError
from backend.app.services.action_policy import authorize_actions, policy_context
from backend.app.services.meal_engine import apply_response
from backend.app.services.price_engine import quote
from backend.app.schemas.actions import validate_response
from backend.app.services.json_guard import safe_loads
from backend.app.services.errors import DomainError

HOST = 'api.groq.com'
PATH = '/openai/v1/chat/completions'
MODEL = 'openai/gpt-oss-120b'
OUTPUT = ROOT / 'notebook/real-results.local.json'
TIMEOUT = 30
MAX_ATTEMPTS = 2
MAX_BODY = 1_000_000
COOLDOWN_SECONDS = 65
RATE_LIMIT_BACKOFF_SECONDS = 120


class ConservativePacer:
    """One request per rolling minute, including failures and an initial cooldown.

    Assumes no other process shares the account's TPM quota during this run.
    Reserving the full input budget plus completion cap leaves 976 tokens spare.
    """
    def __init__(self, sleep=time.sleep, clock=time.monotonic):
        self.sleep = sleep
        self.clock = clock
        self.ready_at = clock() + COOLDOWN_SECONDS

    def wait(self):
        started = self.clock()
        while self.clock() < self.ready_at:
            self.sleep(min(30, self.ready_at - self.clock()))
        return self.clock() - started

    def completed(self, status):
        delay = RATE_LIMIT_BACKOFF_SECONDS if status == 429 else COOLDOWN_SECONDS
        self.ready_at = self.clock() + delay


class DirectError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def request_body(messages, *, compact=False):
    body = {'model': MODEL, 'messages': messages, 'temperature': 0,
            'response_format': {'type': 'json_object'}}
    if compact:
        body['max_completion_tokens'] = COMPLETION_BUDGET
    return body


def safe_diagnostic_text(value, api_key):
    """Redact before truncation; never emit request headers or raw exception objects."""
    text = value.decode('utf-8', errors='replace') if isinstance(value, bytes) else str(value)
    def redact(text):
        if api_key:
            text = text.replace(api_key, '[REDACTED]')
            text = text.replace(json.dumps(api_key)[1:-1], '[REDACTED]')
        text = re.sub(r'(?i)bearer\s+[^\s"\\,}]+', '[REDACTED]', text)
        text = re.sub(r'\b(?:gsk_[A-Za-z0-9_-]+|sk-[A-Za-z0-9_-]{12,})', '[REDACTED]', text)
        return text
    try:
        parsed = safe_loads(text, max_bytes=MAX_BODY, max_depth=24)
        def clean(item):
            if isinstance(item, dict):
                return {redact(k): clean(v) for k, v in item.items()
                        if k.lower() not in ('authorization', 'proxy-authorization', 'api_key', 'groq_api_key')}
            if isinstance(item, list):
                return [clean(v) for v in item]
            return redact(item) if isinstance(item, str) else item
        text = json.dumps(clean(parsed), ensure_ascii=False)
    except (ValueError, TypeError, RecursionError):
        text = '\n'.join(line for line in text.splitlines() if 'authorization' not in line.lower())
        text = redact(text)
    return text[:4096]


def post_https(payload, api_key, *, diagnostics=None):
    """http.client never follows redirects. No URL/environment parsing is involved."""
    encoded = json.dumps(payload).encode('utf-8')
    if diagnostics is not None:
        diagnostics.update(final_request_url='https://' + HOST + PATH, model=MODEL,
                           api_key_present=bool(api_key), http_status=None, request_bytes=len(encoded),
                           timeout_seconds=TIMEOUT, transport='http.client.HTTPSConnection',
                           follows_redirects=False, uses_proxy_environment=False,
                           exception_type=None, exception_message=None)
    connection = http.client.HTTPSConnection(HOST, timeout=TIMEOUT)
    deadline = time.monotonic() + TIMEOUT
    try:
        connection.request('POST', PATH, body=encoded, headers={
            'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'})
        sock = connection.sock
        def remaining():
            budget = deadline - time.monotonic()
            if budget <= 0:
                raise TimeoutError()
            if sock is not None:
                sock.settimeout(budget)
        remaining()
        response = connection.getresponse()
        status = response.status
        if diagnostics is not None:
            diagnostics['http_status'] = status
            diagnostics['http_reason'] = safe_diagnostic_text(response.reason, api_key)
        # Error bodies are opt-in diagnostics only. Redirects are never followed.
        if status != 200 and diagnostics is None:
            return status, b''
        body_limit = MAX_BODY if status == 200 else 16384
        body = bytearray()
        while len(body) <= body_limit:
            remaining()
            part = response.read1(min(65536, body_limit + 1 - len(body)))
            if not part:
                break
            body.extend(part)
        if diagnostics is not None:
            diagnostics['response_body'] = safe_diagnostic_text(bytes(body), api_key)
            diagnostics['response_body_truncated'] = len(body) > body_limit or len(body) > 4096
        if status == 200 and len(body) > MAX_BODY:
            raise DirectError('PROVIDER_RESPONSE_TOO_LARGE')
        return status, bytes(body) if status == 200 else b''
    except Exception as exc:
        if diagnostics is not None:
            diagnostics['exception_type'] = type(exc).__name__
            diagnostics['exception_message'] = safe_diagnostic_text(str(exc), api_key)
        raise
    finally:
        connection.close()


def parse_completion(body, api_key):
    try:
        data = safe_loads(body, max_bytes=MAX_BODY, max_depth=24)
        choice = data['choices'][0]
        raw = choice['message']['content']
        if not isinstance(raw, str) or not raw.strip() or len(raw.encode('utf-8')) > 100_000:
            raise ValueError()
        if api_key in raw:
            raise DirectError('PROVIDER_SECRET_ECHO_BLOCKED')
        finish = choice.get('finish_reason')
        return raw, finish if finish in ('stop', 'length', 'content_filter', 'tool_calls') else 'unknown'
    except DirectError:
        raise
    except (ValueError, TypeError, KeyError, IndexError, RecursionError):
        raise DirectError('PROVIDER_INVALID_RESPONSE') from None


def direct_call(messages, api_key, transport=post_https, sleep=time.sleep, *, pacer=None):
    pacer = pacer if pacer is not None else ConservativePacer(sleep)
    attempts = []
    for index in range(MAX_ATTEMPTS):
        waited = pacer.wait()
        status = None
        retry = False
        try:
            status, body = transport(request_body(messages, compact=True), api_key)
            if status != 200:
                code = 'PROVIDER_REDIRECT_BLOCKED' if 300 <= status < 400 else 'PROVIDER_HTTP_ERROR'
                retry = status in (413, 429) or status >= 500
                raise DirectError(code)
            raw, finish = parse_completion(body, api_key)
            attempts.append({'http_status': status, 'outcome': 'MODEL_RESPONSE', 'error': None, 'pacing_wait_seconds': waited})
            return raw, finish, attempts, None
        except DirectError as exc:
            code = exc.code
        except (TimeoutError, socket.timeout):
            code, retry = 'PROVIDER_TIMEOUT', True
        except (OSError, http.client.HTTPException):
            code, retry = 'PROVIDER_CONNECTION_FAILURE', True
        except Exception:
            code = 'PROVIDER_UNEXPECTED_ERROR'
        finally:
            pacer.completed(status)
        attempts.append({'http_status': status, 'outcome': 'FAILED', 'error': code, 'pacing_wait_seconds': waited})
        if not retry or index == MAX_ATTEMPTS - 1:
            return None, None, attempts, {'code': code, 'details': {'attempts': len(attempts), 'http_status': status}}


def evaluate_actions(scenario, raw, transport_error, finish, menu, authorization):
    result = {'accepted': False, 'response': None, 'raw_response': raw,
              'state': deepcopy(scenario['initial_state']), 'quote': None, 'error': transport_error}
    if transport_error:
        return result
    if finish != 'stop':
        result['error'] = {'code': 'PROVIDER_INCOMPLETE_COMPLETION', 'details': {'finish_reason': finish}}
        return result
    try:
        result['response'] = validate_response(raw, menu)
        candidate = apply_response(scenario['initial_state'], result['response'], menu, authorization=authorization)
        pricing = quote(candidate, menu)
        result.update(accepted=True, state=candidate, quote=pricing)
    except DomainError as exc:
        result['error'] = exc.as_dict()
    return result


def execution_summary(rows):
    attempts = [a for row in rows for a in row['direct_request']['attempts']]
    returned = sum(row['direct_request']['model_response_received'] for row in rows)
    return {'planned_combinations': 42, 'combinations_attempted': len(rows),
            'http_attempts': len(attempts),
            'http_429_rate_limit_errors': sum(a['http_status'] == 429 for a in attempts),
            'http_413_payload_limit_errors': sum(a['http_status'] == 413 for a in attempts),
            'http_200_responses': sum(a['http_status'] == 200 for a in attempts),
            'http_non_200_or_transport_failures': sum(a['http_status'] != 200 for a in attempts),
            'successful_calls_with_model_response': sum(a['outcome'] == 'MODEL_RESPONSE' for a in attempts),
            'failed_calls_including_invalid_envelopes': sum(a['outcome'] == 'FAILED' for a in attempts),
            'combinations_with_model_response': returned,
            'combinations_without_model_response': len(rows) - returned,
            'complete_model_responses': sum(row['direct_request']['finish_reason'] == 'stop' for row in rows),
            'all_42_received_model_responses': len(rows) == returned == 42,
            'accepted_action_batches': sum(row['validation_result']['accepted'] for row in rows)}


def save_report(report, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + '.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(output)


def run_evaluation(*, transport=post_https, sleep=time.sleep, clock=time.monotonic, output=OUTPUT, progress=None):
    api_key = os.environ.get('GROQ_API_KEY', '').strip()
    if not api_key or any(c.isspace() for c in api_key):
        raise DirectError('GROQ_API_KEY_MISSING_OR_INVALID')
    started = clock()
    menu = MenuService()
    cases = scenarios(menu)
    # Preflight all payloads before sending or overwriting any report.
    prepared = {}
    for version in ('v1','v2','v3'):
        for case in cases:
            grant = authorize_actions(case['initial_state'], case['authorized_actions'], menu)
            prepared[version, case['id']] = build_eval_messages(
                version, menu, case['initial_state'], case['input'], case['history'],
                policy=policy_context(case['initial_state'], grant, 'composition'))
    pacer = ConservativePacer(sleep, clock)
    digest = lambda data: hashlib.sha256(data).hexdigest()
    report = {'mode': 'real', 'provider': 'Groq direct HTTPS', 'model': MODEL,
              'metadata': {'execution_path': 'DIRECT_GROQ_EVAL', 'production_provider_used': False,
                'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'scenario_version': '2.0',
                'report_schema_version': 'direct-1.0', 'endpoint': 'https://' + HOST + PATH,
                'scenario_hash': digest(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()),
                'menu_hash': digest(json.dumps(menu.snapshot(), sort_keys=True, ensure_ascii=False).encode()),
                'prompt_hashes': {v: digest((PROMPT_DIR / ('prompt_' + v + '.txt')).read_bytes()) for v in ('v1','v2','v3')},
                'generation_settings': {'temperature': 0, 'response_format': {'type': 'json_object'}, 'max_completion_tokens': COMPLETION_BUDGET},
                'context_strategy': STRATEGY_VERSION, 'input_token_budget': INPUT_BUDGET,
                'input_tokenizer': 'o200k_harmony',
                'pacing': {'cooldown_seconds': COOLDOWN_SECONDS, 'initial_cooldown': True,
                    'after_429_seconds': RATE_LIMIT_BACKOFF_SECONDS, 'account_tpm_limit': 8000,
                    'maximum_reserved_tokens_per_attempt': INPUT_BUDGET + COMPLETION_BUDGET,
                    'assumes_exclusive_account_usage': True},
                'timeout_seconds': TIMEOUT, 'max_attempts_per_combination': MAX_ATTEMPTS,
                'completed': False},
              'limitations': 'Fixture match is not model quality. Lexical diagnostics do not establish grounding, ambiguity, '
                'refusal or injection resistance. Semantic review remains pending. Invalid fixture actions can be safely '
                'refused by a real model. Request/read deadlines bound normal socket operations; system DNS resolution '
                'may exceed a socket timeout. No production provider is instantiated or invoked.',
              'rows': [], 'comparison': {},
              'model_quality_comparison': {k: {v:'PENDING_REVIEW' for v in ('v1','v2','v3')} for k in CRITERIA}}
    for version in ('v1','v2','v3'):
        for scenario in cases:
            grant = authorize_actions(scenario['initial_state'], scenario['authorized_actions'], menu)
            messages = prepared[version, scenario['id']]
            raw, finish, attempts, error = direct_call(messages, api_key, transport, sleep, pacer=pacer)
            result = evaluate_actions(scenario, raw, error, finish, menu, grant)
            score = score_scenario(scenario, result, menu)
            row = {'mode': 'REAL MODEL EVALUATION', 'prompt': version, 'scenario': scenario['id'],
                   'input': scenario['input'], 'history': scenario['history'], 'initial_state': scenario['initial_state'],
                   'authorized_actions': scenario['authorized_actions'], 'model_response': result['raw_response'],
                   'validation_result': {'accepted': result['accepted'], 'error': result['error']},
                   'resulting_meal_state': result['state'], 'quote': result['quote'],
                   'expected_behavior': scenario['expected_behavior'], 'expected_state': scenario['expected_state'],
                   'expected_error': scenario['expected_error'], 'expected_actions': scenario['expected_actions'],
                   **score, 'fixture_contract_match': score['contract_pass'], **review_record(scenario, result, menu),
                   'pass_fail': 'PENDING_REVIEW' if result['response'] is not None else 'FAIL',
                   'direct_request': {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'attempts': attempts,
                                      'model_response_received': raw is not None, 'finish_reason': finish,
                                      'payload_budget': payload_measure(messages),
                                      'scoped_categories': scope_categories(scenario['initial_state'], scenario['input'], scenario['history']),
                                      'messages_sha256': digest(json.dumps(messages, ensure_ascii=False).encode())}}
            report['rows'].append(row)
            report['comparison'] = comparison(report['rows'])
            report['execution_summary'] = execution_summary(report['rows'])
            report['execution_summary']['elapsed_seconds'] = round(clock() - started, 3)
            report['per_prompt_execution'] = {
                v: dict(execution_summary([r for r in report['rows'] if r['prompt'] == v]),
                        planned_combinations=14)
                for v in ('v1', 'v2', 'v3')}
            for summary in report['per_prompt_execution'].values():
                summary.pop('all_42_received_model_responses')
                summary['all_14_received_model_responses'] = summary['combinations_with_model_response'] == 14
            if output is not None:
                save_report(report, output)
            if progress is not None:
                progress(version, scenario['id'], report['execution_summary'])
    report['metadata']['completed'] = True
    report['metadata']['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
    if output is not None:
        save_report(report, output)
    return report


def main():
    try:
        print('DIRECT_GROQ_EVAL: 42 combinations; 65s cooldown before each attempt, '
              '120s after 429. Avoid concurrent Groq usage. Semantic review remains pending.', flush=True)
        def progress(version, scenario, summary):
            print(f"{summary['combinations_attempted']}/42 {version}/{scenario}: "
                  f"HTTP 200={summary['http_200_responses']}, "
                  f"model responses={summary['combinations_with_model_response']}, "
                  f"failed calls={summary['failed_calls_including_invalid_envelopes']}, "
                  f"elapsed={summary['elapsed_seconds']}s", flush=True)
        report = run_evaluation(progress=progress)
    except PayloadBudgetError as exc:
        print(str(exc))
        return 2
    except DirectError as exc:
        print(exc.code + ': export GROQ_API_KEY privately in this terminal; no requests made.')
        return 2
    except Exception:
        print('DIRECT_GROQ_EVAL_FAILED: inspect any checkpoint report; no exception details logged.')
        return 1
    print(json.dumps(report['execution_summary'], indent=2))
    print(json.dumps(report['per_prompt_execution'], indent=2))
    print('Saved notebook/real-results.local.json; semantic review is pending.')
    return 0 if report['execution_summary']['all_42_received_model_responses'] else 1


if __name__ == '__main__':
    sys.exit(main())
