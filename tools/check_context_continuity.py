"""Stage 3.9 offline comparison; no provider, secrets or network."""
import json
from backend.app.services.menu import MenuService
from backend.app.services.meal_engine import create_meal
from backend.app.services.action_policy import authorize_actions
from tools.context_continuity import plan,record,history,memory
from tools.history_budget_prototype import plan as old_plan,BudgetExceeded,archive,Budget,metrics
from tools.check_history_budget import salad
from tools.eval_payload import token_count


def act(kind,**fields):return dict(type=kind,**fields)
def add(name):return act('ADD_ITEM',item_id='salad.'+name)
def remove(name):return act('REMOVE_ITEM',item_id='salad.'+name)


def script():
    ack='Composition mise à jour.'
    return [
        ('Je veux une grande salade avec poulet et tomate.',ack,[act('SET_CATEGORY',category='salad'),act('SET_SIZE',size='large'),add('ingredient.grilled_chicken'),add('ingredient.tomato')]),
        ('Ajoute du maïs.',ack,[add('ingredient.corn')]),
        ('Quelles bases proposes-tu ?', 'Laitue, roquette, chou rouge et épinards.',[act('RECOMMEND_ITEM',item_id='salad.base.lettuce')]),
        ('Ajoute de la laitue.',ack,[add('base.lettuce')]),
        ('Enlève le maïs.',ack,[remove('ingredient.corn')]),
        ('Écris un poème.','Je reste dans le menu.',[]),
        ('Revenons à ma salade.','Votre composition reste disponible.',[]),
        ('Enlève la tomate.',ack,[remove('ingredient.tomato')]),
        ('Ajoute du concombre.',ack,[add('ingredient.cucumber')]),
        ('Passe à une petite salade.',ack,[act('SET_SIZE',size='small')]),
        ('Ajoute une sauce.','Quelle sauce souhaitez-vous ?',[]),
        ('Ajoute de la sauce Caesar.',ack,[add('sauce.caesar')]),
        ('Est-ce complet ?','Il manque un topping.',[]),
        ('Enlève le poulet.',ack,[remove('ingredient.grilled_chicken')]),
        ('Récapitule ma salade.','Petite salade : laitue, concombre et sauce Caesar. Il manque un ingrédient et un topping.',[]),
    ]


def grant(menu,state,actions):
    protected=[a for a in actions if a['type']=='REMOVE_ITEM']
    return authorize_actions(state,protected,menu) if protected else None


def sizes(messages):
    prefix,raw=messages[0]['content'].rsplit('\n',1);ctx=json.loads(raw)
    dump=lambda v:json.dumps(v,ensure_ascii=False,separators=(',',':'))
    return {'v3':token_count(prefix),'menu':token_count(dump(ctx['MENU_CONTEXT'])),
            'state':token_count(dump(ctx['MEAL_STATE'])),'schema':token_count(dump(ctx['ACTION_SCHEMA'])),
            'policy':token_count(dump(ctx['ACTION_POLICY'])),
            'current_user':token_count(messages[-1]['content'])}


def run(sequence,initial=None,stop_on_block=False):
    menu=MenuService();state=initial if initial is not None else create_meal();turns=[];rows=[]
    for number,(user,answer,actions) in enumerate(sequence,1):
        consent=grant(menu,state,actions)
        old=None
        try:old=old_plan(menu,state,user,history(turns),authorization=consent)
        except BudgetExceeded as exc:old={'metrics':exc.metrics.get('candidate',exc.metrics)}
        try:
            p=plan(menu,state,user,turns,authorization=consent)
        except BudgetExceeded as exc:
            rows.append({'turn':number,'status':'BLOCKED_NO_SEND','new':exc.metrics,'old':old['metrics'],'state_before':state,'state_after':state})
            break
        split=max(0,len(turns)-2)
        raw_old=history(turns[:split]);recent=history(turns[split:])
        a=token_count(json.dumps(raw_old,ensure_ascii=False,separators=(',',':')))
        b=token_count(json.dumps(archive(raw_old),ensure_ascii=False,separators=(',',':')))
        candidate_summary,_=memory(turns[:split],menu)
        c=token_count(json.dumps(candidate_summary,ensure_ascii=False,separators=(',',':'))) if candidate_summary else 0
        receipt=record(menu,state,user,answer,actions,consent)
        rows.append({'turn':number,'status':'ADMITTED_OFFLINE','user':user,'scripted_response':answer,'actions':actions,
                     'old':old['metrics'],'new':p['metrics'],'components':sizes(p['messages']),
                     'old_history_payload_tokens':a,'old_archive_payload_tokens':b,'minimal_summary_tokens':c,
                     'recent_content_tokens':sum(token_count(m['content']) for m in recent),
                     'summary':p['summary'],'retired':p['retired'],'recent_messages':p['messages'][-(2*p['recent_pairs']+1):-1],
                     'state_before':state,'state_after':receipt.after})
        state=receipt.after;turns.append(receipt)
    return rows


def mixed():
    sequence=[]
    for i in range(15):
        k=i%5
        if k==0:user,actions='Passe en grande salade.',[act('SET_SIZE',size='large')]
        elif k==1:user,actions='Ajoute du maïs.',[add('ingredient.corn')]
        elif k==2:user,actions='Enlève le maïs.',[remove('ingredient.corn')]
        elif k==3:user,actions='Écris un poème.',[]
        else:user,actions='Je souhaite revenir au repas. '+('Merci de garder mes choix. '*8),[]
        sequence.append((user,'Proposition scriptée, moteur validé.',actions))
    return sequence


if __name__=='__main__':
    print(json.dumps({'mode':'OFFLINE_SCRIPTED_NO_PROVIDER','groq_live':'NOT RUN',
                     'scenario_15':run(script()),'mixed_continued':run(mixed(),salad(MenuService()))},ensure_ascii=False,indent=2))
