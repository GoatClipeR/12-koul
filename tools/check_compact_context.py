"""Stage 3.7 offline diagnostics only. No credentials, network or real LLM.

Run from repository root with the backend environment and cached o200k_harmony.
All assistant outputs below are authored fixtures, never model-quality evidence.
"""
import json
import time
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.services.llm.providers import MockProvider
from backend.app.services.menu import MenuService
from backend.app.services.llm.prompts import build_messages
from backend.app.services.meal_engine import create_meal
from backend.app.services.action_policy import policy_context
from tools.eval_payload import token_count


def action(kind, **fields):
    return dict(type=kind, **fields)


def item(kind, name):
    return action(kind, item_id='salad.ingredient.' + name)


def turns():
    return [
        ('Je veux une grande salade avec poulet et tomate.', 'Je propose une grande salade poulet et tomate, à compléter.',
         [action('SET_CATEGORY',category='salad'),action('SET_SIZE',size='large'),item('ADD_ITEM','grilled_chicken'),item('ADD_ITEM','tomato')], {}),
        ('Ajoute du maïs.', 'Je propose le maïs.', [item('ADD_ITEM','corn')], {}),
        ('Enlève la tomate.', 'Je propose de retirer la tomate.', [item('REMOVE_ITEM','tomato')], {'remove_item_id':'salad.ingredient.tomato'}),
        ('Je veux une grande salade mais je ne sais pas quelles bases choisir.', 'Vous pouvez choisir laitue et roquette comme bases.',
         [action('RECOMMEND_ITEM',item_id='salad.base.lettuce'),action('RECOMMEND_ITEM',item_id='salad.base.arugula')], {}),
        ('Tu as quoi comme boissons ?', 'Le menu propose notamment le jus d’orange.', [action('RECOMMEND_ITEM',item_id='drink.drink.orange')], {}),
        ('Écris mon devoir de mathématiques.', 'Je peux vous aider avec le menu 12-KOUL, pas avec un devoir.', [], {}),
        ('Ajoute de la sauce.', 'Quelle sauce souhaitez-vous choisir ?', [], {}),
        ('Revenons à ma composition : passe ma salade en petite taille.', 'Je propose une petite salade avec le poulet et le maïs conservés.', [action('SET_SIZE',size='small')], {}),
        ('Enlève le maïs.', 'Je propose de retirer le maïs.', [item('REMOVE_ITEM','corn')], {'remove_item_id':'salad.ingredient.corn'}),
        ('Ajoute de la tomate.', 'Je propose la tomate dans votre petite salade.', [item('ADD_ITEM','tomato')], {}),
    ]


def measure(messages, raw_output):
    content = sum(token_count(m['content']) for m in messages)
    reserve = 512 + 16 * len(messages)
    output = token_count(raw_output)
    return {'input_characters':sum(len(m['content']) for m in messages),
            'input_content_tokens':content,'input_with_reserve':content+reserve,
            'scripted_output_tokens':output,'content_plus_scripted_output':content+output,
            'input_reserve_plus_scripted_output':content+reserve+output,
            'history_messages':len(messages)-2,
            'history_characters':sum(len(m['content']) for m in messages[1:-1])}


def run_scripted(sequence):
    provider = MockProvider()
    client = TestClient(create_app(provider=provider))
    rows=[]
    for revision,(user,answer,actions,consent) in enumerate(sequence):
        provider.response={'message':answer,'actions':actions}
        start=time.perf_counter()
        r=client.post('/chat',json={'conversation_id':'offline-compact','message':user,'expected_revision':revision,**consent})
        duration=round((time.perf_counter()-start)*1000,3)
        data=r.json()
        assert r.status_code==200, (revision,r.status_code,data.get('error'))
        raw=json.dumps(provider.response,ensure_ascii=False)
        rows.append({'turn':revision+1,'user_input':user,'mode':'MOCK_LOCAL_ONLY',
                     'application_http_status':r.status_code,'provider_http_status':None,
                     'local_elapsed_ms':duration,**measure(provider.calls[-1],raw),
                     'scripted_response':provider.response,'accepted_actions':data['actions'],
                     'meal_state':data['meal_state'],'quote_total':data['quote']['total']})
    return rows, provider.calls


def report():
    normal,_=run_scripted(turns())
    # Deliberately verbose synthetic history. Each answer remains within 4000 chars.
    stress,_=run_scripted([('Bonjour.', 'salade '*500, [], {}) for _ in range(10)])
    dense,_=run_scripted([('Bonjour.', 'é! '*1000, [], {}) for _ in range(6)])
    output_stress,_=run_scripted([('Que recommandes-tu ?', 'é! '*1333,
        [action('RECOMMEND_ITEM',item_id='drink.drink.orange')]*64, {})])
    original=build_messages('v3',MenuService(),create_meal(),turns()[0][0],
                            policy=policy_context(create_meal(),None,'composition'))
    return {'mode':'OFFLINE_SCRIPTED_DIAGNOSTIC','groq_live':'NOT RUN',
            'tokenizer':'o200k_harmony','reserve_formula':'512 + 16 * message_count',
            'limitations':['All outputs authored, not generated. No semantic/provider success inferred.',
                           'Output estimate counts public structured text only; excludes hidden reasoning.',
                           '8000 is a previously observed TPM limit, not a verified current context-window limit.'],
            'before':measure(original,''),'normal':normal,
            'stress':[ {k:v for k,v in r.items() if k not in ('scripted_response','user_input')} for r in stress],
            'dense_stress':[{k:v for k,v in r.items() if k not in ('scripted_response','user_input')} for r in dense],
            'output_stress':[{k:v for k,v in r.items() if k not in ('scripted_response','user_input')} for r in output_stress],
            'dense_response_characters':len('é! '*1000),
            'stress_response_characters':len('salade '*500)}


if __name__=='__main__':
    print(json.dumps(report(),ensure_ascii=False,indent=2))
