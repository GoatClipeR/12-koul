import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.services.llm.providers import CompatibleProvider, MockProvider, ProviderError, provider_from_env

ENV={'GROQ_API_KEY':'test-only-not-a-real-key','LLM_MODEL':'openai/gpt-oss-120b','LLM_BASE_URL':'https://api.groq.com/openai/v1'}

class ProviderSelectionTests(unittest.TestCase):
 def test_key_without_selector_uses_existing_real_provider(self):
  with patch.dict(os.environ,ENV,clear=True):
   provider=provider_from_env()
   self.assertIsInstance(provider,CompatibleProvider)
   self.assertEqual(provider.model,ENV['LLM_MODEL'])
   with patch.object(CompatibleProvider,'complete',return_value=json.dumps({'message':'Réponse réelle simulée pour le test.','actions':[]})):
    data=TestClient(create_app()).post('/chat',json={'conversation_id':'fresh','message':'Bonjour'}).json()
   self.assertEqual(data['provider_mode'],'real')
   self.assertNotIn('Bienvenue chez',data['assistant_message'])
 def test_dotenv_load_and_real_status(self):
  with TemporaryDirectory() as directory, patch.dict(os.environ,{},clear=True):
   path=Path(directory)/'.env';path.write_text('\n'.join(k+'='+v for k,v in ENV.items()))
   app=create_app(env_file=path)
   self.assertTrue(os.getenv('GROQ_API_KEY'))
   with patch.object(CompatibleProvider,'complete',return_value='{"message":"Proposition.","actions":[]}'):
    data=TestClient(app).post('/chat',json={'conversation_id':'fresh','message':'Bonjour'}).json()
   self.assertEqual(data['provider_mode'],'real')
 def test_real_failure_never_falls_back_to_mock(self):
  with patch.dict(os.environ,ENV,clear=True),patch.object(CompatibleProvider,'complete',side_effect=ProviderError('PROVIDER_UNAVAILABLE')),patch.object(MockProvider,'complete') as mock:
   r=TestClient(create_app()).post('/chat',json={'conversation_id':'fresh','message':'Bonjour'})
   self.assertEqual(r.status_code,503);self.assertEqual(r.json()['provider_mode'],'real')
   self.assertIsNone(r.json()['assistant_message']);self.assertEqual(r.json()['error']['code'],'PROVIDER_UNAVAILABLE');mock.assert_not_called()
 def test_explicit_mock_is_an_intentional_offline_mode(self):
  with patch.dict(os.environ,{**ENV,'LLM_PROVIDER':'mock'},clear=True):
   self.assertIsInstance(provider_from_env(),MockProvider)
