import io,json,unittest
from urllib.error import HTTPError
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.services.llm.providers import CompatibleProvider

class ProviderRateLimitTests(unittest.TestCase):
 def test_daily_limit_is_429_with_retry_after_and_no_retry_or_secret(self):
  calls=[]
  def transport(*args):
   calls.append(1)
   body=json.dumps({'error':{'message':'tokens per day (TPD): Limit 200000, Used 199350, Requested 5925 secret-provider-detail'}}).encode()
   raise HTTPError('https://example.test',429,'limited',{'retry-after':'2279'},io.BytesIO(body))
  p=CompatibleProvider(api_key='test-only',model='test',base_url='https://example.test',transport=transport,max_retries=3)
  r=TestClient(create_app(provider=p)).post('/chat',json={'conversation_id':'quota','message':'Une salade'})
  self.assertEqual(r.status_code,429);self.assertEqual(len(calls),1)
  self.assertEqual(r.headers['retry-after'],'2279')
  data=r.json();self.assertEqual(data['provider_mode'],'real');self.assertFalse(data['accepted'])
  self.assertEqual(data['error']['code'],'PROVIDER_RATE_LIMITED')
  self.assertIn('quotidien',data['error']['message']);self.assertIn('2279',data['error']['message'])
  self.assertIsNone(data['assistant_message']);self.assertEqual(data['meal_state']['categories'],{})
  self.assertNotIn('secret-provider-detail',r.text);self.assertNotIn('test-only',r.text)
 def test_malformed_body_and_retry_after_remain_safe_rate_limit(self):
  def transport(*args):raise HTTPError('https://example.test',429,'limited',{'retry-after':'secret'},io.BytesIO(b'not-json secret'))
  p=CompatibleProvider(api_key='test',model='test',base_url='https://example.test',transport=transport)
  r=TestClient(create_app(provider=p)).post('/chat',json={'conversation_id':'quota','message':'Bonjour'})
  self.assertEqual(r.status_code,429);self.assertNotIn('retry-after',r.headers);self.assertNotIn('secret',r.text)
