"""Offline HTTP integration: no real provider credentials or requests."""
import json
import os
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.app.main import create_app
from backend.app.api.conversations import ConversationStore
from backend.app.schemas.api import ChatResponse
from backend.app.services.llm.providers import CompatibleProvider, MockProvider, ProviderError
from backend.app.services.menu import MenuService
from backend.app.services.meal_engine import create_meal


def act(kind, **fields):
    return dict(type=kind, **fields)


def drink():
    return [act('SET_CATEGORY', category='drink'), act('ADD_ITEM', item_id='drink.drink.orange')]


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.provider = MockProvider({'message': 'Je propose un jus.', 'actions': drink()})
        self.store = ConversationStore()
        self.client = TestClient(create_app(provider=self.provider, store=self.store), raise_server_exceptions=False)

    def post(self, message='Un jus', cid='client-a', **fields):
        return self.client.post('/chat', json=dict(conversation_id=cid, message=message, **fields))

    def test_health_no_provider_call_and_normal_post(self):
        self.assertEqual(self.client.get('/health').json(), {'status': 'ok', 'prompt_version': 'v3'})
        self.assertEqual(self.provider.calls, [])
        response = self.post()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ChatResponse.model_validate(data)
        self.assertTrue(data['accepted'])
        self.assertEqual(data['provider_mode'], 'mock')
        self.assertEqual(data['quote']['total'], 15)
        self.assertFalse(data['model_text_trusted'])
        self.assertFalse(data['limits']['external_order_submitted'])
        prompt = Path('backend/app/prompts/prompt_v3.txt').read_text()
        self.assertTrue(self.provider.calls[0][0]['content'].startswith(prompt + '\n'))

    def test_validation_empty_message_ids_types_extra_fields_and_json(self):
        bodies = [dict(conversation_id='a', message=v) for v in ['', '  \n\t', None, 123, 'a'*1001]]
        bodies += [dict(conversation_id=v, message='ok') for v in ['', '../x', 'a'*65, 'a\n', 3, None]]
        bodies += [dict(message='ok'), dict(conversation_id='a', message='ok', prompt_version='v1'),
                   dict(conversation_id='a', message='ok', authorized_actions=[act('CONFIRM_ORDER')]),
                   dict(conversation_id='a', message='ok', confirm_composition='true'),
                   dict(conversation_id='a', message='ok', confirm_composition=True)]
        for body in bodies:
            with self.subTest(body=body):
                r = self.client.post('/chat', json=body)
                self.assertEqual(r.status_code, 422)
                self.assertEqual(set(r.json()['error']), {'code', 'message'})
        r = self.client.post('/chat', content='{"message":"private-input",', headers={'Content-Type':'application/json'})
        self.assertEqual(r.status_code, 422)
        self.assertNotIn('private-input', r.text)
        self.assertEqual(self.provider.calls, [])

    def test_two_turn_salad_history_state_and_isolation_reset(self):
        self.provider.response = {'message': 'Grande salade poulet et tomate, à compléter.', 'actions': [
            act('SET_CATEGORY', category='salad'), act('SET_SIZE', size='large'),
            act('ADD_ITEM', item_id='salad.ingredient.grilled_chicken'), act('ADD_ITEM', item_id='salad.ingredient.tomato')]}
        first = self.post('Je veux une grande salade avec poulet et tomate.').json()
        self.provider.response = {'message': 'Je propose le maïs.', 'actions':[act('ADD_ITEM', item_id='salad.ingredient.corn')]}
        second = self.post('Ajoute aussi du maïs.').json()
        self.assertEqual(second['meal_state']['categories']['salad']['slots']['ingredient'],
                         ['salad.ingredient.grilled_chicken','salad.ingredient.tomato','salad.ingredient.corn'])
        self.assertEqual(second['quote']['total'], 55)
        self.assertEqual(second['revision'], 2)
        messages = self.provider.calls[1]
        self.assertEqual([m['role'] for m in messages], ['system','user','assistant','user'])
        self.assertEqual(messages[1]['content'], 'Je veux une grande salade avec poulet et tomate.')
        self.assertEqual(messages[2]['content'], first['assistant_message'])
        self.assertEqual(json.loads(messages[0]['content'].split('\n')[-1])['MEAL_STATE'], first['meal_state'])
        self.provider.response = {'message':'Un jus.', 'actions':drink()}
        other = self.post(cid='client-b').json()
        self.assertEqual(len(self.provider.calls[-1]), 2)
        self.assertEqual(other['meal_state']['active_category'], 'drink')
        self.assertEqual(self.client.delete('/chat/client-a').json(), {'conversation_id':'client-a','deleted':True})
        self.assertFalse(self.client.delete('/chat/client-a').json()['deleted'])
        self.provider.response = {'message':'Nouvelle conversation.', 'actions':[]}
        reset = self.post().json()
        self.assertEqual(reset['meal_state'], create_meal())
        self.assertEqual(len(self.provider.calls[-1]), 2)
        self.assertEqual(reset['revision'], 1)
        self.assertEqual(self.post(cid='client-b').json()['meal_state'], other['meal_state'])

    def test_explicit_removal_add_remove_add_and_exact_authorization(self):
        chicken = 'salad.ingredient.grilled_chicken'
        tomato = 'salad.ingredient.tomato'
        corn = 'salad.ingredient.corn'
        self.provider.response = {'message':'Grande salade.', 'actions':[
            act('SET_CATEGORY',category='salad'), act('SET_SIZE',size='large'),
            *[act('ADD_ITEM',item_id=i) for i in [chicken,tomato,corn]]]}
        first = self.post('Je veux une grande salade avec poulet, tomate et maïs.').json()
        self.provider.response = {'message':'Tomate retirée.', 'actions':[act('REMOVE_ITEM',item_id=tomato)]}
        denied = self.post('Enlève la tomate.')
        self.assertEqual(denied.status_code,422)
        self.assertEqual(denied.json()['meal_state'],first['meal_state'])
        count = len(self.provider.calls)
        for fields, status in [({'remove_item_id':tomato},422),
                               ({'remove_item_id':tomato,'expected_revision':1},409),
                               ({'remove_item_id':'salad.ingredient.cucumber','expected_revision':2},422),
                               ({'remove_item_id':tomato,'expected_revision':2,'confirm_composition':True},422)]:
            self.assertEqual(self.post('Enlève la tomate.',**fields).status_code,status)
        self.assertEqual(len(self.provider.calls),count)
        removed = self.post('Enlève la tomate.',remove_item_id=tomato,expected_revision=2)
        self.assertEqual(removed.status_code,200)
        self.assertEqual(removed.json()['actions'],[act('REMOVE_ITEM',item_id=tomato)])
        self.assertEqual(removed.json()['meal_state']['categories']['salad']['slots']['ingredient'],[chicken,corn])
        policy=json.loads(self.provider.calls[-1][0]['content'].split('\n')[-1])['ACTION_POLICY']
        self.assertEqual(policy['authorized_protected_actions'],[act('REMOVE_ITEM',item_id=tomato)])
        self.provider.response={'message':'Autre retrait', 'actions':[act('REMOVE_ITEM',item_id=chicken)]}
        wrong=self.post('Enlève le maïs.',remove_item_id=corn,expected_revision=3)
        self.assertEqual(wrong.status_code,422)
        self.assertEqual(wrong.json()['meal_state'],removed.json()['meal_state'])
        self.provider.response={'message':'Tomate ajoutée.', 'actions':[act('ADD_ITEM',item_id=tomato)]}
        added=self.post('Ajoute la tomate.',expected_revision=4).json()
        self.assertEqual(added['meal_state']['categories']['salad']['slots']['ingredient'],[chicken,corn,tomato])
        self.assertEqual(added['quote']['total'],55)

    def test_provider_transport_success_and_menu_price_not_model(self):
        calls = []
        def transport(url, payload, headers, timeout):
            calls.append((url,payload,timeout))
            return {'choices':[{'message':{'content':json.dumps({'message':'Prix zéro !','actions':drink()})}}]}
        provider = CompatibleProvider(api_key='test-only', model='test-model', base_url='https://example.invalid/v1', transport=transport)
        client = TestClient(create_app(provider=provider))
        data = client.post('/chat', json={'conversation_id':'test','message':'Jus à zéro'}).json()
        self.assertEqual(data['provider_mode'], 'real')  # Adapter path, mocked HTTPS transport, no live network.
        self.assertEqual(data['quote']['total'], MenuService().item('drink.drink.orange')['price'])
        self.assertEqual(data['display']['facts']['quote']['total'], 15)
        self.assertNotIn('zéro', data['display']['message'])
        self.assertEqual(calls[0][0], 'https://example.invalid/v1/chat/completions')
        self.assertEqual(calls[0][1]['model'], 'test-model')

    def test_real_adapter_deadline_returns_504_and_rolls_back(self):
        done = threading.Event()
        def blocked(*args):
            done.wait(1)
            return {}
        provider = CompatibleProvider(api_key='test', model='test', base_url='https://example.invalid',
                                      timeout=0.03, overall_timeout=0.04, max_retries=0, transport=blocked)
        try:
            start = time.monotonic()
            with TestClient(create_app(provider=provider)) as client:
                r = client.post('/chat', json={'conversation_id':'a','message':'Bonjour'})
            self.assertLess(time.monotonic()-start, 0.8)
            self.assertEqual(r.status_code, 504)
            self.assertEqual(r.json()['meal_state'], create_meal())
            self.assertIsNone(r.json()['assistant_message'])
        finally:
            done.set()

    def test_provider_unavailable_configuration_and_no_exception_leak(self):
        class Broken:
            def complete(self, messages):
                raise ProviderError('PROVIDER_UNAVAILABLE', {'secret':'do-not-leak'})
        client = TestClient(create_app(provider=Broken()))
        r = client.post('/chat', json={'conversation_id':'a','message':'ok'})
        self.assertEqual(r.status_code, 503)
        self.assertNotIn('do-not-leak', r.text)
        with patch.dict(os.environ, {'LLM_PROVIDER':'groq','GROQ_API_KEY':'','LLM_MODEL':'x'}, clear=True):
            client = TestClient(create_app())
            self.assertEqual(client.get('/health').status_code, 200)
            self.assertEqual(client.post('/chat',json={'conversation_id':'a','message':'ok'}).status_code,503)

    def test_malformed_model_unknown_action_price_and_atomic_rollback(self):
        original = self.post().json()['meal_state']
        invalids = [('{bad', 502), ('[]', 502),
                    ({'message':'secret-invalid','actions':[act('MAGIC')]},422),
                    ({'message':'free','actions':[act('ADD_ITEM',item_id='drink.drink.orange',price=0)]},422),
                    ({'message':'pizza','actions':[act('SET_CATEGORY',category='salad'),act('ADD_ITEM',item_id='pizza.fake')]},422),
                    ({'message':'clear','actions':[act('CLEAR_MEAL')]},422)]
        for response, status in invalids:
            self.provider.response = response
            r = self.post()
            self.assertEqual(r.status_code,status)
            self.assertFalse(r.json()['accepted'])
            self.assertEqual(r.json()['meal_state'], original)
            self.assertEqual(r.json()['quote']['total'],15)
            self.assertEqual(r.json()['actions'],[])
            self.assertIsNone(r.json()['assistant_message'])
        self.provider.response = {'message':'ok','actions':[]}
        self.post()
        self.assertNotIn('secret-invalid', json.dumps(self.provider.calls[-1]))

    def test_confirmation_requires_explicit_revision_and_preserves_final_rule(self):
        state = self.post().json()['meal_state']
        self.provider.response = {'message':'envoyée en cuisine', 'actions':[act('CONFIRM_ORDER')]}
        self.assertEqual(self.post('Confirme').status_code,422)
        before = len(self.provider.calls)
        self.assertEqual(self.post('Confirme',confirm_composition=True,expected_revision=1).status_code,409)
        self.assertEqual(len(self.provider.calls),before)
        r = self.post('Confirme',confirm_composition=True,expected_revision=2)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['meal_state'],state)
        self.assertIn('aucune commande envoyée',r.json()['display']['message'])
        self.assertFalse(r.json()['limits']['external_order_submitted'])
        for actions in [[act('CONFIRM_ORDER'),act('CONFIRM_ORDER')],
                        [act('CONFIRM_ORDER'),act('RECOMMEND_ITEM',item_id='drink.drink.orange')]]:
            self.provider.response = {'message':'bad','actions':actions}
            with self.store.lease('client-a') as entry: revision=entry.revision
            self.assertEqual(self.post(confirm_composition=True,expected_revision=revision).status_code,422)

    def test_confirmation_incomplete_rejected_and_final_state_validated(self):
        self.provider.response = {'message':'salade','actions':[act('SET_CATEGORY',category='salad'),act('SET_SIZE',size='small')]}
        self.post()
        self.provider.response = {'message':'confirm','actions':[act('CONFIRM_ORDER')]}
        r = self.post(confirm_composition=True,expected_revision=1)
        self.assertEqual(r.status_code,422)
        self.assertFalse(r.json()['quote']['orderable'])
        self.provider.response = {'message':'proposition', 'actions': [
            *[act('ADD_ITEM',item_id=i) for i in ['salad.base.lettuce','salad.ingredient.tomato','salad.ingredient.cucumber','salad.topping.croutons','salad.sauce.caesar']],
            act('CONFIRM_ORDER')]}
        r=self.post(confirm_composition=True,expected_revision=2)
        self.assertEqual(r.status_code,200)
        self.assertTrue(r.json()['quote']['orderable'])
        self.assertEqual(r.json()['quote']['total'],35)

    def test_partial_state_output_history_window_and_capacity(self):
        self.provider.response = {'message':'Choisissez la taille.', 'actions':[act('SET_CATEGORY',category='salad')]}
        r=self.post().json()
        self.assertEqual(r['quote']['missing'],[{'category':'salad','size_required':True}])
        self.assertIsNone(r['quote']['total'])
        self.provider.response={'message':'x'*1500,'actions':[]}
        for _ in range(22): self.assertEqual(self.post('q'*1000).status_code,200)
        self.assertLessEqual(len(self.provider.calls[-1])-2,40)
        self.assertLessEqual(sum(len(x['content']) for x in self.provider.calls[-1][1:-1]),16000)
        self.assertEqual(self.provider.calls[-1][1]['role'],'user')
        limited=TestClient(create_app(provider=MockProvider(),store=ConversationStore(capacity=1)))
        self.assertEqual(limited.post('/chat',json={'conversation_id':'a','message':'hi'}).status_code,200)
        self.assertEqual(limited.post('/chat',json={'conversation_id':'b','message':'hi'}).status_code,503)

    def test_concurrent_same_id_and_delete_busy_but_other_id_independent(self):
        entered, release = threading.Event(), threading.Event()
        class Blocking:
            def complete(self,messages):
                if messages[-1]['content']=='block':
                    entered.set();release.wait(2)
                return '{"message":"ok","actions":[]}'
        client=TestClient(create_app(provider=Blocking()))
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(client.post,'/chat',json={'conversation_id':'a','message':'block'})
            try:
                self.assertTrue(entered.wait(1))
                self.assertEqual(client.delete('/chat/a').status_code,409)
                self.assertEqual(client.post('/chat',json={'conversation_id':'a','message':'other'}).status_code,409)
                self.assertEqual(client.post('/chat',json={'conversation_id':'b','message':'other'}).status_code,200)
            finally: release.set()
            self.assertEqual(pending.result().status_code,200)
        self.assertEqual(client.delete('/chat/a').status_code,200)

    def test_internal_failure_no_commit_or_trace_and_pydantic_output(self):
        with patch('backend.app.main.quote',side_effect=RuntimeError('secret-internal')):
            r=self.post()
        self.assertEqual(r.status_code,500)
        self.assertNotIn('secret-internal',r.text)
        self.assertNotIn('Traceback',r.text)
        with self.store.lease('client-a') as entry:
            self.assertEqual(entry.state,create_meal());self.assertEqual(entry.history,[])
        data=self.post().json();data['actions'][0]['price']=0
        with self.assertRaises(ValidationError): ChatResponse.model_validate(data)

    def test_cors_openapi_and_explicit_env_loading(self):
        r=self.client.options('/chat',headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'POST'})
        self.assertEqual(r.headers['access-control-allow-origin'],'http://localhost:5173')
        self.assertNotIn('access-control-allow-origin',self.client.get('/health',headers={'Origin':'https://untrusted.invalid'}).headers)
        spec=self.client.get('/openapi.json').json()
        self.assertIn('ChatRequest',spec['components']['schemas'])
        self.assertIn('discriminator',spec['components']['schemas']['ChatResponse']['properties']['actions']['items'])
        with TemporaryDirectory() as directory, patch.dict(os.environ,{},clear=True):
            env=Path(directory)/'.env';env.write_text('LLM_PROVIDER=mock\nCORS_ORIGINS=http://localhost:9999\n')
            client=TestClient(create_app(env_file=env))
            self.assertEqual(client.post('/chat',json={'conversation_id':'a','message':'hello'}).json()['provider_mode'],'mock')
            self.assertEqual(client.get('/health',headers={'Origin':'http://localhost:9999'}).headers['access-control-allow-origin'],'http://localhost:9999')
