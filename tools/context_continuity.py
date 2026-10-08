"""Stage 3.9 offline context prototype. No production imports this module.

Only a closed, full-message grammar plus an engine-validated receipt permits
forgetting a completed command. Unknown text/questions retain verbatim evidence.
Memory never authorizes actions; language is a quoted user preference, not policy.
"""
from copy import deepcopy
from dataclasses import dataclass
import json
import re
from backend.app.services.meal_engine import apply_response
from backend.app.services.llm.prompts import build_messages
from backend.app.services.llm.production_context import compact_messages
from backend.app.services.action_policy import policy_context
from tools.history_budget_prototype import Budget,BudgetExceeded,metrics,check_output


@dataclass(frozen=True)
class Turn:
    user: str
    assistant: str
    actions: list
    before: dict
    after: dict


def record(menu,state,user,assistant,actions,authorization=None):
    # Actual unchanged validator/engine; this is never built from a model's claims.
    check_output(json.dumps({'message':assistant,'actions':actions},ensure_ascii=False))
    after=apply_response(state,{'message':assistant,'actions':actions},menu,authorization=authorization)
    return Turn(user,assistant,deepcopy(actions),deepcopy(state),after)


def item_id(text,menu):
    text=text.casefold()
    aliases={'poulet':'salad.ingredient.grilled_chicken'}
    matches=[i['id'] for i in menu.items('salad') if
             text in {name.casefold() for name in i['name'].values()} or
             (i['slot']=='sauce' and text in {'sauce '+name.casefold() for name in i['name'].values()})]
    if text in aliases:matches.append(aliases[text])
    return matches[0] if len(set(matches))==1 else None


def command_actions(user,menu):
    """Closed grammar only. Any suffix/condition/unknown item means retain text."""
    expected=None
    match=re.fullmatch(r'(Ajoute|Enlève) (?:du |de la |de l’|des |le |la |l’)?(.+)\.',user)
    if match:
        target=item_id(match[2],menu)
        if target:
            expected=[{'type':'ADD_ITEM' if match[1]=='Ajoute' else 'REMOVE_ITEM','item_id':target}]
    match=re.fullmatch(r'Passe (?:en|à une) (grande|petite) salade\.',user)
    if match:expected=[{'type':'SET_SIZE','size':'large' if match[1]=='grande' else 'small'}]
    match=re.fullmatch(r'Je veux une (grande|petite) salade avec (.+)\.',user)
    if match:
        names=re.split(r', | et ',match[2]);ids=[item_id(name,menu) for name in names]
        if all(ids):
            expected=[{'type':'SET_CATEGORY','category':'salad'},
                      {'type':'SET_SIZE','size':'large' if match[1]=='grande' else 'small'},
                      *[{'type':'ADD_ITEM','item_id':i} for i in ids]]
    return expected


def completed_command(turn,menu):
    expected=command_actions(turn.user,menu)
    return expected is not None and expected==turn.actions


# These exact receipts are disposable, never arbitrary model prose/open questions.
ACKS=frozenset({'Proposition scriptée, moteur validé.','Composition mise à jour.',
               'Votre préférence est notée.','D’accord.','Avec plaisir.'})
LANGUAGE={'Please speak English.':'en','Réponds en anglais.':'en','Réponds en français.':'fr'}


def keep_choices(text):
    return re.fullmatch(r'Je souhaite revenir au repas\. (?:Merci de garder mes choix\. ){1,30}',text) is not None


# Closed standalone queries only. Unknown references require lossless fallback.
STANDALONE=frozenset({'Quelles bases proposes-tu ?', 'Est-ce complet ?',
    'Ajoute une sauce.', 'Récapitule ma salade.', 'Revenons à ma salade.',
    'Écris un poème.', 'Bonjour.', 'Où en est ma salade ?', 'Tu as quoi comme boissons ?'})


def memory(turns,menu):
    summary={};unresolved=[];retired=[]
    for index,turn in enumerate(turns):
        if completed_command(turn,menu) and turn.assistant in ACKS:
            retired.append({'turn':index+1,'reason':'completed_command_in_state'})
        elif turn.user=='Merci.' and turn.assistant=='Avec plaisir.' and not turn.actions:
            retired.append({'turn':index+1,'reason':'closed_courtesy'})
        elif turn.user=='Écris un poème.' and turn.assistant=='Je reste dans le menu.' and not turn.actions:
            retired.append({'turn':index+1,'reason':'closed_out_of_domain'})
        elif keep_choices(turn.user) and turn.assistant in ACKS and not turn.actions:
            summary['keep_choices_request']='Merci de garder mes choix.'
        elif turn.user in LANGUAGE and turn.assistant in ACKS and not turn.actions:
            summary['language_request']={'value':LANGUAGE[turn.user],'quote':turn.user}
        elif turn.user=='Je préfère sans sauce pour le moment.' and turn.assistant in ACKS and not turn.actions:
            summary['constraints']=['Je préfère sans sauce pour le moment.']
        else:
            # Preserve unknown decisions, constraints and their resolving context.
            # Never pretend a regex can safely summarize arbitrary prose.
            unresolved.append([turn.user,turn.assistant])
    if unresolved:summary['unresolved_turns']=unresolved
    return summary,retired


def history(turns):
    return [m for t in turns for m in ({'role':'user','content':t.user},{'role':'assistant','content':t.assistant})]


def plan(menu,state,message,turns,*,authorization=None,budget=Budget()):
    # Ensure the receipt chain agrees with the authoritative snapshot.
    for i,t in enumerate(turns):
        if i and t.before!=turns[i-1].after:raise ValueError('Broken receipt chain')
        if not isinstance(t.user,str) or not 1<=len(t.user)<=1000:raise ValueError('Invalid user message')
    if turns and turns[-1].after!=state:raise ValueError('State does not match receipts')
    base=compact_messages(build_messages('v3',menu,state,message,policy=policy_context(state,authorization,'composition')))
    full=[base[0],*history(turns),base[-1]]
    original=metrics(full,budget,2*len(turns),0)
    if original['admitted']:
        return {'messages':full,'metrics':original,'summary':{},'retired':[],'original_metrics':original,'recent_pairs':len(turns)}
    if command_actions(message,menu) is None and message not in STANDALONE and not keep_choices(message):
        # Do not remove evidence needed for 'undo that old change' or anaphora.
        from tools.history_budget_prototype import plan as lossless_plan
        fallback=lossless_plan(menu,state,message,history(turns),authorization=authorization,budget=budget)
        return {**fallback,'summary':{},'retired':[],'recent_pairs':min(len(turns),budget.recent_pairs),
                'lossless_fallback':True}
    count=min(len(turns),budget.recent_pairs);split=len(turns)-count
    summary,retired=memory(turns[:split],menu)
    middle=[]
    if summary:
        middle=[{'role':'user','content':json.dumps({'untrusted_conversation_memory':summary},ensure_ascii=False,separators=(',',':'))}]
    candidate=[base[0],*middle,*history(turns[split:]),base[-1]]
    cost=metrics(candidate,budget,2*len(turns),2*split)
    cost['historical_messages_examined']=cost.pop('historical_messages_preserved')
    cost['old_messages_considered']=cost.pop('historical_messages_archived')
    cost['retired_turns']=len(retired);cost['summary_turns_raw']=len(summary.get('unresolved_turns',[]))
    if not cost['admitted']:
        raise BudgetExceeded({'original':original,'candidate':cost,'summary':summary,'retired':retired})
    return {'messages':candidate,'metrics':cost,'summary':summary,'retired':retired,
            'original_metrics':original,'recent_pairs':count}
