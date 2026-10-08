"""Offline boundary regressions; these tests do not establish model quality."""
import json
import unittest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.services.llm.providers import CompatibleProvider


class FirstTurnTests(unittest.TestCase):
    def test_raw_actions_survive_provider_api_and_partial_draft_validation(self):
        actions = [
            {'type': 'SET_CATEGORY', 'category': 'salad'},
            {'type': 'SET_SIZE', 'size': 'large'},
            {'type': 'ADD_ITEM', 'item_id': 'salad.ingredient.grilled_chicken'},
            {'type': 'ADD_ITEM', 'item_id': 'salad.ingredient.tomato'},
        ]
        for batch in ([], actions):
            with self.subTest(batch=batch):
                calls = []
                def transport(url, payload, headers, timeout):
                    calls.append(payload)
                    return {'choices': [{'message': {'content': json.dumps(
                        {'message': 'Proposition à compléter.', 'actions': batch})}}]}
                provider = CompatibleProvider(api_key='test-only', model='test',
                    base_url='https://example.test/v1', transport=transport)
                client = TestClient(create_app(provider=provider))
                message = 'Je veux une grande salade avec poulet et tomate.'
                response = client.post('/chat', json={'conversation_id': 'new',
                    'message': message, 'expected_revision': 0})
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data['actions'], batch)
                self.assertTrue(data['accepted'])
                self.assertFalse(data['quote']['orderable'])
                self.assertEqual(len(calls[0]['messages']), 2)
                self.assertEqual(calls[0]['messages'][-1], {'role': 'user', 'content': message})
                context = json.loads(calls[0]['messages'][0]['content'].rsplit('\n', 1)[1])
                self.assertEqual(context['MEAL_STATE'], {'active_category': None, 'categories': {}})
                self.assertEqual(context['ACTION_POLICY']['mode'], 'composition')
                if batch:
                    draft = data['meal_state']['categories']['salad']
                    self.assertEqual(draft['size'], 'large')
                    self.assertEqual(draft['slots']['ingredient'],
                        ['salad.ingredient.grilled_chicken', 'salad.ingredient.tomato'])
                    self.assertEqual(draft['slots']['base'], [])
                else:
                    self.assertEqual(data['meal_state']['categories'], {})
