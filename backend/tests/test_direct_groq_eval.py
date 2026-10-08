"""Direct evaluation runner tests: fake HTTPS only; no live key required."""
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock
from tools import direct_groq_eval as runner
from backend.app.services.evaluation import scenarios
from backend.app.services.menu import MenuService
from backend.app.services.action_policy import authorize_actions, policy_context
from tools.eval_payload import build_eval_messages

DUMMY = 'dummy-direct-eval-key'


def envelope(content, finish='stop'):
    return json.dumps({'choices':[{'message':{'content':content},'finish_reason':finish}]}).encode()


class VirtualClock:
    def __init__(self):
        self.now = 0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def pacer(self):
        return runner.ConservativePacer(self.sleep, self.clock)


class DirectGroqTests(unittest.TestCase):
    def setUp(self):
        self.timer = VirtualClock()

    def call(self, messages, key, transport, sleep=None):
        return runner.direct_call(messages, key, transport, pacer=self.timer.pacer())

    def test_fixed_https_request_and_no_redirect_following(self):
        connection=MagicMock()
        connection.getresponse.return_value.status=302
        with patch.object(runner.http.client,'HTTPSConnection',return_value=connection) as factory:
            status,body=runner.post_https({'messages':[]},DUMMY)
        factory.assert_called_once_with('api.groq.com',timeout=30)
        args=connection.request.call_args
        self.assertEqual(args.args,('POST','/openai/v1/chat/completions'))
        self.assertEqual(args.kwargs['headers']['Authorization'],'Bearer '+DUMMY)
        self.assertEqual(status,302)
        self.assertEqual(body,b'')
        connection.request.assert_called_once()
        connection.close.assert_called_once()

    def test_exact_context_all_42_and_polluted_environment_ignored(self):
        menu=MenuService();cases=scenarios(menu);captured=[]
        def transport(payload,key):
            index=len(captured);captured.append(payload)
            self.assertEqual(self.timer.now,65 * (index + 1))
            self.assertEqual(key,DUMMY)
            return 200,envelope(json.dumps(cases[index%14]['mock_response']))
        env={'GROQ_API_KEY':DUMMY,'LLM_BASE_URL':'[broken](markdown)', 'LLM_MODEL':'wrong','LLM_PROVIDER':'wrong'}
        with patch.dict(os.environ,env),patch('backend.app.services.llm.providers.CompatibleProvider',side_effect=AssertionError('production provider forbidden')):
            report=runner.run_evaluation(transport=transport,sleep=self.timer.sleep,clock=self.timer.clock,output=None)
        self.assertEqual(len(captured),42)
        for index,payload in enumerate(captured):
            case=cases[index%14];version=('v1','v2','v3')[index//14]
            grant=authorize_actions(case['initial_state'],case['authorized_actions'],menu)
            expected=build_eval_messages(version,menu,case['initial_state'],case['input'],case['history'],
                policy=policy_context(case['initial_state'],grant,'composition'))
            self.assertEqual(payload,{'model':'openai/gpt-oss-120b','messages':expected,
                                     'temperature':0,'response_format':{'type':'json_object'},'max_completion_tokens':1024})
        self.assertTrue(all(r['contract_pass'] for r in report['rows']))
        self.assertTrue(report['execution_summary']['all_42_received_model_responses'])
        self.assertEqual(report['execution_summary']['http_attempts'],42)
        self.assertEqual(report['metadata']['execution_path'],'DIRECT_GROQ_EVAL')
        self.assertFalse(report['metadata']['production_provider_used'])
        self.assertNotIn(DUMMY,json.dumps(report))
        self.assertTrue(all(r['semantic_evaluation']['status']=='PENDING_HUMAN_REVIEW' for r in report['rows']))

    def test_malformed_envelopes_are_safe(self):
        for body in (b'',b'{',b'['*1000+b'0'+b']'*1000,b'{}',envelope(''),envelope(None)):
            raw,finish,attempts,error=self.call([],DUMMY,lambda *a:(200,body))
            self.assertIsNone(raw)
            self.assertEqual(error['code'],'PROVIDER_INVALID_RESPONSE')
            self.assertEqual(len(attempts),1)

    def test_bad_inner_json_and_unknown_item_do_not_abort_or_mutate(self):
        bad=['{','['*1000+'0'+']'*1000,json.dumps({'message':'x','actions':[{'type':'ADD_ITEM','item_id':'invented'}]})]
        calls=[]
        def transport(*args):
            index=len(calls);calls.append(1)
            return 200,envelope(bad[index] if index<len(bad) else '{"message":"x","actions":[]}')
        with patch.dict(os.environ,{'GROQ_API_KEY':DUMMY}),TemporaryDirectory() as temp:
            output=Path(temp)/'real-results.local.json'
            report=runner.run_evaluation(transport=transport,sleep=self.timer.sleep,clock=self.timer.clock,output=output)
            self.assertEqual(json.loads(output.read_text()),report)
        self.assertEqual(len(calls),42)
        self.assertEqual(report['execution_summary']['successful_calls_with_model_response'],42)
        for row in report['rows'][:3]:
            self.assertFalse(row['validation_result']['accepted'])
            self.assertEqual(row['resulting_meal_state'],row['initial_state'])

    def test_retry_counts_and_redaction(self):
        calls=[]
        def transient(*args):
            calls.append(1)
            return (429,b'dummy-private-error') if len(calls)==1 else (200,envelope('{"message":"ok","actions":[]}'))
        raw,finish,attempts,error=self.call([],DUMMY,transient,lambda _:None)
        self.assertEqual(len(attempts),2)
        self.assertEqual(attempts[0]['http_status'],429)
        self.assertIsNone(error)
        for failure in (TimeoutError(DUMMY),RuntimeError(DUMMY)):
            def broken(*args):raise failure
            result=self.call([],DUMMY,broken,lambda _:None)
            self.assertNotIn(DUMMY,json.dumps(result))
        raw,finish,attempts,error=self.call([],DUMMY,lambda *a:(200,envelope(DUMMY)))
        self.assertIsNone(raw)
        self.assertEqual(error['code'],'PROVIDER_SECRET_ECHO_BLOCKED')

    def test_pacing_includes_retries_and_next_combination(self):
        pacer = self.timer.pacer()
        starts = []
        statuses = iter([429, 200, 413, 413, 503, 200])
        def transport(*args):
            starts.append(self.timer.now)
            self.timer.now += 3  # request duration also separates attempts
            return next(statuses), envelope('{"message":"ok","actions":[]}')
        results = [runner.direct_call([], DUMMY, transport, pacer=pacer) for _ in range(3)]
        self.assertEqual(starts, [65,188,256,324,392,460])
        self.assertEqual([len(r[2]) for r in results], [2,2,2])
        self.assertIsNotNone(results[1][3])
        self.assertTrue(all(delay <= 30 for delay in self.timer.sleeps))
        self.assertLess(runner.INPUT_BUDGET + runner.COMPLETION_BUDGET, 8000)

    def test_missing_key_preserves_existing_results(self):
        with TemporaryDirectory() as temp,patch.dict(os.environ,{},clear=True):
            path=Path(temp)/'real-results.local.json';path.write_text('existing')
            with self.assertRaises(runner.DirectError):runner.run_evaluation(output=path)
            self.assertEqual(path.read_text(),'existing')

    def test_truncated_completion_is_not_applied(self):
        case=scenarios(MenuService())[0];menu=MenuService()
        grant=authorize_actions(case['initial_state'],case['authorized_actions'],menu)
        result=runner.evaluate_actions(case,json.dumps(case['mock_response']),None,'length',menu,grant)
        self.assertEqual(result['error']['code'],'PROVIDER_INCOMPLETE_COMPLETION')
        self.assertEqual(result['state'],case['initial_state'])
