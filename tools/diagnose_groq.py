"""ONE direct Python Groq request, no retries or evaluation loop.

Default: minimal model/messages/max_tokens request. Optional --full reproduces one
unchanged evaluation payload to diagnose a size rejection after minimal HTTP 200.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import direct_groq_eval as runner
from backend.app.services.menu import MenuService
from backend.app.services.evaluation import scenarios
from backend.app.services.action_policy import authorize_actions, policy_context
from backend.app.services.llm.prompts import build_messages
from tools.eval_payload import build_eval_messages, payload_measure, STRATEGY_VERSION, PayloadBudgetError


def diagnostic_payload(full=False, version='v1', scenario_id='normal_order', compact=False):
    if not full and not compact:
        return {'model': runner.MODEL, 'messages': [{'role': 'user', 'content': 'OK'}], 'max_tokens': 100}
    menu = MenuService()
    case = next(s for s in scenarios(menu) if s['id'] == scenario_id)
    grant = authorize_actions(case['initial_state'], case['authorized_actions'], menu)
    builder = build_eval_messages if compact else build_messages
    messages = builder(version, menu, case['initial_state'], case['input'], case['history'],
                              policy=policy_context(case['initial_state'], grant, 'composition'))
    return runner.request_body(messages, compact=compact)


def diagnose(*, full=False, version='v1', scenario_id='normal_order', compact=False):
    key = os.environ.get('GROQ_API_KEY', '').strip()
    payload = diagnostic_payload(full, version, scenario_id, compact)
    report = {'diagnostic': 'DIRECT_GROQ_ONE_REQUEST', 'payload_kind': ('compact_scenario' if compact else 'existing_full_scenario') if (full or compact) else 'minimal',
              'final_request_url': 'https://' + runner.HOST + runner.PATH,
              'model': runner.MODEL, 'api_key_present': bool(key), 'request_count': 0,
              'http_status': None, 'exception_type': None, 'exception_message': None,
              'proxy_variables_present': {k: bool(os.environ.get(k)) for k in (
                  'HTTPS_PROXY','https_proxy','HTTP_PROXY','http_proxy','ALL_PROXY','all_proxy','NO_PROXY','no_proxy')},
              'certificate_variables_present': {k: bool(os.environ.get(k)) for k in ('SSL_CERT_FILE','SSL_CERT_DIR')},
              'python_version': sys.version.split()[0], 'request_bytes': len(json.dumps(payload).encode()),
              'request_fields': sorted(payload), 'messages_count': len(payload['messages']),
              'uses_proxy_environment': False, 'follows_redirects': False}
    if compact:
        report['context_strategy'] = STRATEGY_VERSION
        report['payload_budget'] = payload_measure(payload['messages'])
    if not key or any(c.isspace() for c in key):
        report['blocked_reason'] = 'GROQ_API_KEY_MISSING_OR_INVALID'
        return report
    report['request_count'] = 1
    try:
        status, body = runner.post_https(payload, key, diagnostics=report)
        report['http_200'] = status == 200
        if status == 200:
            try:
                raw, finish = runner.parse_completion(body, key)
                report['completion_parsed'] = True
                report['finish_reason'] = finish
            except runner.DirectError as exc:
                report['completion_parsed'] = False
                report['parsing_error'] = exc.code
    except Exception as exc:
        report['http_200'] = report['http_status'] == 200
        report['exception_type'] = type(exc).__name__
        report['exception_message'] = runner.safe_diagnostic_text(str(exc), key)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--compact', action='store_true', help='Send ONE optimized scenario with a checked token budget')
    mode.add_argument('--full', action='store_true', help='Send one unchanged evaluation payload, not 42 calls')
    parser.add_argument('--prompt', choices=('v1','v2','v3'), default='v1')
    parser.add_argument('--scenario', default='normal_order', choices=[s['id'] for s in scenarios(MenuService())])
    args = parser.parse_args()
    try:
        result = diagnose(full=args.full, compact=args.compact, version=args.prompt, scenario_id=args.scenario)
    except PayloadBudgetError as exc:
        print(str(exc))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('http_200') else 1


if __name__ == '__main__':
    sys.exit(main())
