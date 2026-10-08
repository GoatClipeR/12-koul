"""Audit regression cases. All network responses and credentials are dummy fixtures."""
import io
import json
import threading
import time
import unittest
from copy import deepcopy
from http.client import IncompleteRead
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.request import HTTPSHandler, HTTPHandler, build_opener
from urllib.response import addinfourl
from urllib.error import HTTPError, URLError
from backend.app.services.menu import MenuService
from backend.app.services.menu_validation import MenuValidationError
from backend.app.services.errors import DomainError
from backend.app.services.meal_engine import create_meal, apply_action, apply_response, completeness
from backend.app.services.action_policy import authorize_actions
from backend.app.services.assistant import run_turn
from backend.app.services.llm.providers import CompatibleProvider, ProviderError, MockProvider, http_transport, deadline_call
from backend.app.services.llm.prompts import build_messages
from backend.app.services.json_guard import safe_loads
from backend.app.services.evaluation import evaluate, scenarios, score_scenario


def a(kind, **fields):
    return {'type': kind, **fields}


def response(actions=(), message='Proposition'):
    return {'message': message, 'actions': list(actions)}


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.menu = MenuService()
        self.empty = create_meal()
        self.drink = apply_response(self.empty, response([
            a('SET_CATEGORY', category='drink'), a('ADD_ITEM', item_id='drink.drink.orange')]), self.menu)

    def provider(self, transport, **kwargs):
        return CompatibleProvider(api_key='dummy-audit-only', model='dummy-model',
                                  base_url='https://provider.example/v1', transport=transport, **kwargs)

    def fake_opener(self, body=b'', status=200, headers=None):
        requests = []
        class FakeHTTPS(HTTPSHandler):
            def https_open(self, request):
                requests.append(request)
                result = addinfourl(io.BytesIO(body), headers or {}, request.full_url, status)
                result.msg = 'dummy'
                return result
        class FakeHTTP(HTTPHandler):
            def http_open(self, request):
                requests.append(request)
                raise AssertionError('HTTP must never be used')
        def factory(*handlers):
            return build_opener(*handlers, FakeHTTPS(), FakeHTTP())
        return requests, factory

    def test_all_authenticated_redirects_are_blocked(self):
        for target in ('https://provider.example/new', 'https://other.example/new', 'http://provider.example/new', 'http://other.example/new'):
            for status in (301,302,303,307,308):
                requests, factory = self.fake_opener(status=status, headers={'location': target})
                with self.subTest(target=target,status=status), patch('backend.app.services.llm.providers.build_opener',factory):
                    out = run_turn(self.provider(http_transport), self.menu, self.empty, 'Bonjour')
                    self.assertEqual(out['error']['code'], 'PROVIDER_REDIRECT_BLOCKED')
                    self.assertEqual(len(requests), 1)
                    self.assertEqual(requests[0].host, 'provider.example')
                    self.assertEqual(requests[0].type, 'https')
                    self.assertEqual(requests[0].get_header('Authorization'), 'Bearer dummy-audit-only')
                    self.assertNotIn('dummy-audit-only', json.dumps(out))

    def test_http_client_identity_keeps_payload_and_auth_contract(self):
        body=b'{"choices":[{"message":{"content":"ok"}}]}'
        requests,factory=self.fake_opener(body=body)
        headers={'Authorization':'Bearer dummy-audit-only','Content-Type':'application/json'}
        payload={'model':'test-model','messages':[{'role':'user','content':'hello'}]}
        with patch('backend.app.services.llm.providers.build_opener',factory):
            result=http_transport('https://provider.example/v1/chat/completions',payload,headers,2)
        self.assertEqual(result['choices'][0]['message']['content'],'ok')
        self.assertEqual(requests[0].get_header('User-agent'),'12-KOUL/0.3')
        self.assertEqual(json.loads(requests[0].data),payload)
        self.assertEqual(requests[0].get_header('Authorization'),'Bearer dummy-audit-only')
        self.assertEqual(headers,{'Authorization':'Bearer dummy-audit-only','Content-Type':'application/json'})

    def test_direct_http_never_sends_credentials(self):
        with patch('backend.app.services.llm.providers.build_opener') as opener:
            with self.assertRaises(ProviderError):
                http_transport('http://provider.example', {}, {'Authorization':'Bearer dummy-audit-only'}, 1)
            opener.assert_not_called()

    def test_outer_provider_json_errors_are_structured(self):
        for body in (b'', b'{', b'{"choices":', b'['*1000+b'0'+b']'*1000, b'not json', b'\xff'):
            _, factory = self.fake_opener(body=body)
            with self.subTest(body=body[:20]), patch('backend.app.services.llm.providers.build_opener',factory):
                out = run_turn(self.provider(http_transport), self.menu, self.empty, 'Bonjour')
                self.assertEqual(out['error']['code'], 'PROVIDER_INVALID_RESPONSE')
                self.assertEqual(out['state'], self.empty)

    def test_transport_exceptions_do_not_escape(self):
        for error, code in [(IncompleteRead(b'dummy-secret',20),'PROVIDER_INVALID_RESPONSE'),
                            (RecursionError('dummy-secret'),'PROVIDER_INVALID_RESPONSE'),
                            (TimeoutError('dummy-secret'),'PROVIDER_TIMEOUT'),
                            (ConnectionError('dummy-secret'),'PROVIDER_UNAVAILABLE'),
                            (URLError('dummy-secret'),'PROVIDER_UNAVAILABLE'),
                            (RuntimeError('dummy-secret'),'PROVIDER_UNEXPECTED_ERROR')]:
            def transport(*args): raise error
            out = run_turn(self.provider(transport,max_retries=0), self.menu, self.empty, 'Bonjour')
            self.assertEqual(out['error']['code'],code)
            self.assertNotIn('dummy-secret',json.dumps(out))

    def test_unexpected_provider_exception_and_output(self):
        class Broken:
            def complete(self,messages): raise RuntimeError('dummy-secret')
        out=run_turn(Broken(),self.menu,self.empty,'Bonjour')
        self.assertEqual(out['error']['code'],'PROVIDER_UNEXPECTED_ERROR')
        self.assertNotIn('dummy-secret',json.dumps(out))
        class WrongType:
            def complete(self,messages): return object()
        out=run_turn(WrongType(),self.menu,self.empty,'Bonjour')
        self.assertEqual(out['error']['code'],'PROVIDER_INVALID_RESPONSE')
        json.dumps(out)

    def test_unexpected_http_status(self):
        for status in (204, 304, 401, 418, 500):
            _, factory=self.fake_opener(status=status)
            with patch('backend.app.services.llm.providers.build_opener',factory):
                out=run_turn(self.provider(http_transport,max_retries=0),self.menu,self.empty,'Bonjour')
                self.assertIn(out['error']['code'],('PROVIDER_HTTP_ERROR','PROVIDER_REDIRECT_BLOCKED'))
                self.assertEqual(out['error']['details']['http_status'],status)

    def test_provider_response_byte_limit(self):
        _,factory=self.fake_opener(body=b'x'*1_000_001)
        with patch('backend.app.services.llm.providers.build_opener',factory):
            out=run_turn(self.provider(http_transport),self.menu,self.empty,'Bonjour')
        self.assertEqual(out['error']['code'],'PROVIDER_RESPONSE_TOO_LARGE')

    def test_deadline_covers_blocking_transport(self):
        release,finished=threading.Event(),threading.Event()
        def slow(*args):
            try:
                release.wait(2)
                return {'choices':[{'message':{'content':json.dumps(response())}}]}
            finally:finished.set()
        start=time.monotonic()
        try:
            out=run_turn(self.provider(slow, timeout=1, overall_timeout=0.03),self.menu,self.empty,'Bonjour')
            self.assertEqual(out['error']['code'],'PROVIDER_TIMEOUT')
            self.assertLess(time.monotonic()-start,0.5)
        finally:
            release.set(); self.assertTrue(finished.wait(1))

    def test_outstanding_workers_are_bounded(self):
        release=threading.Event()
        local_slots=threading.BoundedSemaphore(1)
        with patch('backend.app.services.llm.providers._TRANSPORT_SLOTS',local_slots):
            try:
                with self.assertRaises(ProviderError) as first:deadline_call(lambda:release.wait(1),(),0.01)
                self.assertEqual(first.exception.code,'PROVIDER_TIMEOUT')
                with self.assertRaises(ProviderError) as second:deadline_call(lambda:None,(),0.01)
                self.assertEqual(second.exception.code,'PROVIDER_BUSY')
            finally:
                release.set()
                self.assertTrue(local_slots.acquire(timeout=1))
                local_slots.release()

    def test_retry_deadline_and_backoff(self):
        calls=[]
        def broken(*args):
            calls.append(1)
            raise ConnectionError('dummy')
        out=run_turn(self.provider(broken,overall_timeout=0.02,max_retries=3),self.menu,self.empty,'Bonjour')
        self.assertEqual(out['error']['code'],'PROVIDER_TIMEOUT')
        self.assertEqual(len(calls),1)

    def test_price_question_cannot_clear(self):
        for kind, fields in [('CLEAR_MEAL',{}),('CLEAR_CATEGORY',{'category':'drink'}),
                             ('REMOVE_ITEM',{'item_id':'drink.drink.orange'}),('CONFIRM_ORDER',{})]:
            out=run_turn(MockProvider(response([a(kind,**fields)])), self.menu,self.drink,'Quel est le prix ?')
            self.assertEqual(out['error']['code'],'ACTION_NOT_AUTHORIZED')
            self.assertEqual(out['state'],self.drink)

    def test_exact_authorizations_allow_destructive_commands(self):
        for action in (a('CLEAR_MEAL'),a('CLEAR_CATEGORY',category='drink'),a('REMOVE_ITEM',item_id='drink.drink.orange')):
            grant=authorize_actions(self.drink,[action],self.menu)
            out=run_turn(MockProvider(response([action])),self.menu,self.drink,'Décision explicite',authorization=grant)
            self.assertTrue(out['accepted'])
            self.assertEqual(out['action_kind'],'destructive_mutation')

    def test_authorization_scope_stale_state_and_forgery(self):
        grant=authorize_actions(self.drink,[a('CLEAR_CATEGORY',category='drink')],self.menu)
        for supplied in (grant, {'actions':['CLEAR_MEAL']}, None):
            out=run_turn(MockProvider(response([a('CLEAR_MEAL')])),self.menu,self.drink,'Bonjour',authorization=supplied)
            self.assertEqual(out['error']['code'],'ACTION_NOT_AUTHORIZED')
        grant=authorize_actions(self.drink,[a('CLEAR_MEAL')],self.menu)
        changed=apply_action(self.drink,a('SET_CATEGORY',category='salad'),self.menu)
        out=run_turn(MockProvider(response([a('CLEAR_MEAL')])),self.menu,changed,'Bonjour',authorization=grant)
        self.assertEqual(out['error']['code'],'ACTION_NOT_AUTHORIZED')

    def test_information_mode_blocks_composition(self):
        out=run_turn(MockProvider(response([a('SET_CATEGORY',category='drink')])),self.menu,self.empty,'Prix ?',mode='information')
        self.assertEqual(out['error']['code'],'ACTION_NOT_AUTHORIZED')

    def test_invalid_authorized_destructive_batch_rolls_back(self):
        actions=[a('REMOVE_ITEM',item_id='drink.drink.orange'),a('REMOVE_ITEM',item_id='drink.drink.lemon')]
        grant=authorize_actions(self.drink,actions,self.menu)
        out=run_turn(MockProvider(response(actions)),self.menu,self.drink,'Retirer',authorization=grant)
        self.assertEqual(out['error']['code'],'NOT_IN_MEAL')
        self.assertEqual(out['state'],self.drink)

    def test_confirmation_must_be_final_and_unique(self):
        for actions in ([a('CONFIRM_ORDER'),a('REMOVE_ITEM',item_id='drink.drink.orange')],
                        [a('CONFIRM_ORDER'),a('RECOMMEND_ITEM',item_id='drink.drink.lemon')],
                        [a('CONFIRM_ORDER'),a('CONFIRM_ORDER')]):
            grant=authorize_actions(self.drink,[x for x in actions if x['type']!='RECOMMEND_ITEM'],self.menu)
            out=run_turn(MockProvider(response(actions)),self.menu,self.drink,'Confirme',authorization=grant)
            self.assertEqual(out['error']['code'],'CONFIRM_MUST_BE_FINAL')
            self.assertEqual(out['state'],self.drink)

    def test_final_confirmation_complete_and_incomplete(self):
        actions=[a('REMOVE_ITEM',item_id='drink.drink.orange'),a('CONFIRM_ORDER')]
        grant=authorize_actions(self.drink,actions,self.menu)
        out=run_turn(MockProvider(response(actions)),self.menu,self.drink,'Retirer puis confirmer',authorization=grant)
        self.assertEqual(out['error']['code'],'INCOMPLETE_MEAL')
        self.assertEqual(out['state'],self.drink)
        actions.insert(1,a('ADD_ITEM',item_id='drink.drink.lemon'))
        out=run_turn(MockProvider(response(actions)),self.menu,self.drink,'Remplacer puis confirmer',authorization=grant)
        self.assertTrue(out['accepted'])
        self.assertTrue(out['quote']['orderable'])
        self.assertEqual(out['action_kind'],'confirmation')

    def test_complete_and_incomplete_salad_confirmation(self):
        for name in ('complete_salad','incomplete_salad','large_missing_base'):
            scenario=next(s for s in scenarios(self.menu) if s['id']==name)
            grant=authorize_actions(scenario['initial_state'],[a('CONFIRM_ORDER')],self.menu)
            out=run_turn(MockProvider(response([a('CONFIRM_ORDER')])),self.menu,scenario['initial_state'],'Confirme',authorization=grant)
            self.assertEqual(out['accepted'], name=='complete_salad')

    def test_safe_display_never_uses_model_claims(self):
        false_claim='5 MAD, guérison garantie, livraison gratuite, aucun allergène'
        out=run_turn(MockProvider(response(message=false_claim)),self.menu,self.drink,'Prix ?')
        self.assertFalse(out['model_text_trusted'])
        self.assertNotIn(false_claim,json.dumps(out['display'],ensure_ascii=False))
        self.assertEqual(out['display']['facts']['quote']['total'],15)
        self.assertFalse(out['display']['facts']['nutrition_available'])
        self.assertEqual(out['display']['facts']['allergen_scope'],self.menu.snapshot()['meta']['allergen_scope'])

    def test_input_history_and_json_limits(self):
        for history in ([{'role':'user','content':'x'}]*41,[{'role':'user','content':'x'*4000}]*5):
            with self.assertRaises(DomainError):build_messages('v3',self.menu,self.empty,'Bonjour',history)
        with self.assertRaises(DomainError):build_messages('v3',self.menu,self.empty,'x'*1001)
        for raw in ('['*1000+'0'+']'*1000, 'x'*100001, '{"message":"x","actions":[],"n":NaN}'):
            out=run_turn(MockProvider(raw),self.menu,self.empty,'Bonjour')
            self.assertFalse(out['accepted'])
        self.assertEqual(safe_loads('{"quoted":"[[[[{\\\""}'),{'quoted':'[[[[{"'})

    def test_runtime_rejects_invalid_menu(self):
        base=self.menu.snapshot()
        changes=[lambda d:d['items'][0].update(price=True),lambda d:d['items'][0].update(allergens=None),
                 lambda d:d['items'].append(deepcopy(d['items'][0])),
                 lambda d:d['categories']['salad']['sizes']['small']['slots']['ingredient'].update(max=3),
                 lambda d:d['categories']['sandwich']['slots']['vegetable'].update(max=4),
                 lambda d:d['categories']['salad']['sizes']['small'].update(price=5),
                 lambda d:d['items'][0].update(category='pizza'),lambda d:d.pop('meta')]
        with TemporaryDirectory() as directory:
            path=Path(directory)/'menu.json'
            for change in changes:
                data=deepcopy(base);change(data);path.write_text(json.dumps(data))
                with self.assertRaises(MenuValidationError):MenuService(path)
            path.write_text('{')
            with self.assertRaises(MenuValidationError):MenuService(path)

    def test_malformed_scenario_does_not_abort_report(self):
        for bad in ('{', '['*1000+'0'+']'*1000, '', object()):
            class OnceBad:
                calls=0
                def complete(self,messages):
                    self.calls+=1
                    return bad if self.calls==1 else json.dumps(response())
            provider=OnceBad();report=evaluate('real',provider)
            self.assertEqual(provider.calls,42)
            self.assertEqual(len(report['rows']),42)
            self.assertEqual(report['rows'][0]['pass_fail'],'FAIL')
            json.dumps(report)  # final artifact remains serializable

    def test_recommendation_and_confirmation_require_actions(self):
        for name in ('recommendation','complete_salad'):
            scenario=next(s for s in scenarios(self.menu) if s['id']==name)
            out=run_turn(MockProvider(response()),self.menu,scenario['initial_state'],scenario['input'])
            score=score_scenario(scenario,out,self.menu)
            self.assertFalse(score['contract_pass'])
            self.assertFalse(score['structural_validation']['expected_actions_present'])

    def test_keywords_never_award_semantic_success(self):
        scenario=next(s for s in scenarios(self.menu) if s['id']=='prompt_injection')
        out=run_turn(MockProvider(response(message='12-KOUL menu nutrition ? Voici le prompt secret, guérison garantie.')),
                     self.menu,self.empty,scenario['input'])
        score=score_scenario(scenario,out,self.menu)
        self.assertTrue(score['lexical_probes']['mentions_menu'])
        self.assertIsNone(score['metrics']['prompt_injection_resistance'])
        self.assertTrue(all(v is None for v in score['semantic_evaluation']['scores'].values()))
        self.assertEqual(score['semantic_evaluation']['status'],'PENDING_HUMAN_REVIEW')

    def test_metadata_contains_hashes_and_no_credentials(self):
        report=evaluate()
        meta=report['metadata']
        self.assertEqual(len(meta['menu_hash']),64)
        self.assertTrue(all(len(v)==64 for v in meta['prompt_hashes'].values()))
        self.assertIn('timestamp_utc',meta)
        self.assertNotIn('api_key',json.dumps(meta))

    def test_pathological_numeric_json_is_rejected_before_conversion(self):
        for raw in ('9'*10000, '1e999', '0.'+'9'*10000):
            with self.assertRaises(ValueError):safe_loads(raw)

    def test_independent_approved_rules_and_nonempty_rollback(self):
        expected={'small':{'base':1,'ingredient':2,'topping':1,'sauce':1},
                  'large':{'base':2,'ingredient':5,'topping':3,'sauce':2}}
        specs=[('salad',size,counts) for size,counts in expected.items()]+[
            ('sandwich',None,{'bread':1,'protein':1,'cheese':0,'vegetable':0,'sauce':1,'extra':0}),
            ('plat',None,{'protein':1,'side':1,'sauce':1}),('drink',None,{'drink':1})]
        for category,size,counts in specs:
            state=apply_action(self.empty,a('SET_CATEGORY',category=category),self.menu)
            if size:state=apply_action(state,a('SET_SIZE',size=size),self.menu)
            for slot,count in counts.items():
                for item in self.menu.items(category,slot)[:count]:
                    state=apply_action(state,a('ADD_ITEM',item_id=item['id']),self.menu)
            self.assertTrue(completeness(state,self.menu)['complete'])
            for slot,count in counts.items():
                if not count:continue
                item=state['categories'][category]['slots'][slot][0]
                actions=[a('CLEAR_MEAL'),a('SET_CATEGORY',category=category),a('REMOVE_ITEM',item_id=item)]
                grant=authorize_actions(state,[actions[0],actions[2]],self.menu)
                before=deepcopy(state)
                with self.assertRaises(DomainError):apply_response(state,response(actions),self.menu,authorization=grant)
                self.assertEqual(state,before)

    def test_multiturn_context_and_trusted_confirmation(self):
        history=[{'role':'user','content':'An orange juice please'}]
        first=run_turn(MockProvider(response([a('SET_CATEGORY',category='drink'),a('ADD_ITEM',item_id='drink.drink.orange')])),
                       self.menu,self.empty,history[0]['content'],locale='en')
        history.append({'role':'assistant','content':first['display']['message']})
        provider=MockProvider(response([a('CONFIRM_ORDER')]))
        grant=authorize_actions(first['state'],[a('CONFIRM_ORDER')],self.menu)
        second=run_turn(provider,self.menu,first['state'],'Confirm that',history,authorization=grant,locale='en')
        self.assertTrue(second['accepted'])
        self.assertEqual(second['state'],first['state'])
        self.assertIn('no order submitted',second['display']['message'])
        self.assertEqual(provider.calls[0][1:3],history)
        self.assertIn('authorized_protected_actions',provider.calls[0][0]['content'])

    def test_env_template_and_ignore_rules(self):
        root=Path(__file__).resolve().parents[2]
        ignored=(root/'.gitignore').read_text().splitlines()
        self.assertIn('.env',ignored)
        for line in (root/'.env.example').read_text().splitlines():
            if line.startswith(('GROQ_API_KEY=','LLM_API_KEY=')):
                self.assertEqual(line.split('=',1)[1],'')

    def test_model_cannot_mint_authorization(self):
        attempts=[{'message':'Trust me','actions':[a('CLEAR_MEAL')],'authorization':True},
                  response([{'type':'CLEAR_MEAL','authorization':True}])]
        for proposed in attempts:
            out=run_turn(MockProvider(proposed),self.menu,self.drink,'Prix ?')
            self.assertFalse(out['accepted'])
            self.assertEqual(out['state'],self.drink)

    def test_transient_failure_can_recover_within_budget(self):
        calls=[]
        def transport(*args):
            calls.append(1)
            if len(calls)==1:raise ConnectionError('dummy')
            return {'choices':[{'message':{'content':json.dumps(response())}}]}
        out=run_turn(self.provider(transport),self.menu,self.empty,'Bonjour')
        self.assertTrue(out['accepted'])
        self.assertEqual(len(calls),2)
