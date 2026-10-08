import io
import json
import os
import unittest
from unittest.mock import MagicMock, patch
from tools import diagnose_groq as diagnostic
from tools import direct_groq_eval as runner

KEY='dummy-diagnostic-key'


class GroqDiagnosticTests(unittest.TestCase):
    def test_minimal_exactly_one_request_no_production_provider(self):
        response=MagicMock(status=200,reason='OK')
        data=json.dumps({'choices':[{'message':{'content':'OK'},'finish_reason':'stop'}]}).encode()
        response.read1.side_effect=io.BytesIO(data).read
        connection=MagicMock();connection.getresponse.return_value=response
        with patch.dict(os.environ,{'GROQ_API_KEY':KEY,'LLM_BASE_URL':'invalid markdown'}),patch.object(runner.http.client,'HTTPSConnection',return_value=connection):
            result=diagnostic.diagnose()
        self.assertEqual(result['request_count'],1)
        self.assertEqual(result['http_status'],200)
        connection.request.assert_called_once()
        request=connection.request.call_args
        self.assertEqual(json.loads(request.kwargs['body']),{'model':'openai/gpt-oss-120b','messages':[{'role':'user','content':'OK'}],'max_tokens':100})
        self.assertNotIn(KEY,json.dumps(result))
        self.assertNotIn('Authorization',json.dumps(result))

    def test_413_error_body_preserved_safely_without_retry(self):
        response=MagicMock(status=413,reason='Request too large')
        body=json.dumps({'error':{'message':'Limit 8000 Requested 12345 '+KEY},'Authorization':'Bearer '+KEY}).encode()
        response.read1.side_effect=io.BytesIO(body).read
        connection=MagicMock();connection.getresponse.return_value=response
        with patch.dict(os.environ,{'GROQ_API_KEY':KEY}),patch.object(runner.http.client,'HTTPSConnection',return_value=connection):
            result=diagnostic.diagnose()
        self.assertEqual(result['http_status'],413)
        self.assertIn('Limit 8000 Requested 12345',result['response_body'])
        self.assertNotIn(KEY,json.dumps(result))
        self.assertNotIn('Authorization',result['response_body'])
        connection.request.assert_called_once()

    def test_exception_diagnostics_redacted(self):
        connection=MagicMock();connection.request.side_effect=OSError('failure '+KEY)
        with patch.dict(os.environ,{'GROQ_API_KEY':KEY}),patch.object(runner.http.client,'HTTPSConnection',return_value=connection):
            result=diagnostic.diagnose()
        self.assertEqual(result['exception_type'],'OSError')
        self.assertIn('failure',result['exception_message'])
        self.assertNotIn(KEY,json.dumps(result))

    def test_missing_key_never_calls_http(self):
        with patch.dict(os.environ,{},clear=True),patch.object(runner,'post_https') as post:
            result=diagnostic.diagnose()
        self.assertFalse(result['api_key_present'])
        self.assertEqual(result['request_count'],0)
        post.assert_not_called()

    def test_full_payload_preserves_existing_generation_settings(self):
        payload=diagnostic.diagnostic_payload(True,'v3','normal_order')
        self.assertEqual(payload['response_format'],{'type':'json_object'})
        self.assertEqual(payload['messages'][0]['role'],'system')
        self.assertNotIn('max_tokens',payload)
        self.assertGreater(len(json.dumps(payload)),30000)
