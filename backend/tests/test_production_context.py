"""Lossless application encoding; no credentials or live calls."""
import json
import unittest
from copy import deepcopy
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.services.llm.providers import MockProvider
from backend.app.services.llm.prompts import build_messages, PROMPT_DIR
from backend.app.services.llm.production_context import compact_messages, compact_context
from backend.app.services.menu import MenuService
from backend.app.services.meal_engine import create_meal
from backend.app.services.action_policy import policy_context
from tools.eval_payload import payload_measure


class ProductionContextTests(unittest.TestCase):
    def original(self):
        state = create_meal()
        return build_messages('v3', MenuService(), state, 'Ajoute du maïs.',
                              [{'role':'user','content':'Une grande salade'},
                               {'role':'assistant','content':'Choisissez vos ingrédients.'}],
                              policy=policy_context(state, None, 'composition'))

    def test_lossless_menu_schema_prompt_history_policy_and_no_mutation(self):
        original = self.original()
        before = deepcopy(original)
        compact = compact_messages(original)
        self.assertEqual(original, before)
        self.assertEqual(compact[1:], original[1:])
        prefix, raw = compact[0]['content'].rsplit('\n', 1)
        self.assertEqual(prefix, (PROMPT_DIR/'prompt_v3.txt').read_text())
        decoded = json.loads(raw)
        table = decoded['MENU_CONTEXT']['items']
        decoded['MENU_CONTEXT']['items'] = [dict(zip(table['columns'],row)) for row in table['rows']]
        for item in decoded['MENU_CONTEXT']['items']:
            for field, keys in table['nested_columns'].items():
                item[field] = dict(zip(keys,item[field]))
        schema = decoded['ACTION_SCHEMA']
        definitions = schema.pop('$defs')
        for variant in schema['properties']['actions']['items']['oneOf']:
            for field, value in list(variant['properties'].items()):
                if '$ref' in value:
                    variant['properties'][field] = definitions[value['$ref'].split('/')[-1]]
        self.assertEqual(decoded, json.loads(original[0]['content'].rsplit('\n',1)[1]))

    def test_nonprefix_optional_fields_preserve_original_objects(self):
        context = json.loads(self.original()[0]['content'].rsplit('\n',1)[1])
        del context['MENU_CONTEXT']['items'][1]['tags']
        compact = compact_context(context)
        self.assertEqual(compact['MENU_CONTEXT'], context['MENU_CONTEXT'])

    def test_fastapi_short_add_remove_add_reset_and_budget(self):
        provider = MockProvider()
        client = TestClient(create_app(provider=provider))
        tomato = 'salad.ingredient.tomato'
        turns = [
            ('Je veux une grande salade avec poulet et tomate.', [
                {'type':'SET_CATEGORY','category':'salad'}, {'type':'SET_SIZE','size':'large'},
                {'type':'ADD_ITEM','item_id':'salad.ingredient.grilled_chicken'},
                {'type':'ADD_ITEM','item_id':tomato}], {}),
            ('Enlève la tomate.', [{'type':'REMOVE_ITEM','item_id':tomato}], {'remove_item_id':tomato}),
            ('Ajoute la tomate.', [{'type':'ADD_ITEM','item_id':tomato}], {}),
        ]
        for revision,(message,actions,extra) in enumerate(turns):
            provider.response = {'message':'Proposition à valider par le moteur.', 'actions':actions}
            response = client.post('/chat',json={'conversation_id':'compact','message':message,
                                                'expected_revision':revision,**extra})
            self.assertEqual(response.status_code,200)
            ids=response.json()['meal_state']['categories']['salad']['slots']['ingredient']
            self.assertEqual(tomato in ids, revision != 1)
            self.assertEqual(response.json()['quote']['total'],55)
            self.assertLessEqual(payload_measure(provider.calls[-1])['budgeted_input_tokens'],6500)
        self.assertEqual(client.delete('/chat/compact').status_code,200)
        provider.response={'message':'Bienvenue.', 'actions':[]}
        response=client.post('/chat',json={'conversation_id':'compact','message':'Bonjour'})
        self.assertEqual(response.json()['meal_state'],create_meal())
        self.assertEqual(len(provider.calls[-1]),2)
