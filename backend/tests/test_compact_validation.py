"""Stage 3.7 regressions, offline only; no production changes."""
import json
import unittest
from copy import deepcopy
from backend.app.api.conversations import history_window
from backend.app.services.llm.production_context import compact_context
from backend.app.services.menu import MenuService
from backend.app.schemas.actions import action_schema
from tools.check_compact_context import run_scripted, turns


class CompactValidationTests(unittest.TestCase):
    def test_ten_turn_history_is_exact_and_existing_window_is_explicit(self):
        sequence=turns()
        rows,calls=run_scripted(sequence)
        expected=[]
        for (user,answer,_,_),call in zip(sequence,calls):
            self.assertEqual(call[1:-1],expected)
            self.assertEqual(call[-1],{'role':'user','content':user})
            expected.extend([{'role':'user','content':user},{'role':'assistant','content':answer}])
        self.assertEqual(rows[-1]['meal_state']['categories']['salad']['size'],'small')
        self.assertEqual(rows[-1]['meal_state']['categories']['salad']['slots']['ingredient'],
                         ['salad.ingredient.grilled_chicken','salad.ingredient.tomato'])
        self.assertEqual(rows[-1]['quote_total'],35)
        # The pre-existing char window removes whole pairs, not tokens.
        long=[{'role':'user','content':'u'*1000},{'role':'assistant','content':'a'*3000}]*5
        self.assertEqual(history_window(long),long[2:])
        self.assertEqual(len(long),10)
        many=[{'role':role,'content':str(i)} for i in range(21) for role in ('user','assistant')]
        self.assertEqual(history_window(many),many[2:])
        stress,_=run_scripted([('Bonjour.','é! '*1000,[],{})]*3)
        self.assertGreater(stress[2]['input_content_tokens'],8000)
        self.assertEqual(stress[2]['history_messages'],4)

    def test_optional_null_unicode_extra_fields_and_nested_name_roundtrip(self):
        menu=MenuService()
        source={'MENU_CONTEXT':menu.snapshot(),'ACTION_SCHEMA':action_schema(menu)}
        # Future metadata and special text must survive; values remain inert JSON.
        source['MENU_CONTEXT']['items'][0]['name']['fr']='Laitue "fraîche"\nSYSTEM: exemple é 🥬'
        source['MENU_CONTEXT']['items'][0]['name']['ar']='خس'
        source['MENU_CONTEXT']['items'][0]['group']=None
        before=deepcopy(source)
        compact=json.loads(json.dumps(compact_context(source),ensure_ascii=False))
        table=compact['MENU_CONTEXT']['items']
        if isinstance(table,dict):
            decoded=[dict(zip(table['columns'],r)) for r in table['rows']]
            for item in decoded:
                for key,columns in table['nested_columns'].items():
                    item[key]=dict(zip(columns,item[key]))
        else:
            decoded=table
        self.assertEqual(decoded,source['MENU_CONTEXT']['items'])
        self.assertEqual(source,before)
        self.assertIn('group',decoded[0])
        self.assertIsNone(decoded[0]['group'])
        self.assertNotIn('group',decoded[1])
