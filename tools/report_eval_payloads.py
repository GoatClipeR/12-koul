"""Offline before/after report for all 42 evaluation requests. No Groq calls."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.eval_payload import build_eval_messages, payload_measure, component_breakdown, STRATEGY_VERSION
from backend.app.services.menu import MenuService
from backend.app.services.evaluation import scenarios
from backend.app.services.action_policy import authorize_actions, policy_context
from backend.app.services.llm.prompts import build_messages


def report_payloads():
    menu=MenuService();rows=[]
    for version in ('v1','v2','v3'):
        for case in scenarios(menu):
            grant=authorize_actions(case['initial_state'],case['authorized_actions'],menu)
            policy=policy_context(case['initial_state'],grant,'composition')
            args=(version,menu,case['initial_state'],case['input'],case['history'])
            before=build_messages(*args,policy=policy)
            after=build_eval_messages(*args,policy=policy)
            rows.append({'prompt':version,'scenario':case['id'],
                         'before':payload_measure(before),'after':payload_measure(after),
                         'before_components':component_breakdown(before,version),
                         'after_components':component_breakdown(after,version)})
    return {'strategy':STRATEGY_VERSION,'live_calls':0,
            'method':'o200k_harmony content token counts plus 512 + 16/message framing reserve. Component tokens are independently measured and not exactly additive across BPE boundaries. No claim to reproduce Groq exact TPM accounting.',
            'rows':rows,'max_after_budgeted_tokens':max(r['after']['budgeted_input_tokens'] for r in rows)}


if __name__=='__main__':
    report=report_payloads()
    root=Path(__file__).resolve().parents[1]
    (root/'docs/eval-payload-sizes.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    for v in ('v1','v2','v3'):
        rows=[r for r in report['rows'] if r['prompt']==v]
        print(v,'before:',min(r['before']['budgeted_input_tokens'] for r in rows),'-',max(r['before']['budgeted_input_tokens'] for r in rows),
              'after:',min(r['after']['budgeted_input_tokens'] for r in rows),'-',max(r['after']['budgeted_input_tokens'] for r in rows))
