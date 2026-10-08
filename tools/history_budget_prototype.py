"""Stage 3.8 OFFLINE prototype. Not imported by production or evaluation.

Lossless archive of exact repeated messages; recent pairs remain verbatim.
Non-redundant text is never silently dropped. Failure means DO NOT SEND.
No provider/network implementation: output reservation is not a server-side cap.
"""
from copy import deepcopy
from dataclasses import dataclass
import json
from backend.app.services.llm.prompts import build_messages
from backend.app.services.llm.production_context import compact_messages
from backend.app.services.action_policy import policy_context
from tools.eval_payload import token_count


@dataclass(frozen=True)
class Budget:
    max_context_tokens: int = 6500  # Includes conservative message framing.
    max_output_tokens: int = 1024
    safety_margin: int = 476
    request_limit: int = 8000
    recent_pairs: int = 2

    def __post_init__(self):
        values=(self.max_context_tokens,self.max_output_tokens,self.safety_margin,
                self.request_limit,self.recent_pairs)
        if any(type(x) is not int or x <= 0 for x in values):
            raise ValueError('Budget values must be positive integers')
        if self.max_context_tokens+self.max_output_tokens+self.safety_margin > self.request_limit:
            raise ValueError('Configured budgets exceed request limit')


class BudgetExceeded(ValueError):
    def __init__(self, metrics):
        self.metrics=metrics
        super().__init__('CONTEXT_BUDGET_EXCEEDED: no request may be sent; history retained')


def validate_history(history):
    if not isinstance(history,list) or len(history)%2 or len(history)>200:
        raise ValueError('Expected at most 100 complete user/assistant pairs')
    for index,entry in enumerate(history):
        if (not isinstance(entry,dict) or set(entry)!={'role','content'}
            or entry['role'] != ('user' if index%2==0 else 'assistant')
            or not isinstance(entry['content'],str) or not 1<=len(entry['content'])<=4000):
            raise ValueError('Invalid historical message')


def archive(history):
    """Exact pairs in a dictionary; run lengths retain every occurrence and its order."""
    entries=[];runs=[];indices={}
    for offset in range(0,len(history),2):
        pair=(history[offset]['content'],history[offset+1]['content'])
        if pair not in indices:
            indices[pair]=len(entries);entries.append(list(pair))
        ref=indices[pair]
        if runs and runs[-1][0]==ref:
            runs[-1][1]+=1
        else:
            runs.append([ref,1])
    return {'type':'untrusted_history_archive_v1','entry_columns':['user','assistant'],
            'entries':entries,'chronological_runs':runs,
            'run_columns':['entry_index','repeat_count']}


def unarchive(value):
    history=[]
    for index,count in value['chronological_runs']:
        user,assistant=value['entries'][index]
        for _ in range(count):
            history.extend([{'role':'user','content':user},{'role':'assistant','content':assistant}])
    return history


def metrics(messages,budget,history_count,archived_count):
    content=sum(token_count(m['content']) for m in messages)
    reserve=512+16*len(messages)
    estimated=content+reserve
    return {'input_content_tokens':content,'framing_reserve':reserve,
            'estimated_input_tokens':estimated,'output_budget':budget.max_output_tokens,
            'safety_margin':budget.safety_margin,
            'total_budget':estimated+budget.max_output_tokens+budget.safety_margin,
            'messages_sent':len(messages),'historical_messages_preserved':history_count,
            'historical_messages_archived':archived_count,
            'recent_messages_verbatim':history_count-archived_count,
            'admitted':estimated<=budget.max_context_tokens}


def plan(menu,state,message,history,*,authorization=None,budget=Budget()):
    validate_history(history)
    # Existing validation and V3 unchanged. Full prototype journal is independent
    # of the production 40-message / 16000-character window; no hidden truncation.
    base=compact_messages(build_messages('v3',menu,state,message,
        policy=policy_context(state,authorization,'composition')))
    full=[base[0],*deepcopy(history),base[-1]]
    initial=metrics(full,budget,len(history),0)
    if initial['admitted']:
        return {'messages':full,'metrics':initial,'archive':None,'original_metrics':initial}
    split=max(0,len(history)-2*budget.recent_pairs)
    if not split:
        raise BudgetExceeded(initial)
    saved=archive(history[:split])
    data={'role':'user','content':json.dumps(saved,ensure_ascii=False,separators=(',',':'))}
    candidate=[base[0],data,*deepcopy(history[split:]),base[-1]]
    reduced=metrics(candidate,budget,len(history),split)
    if not reduced['admitted']:
        raise BudgetExceeded({'original':initial,'candidate':reduced})
    return {'messages':candidate,'metrics':reduced,'archive':saved,'original_metrics':initial}


def check_output(raw, budget=Budget()):
    """Offline post-response guard; cannot prevent already billed generation tokens."""
    if not isinstance(raw,str):
        raise ValueError('Expected structured response text')
    count=token_count(raw)
    if count>budget.max_output_tokens:
        raise BudgetExceeded({'output_tokens':count,'output_budget':budget.max_output_tokens})
    return count
