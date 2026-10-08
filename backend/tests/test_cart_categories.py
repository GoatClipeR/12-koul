import unittest
from copy import deepcopy
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.api.conversations import ConversationStore
from backend.app.services.llm.providers import MockProvider
from backend.app.services.meal_engine import apply_response, create_meal
from backend.app.services.price_engine import quote
from backend.app.services.menu import MenuService
from backend.app.services.errors import DomainError


def action(kind, **kw): return {'type':kind,**kw}
def batch(category,ids): return [action('SET_CATEGORY',category=category),*[action('ADD_ITEM',item_id=i) for i in ids]]
SANDWICH=['sandwich.bread.baguette','sandwich.protein.grilled_chicken','sandwich.sauce.algerian']
PLAT=['plat.protein.grilled_chicken','plat.side.fries','plat.sauce.barbecue']
SALAD=[action('SET_CATEGORY',category='salad'),action('SET_SIZE',size='small'),*[action('ADD_ITEM',item_id=i) for i in ['salad.base.lettuce','salad.ingredient.tomato','salad.ingredient.corn','salad.topping.croutons','salad.sauce.caesar']]]

class CategoryCartTests(unittest.TestCase):
 def setUp(self):
  self.menu=MenuService();self.provider=MockProvider();self.store=ConversationStore()
  self.client=TestClient(create_app(provider=self.provider,store=self.store));self.revision=0
 def send(self, actions=None, cid='final', **kw):
  if actions is not None:self.provider.response={'message':'Proposition de test.', 'actions':actions}
  r=self.client.post('/chat',json={'conversation_id':cid,'message':'Test de composition','cart_mode':True,'expected_revision':self.revision,**kw})
  self.revision=r.json().get('revision',self.revision);return r
 def test_sandwich_partial_complete_limits_and_price(self):
  partial=apply_response(create_meal(),{'message':'Proposition.','actions':batch('sandwich',SANDWICH[:2])},self.menu)
  self.assertFalse(quote(partial,self.menu)['orderable'])
  r=self.send(batch('sandwich',SANDWICH)).json();self.assertEqual(r['quote']['total'],38);self.assertTrue(r['quote']['orderable'])
  for slot,limit in [('cheese',1),('vegetable',3),('extra',2)]:
   ids=[i['id'] for i in self.menu.snapshot()['items'] if i['category']=='sandwich' and i['slot']==slot]
   base=deepcopy(r['meal_state'])
   okay=apply_response(base,{'message':'Proposition.','actions':[action('ADD_ITEM',item_id=i) for i in ids[:limit]]},self.menu)
   expected=38+sum(self.menu.item(i)['price'] for i in ids[:limit]);self.assertEqual(quote(okay,self.menu)['total'],expected)
   with self.assertRaises(DomainError):apply_response(okay,{'message':'Proposition.','actions':[action('ADD_ITEM',item_id=ids[limit])]},self.menu)
 def test_cheddar_remove_authorized_and_not_authorized(self):
  self.send(batch('sandwich',SANDWICH+['sandwich.cheese.cheddar']))
  remove=[action('REMOVE_ITEM',item_id='sandwich.cheese.cheddar')]
  self.assertEqual(self.send(remove).status_code,422)
  r=self.send(remove,remove_item_id='sandwich.cheese.cheddar');self.assertEqual(r.status_code,200)
  self.assertEqual(r.json()['meal_state']['categories']['sandwich']['slots']['cheese'],[])
 def test_plat_required_slots_and_price(self):
  for ids in [PLAT[:2],PLAT[1:],PLAT[::2]]:
   state=apply_response(create_meal(),{'message':'Proposition.','actions':batch('plat',ids)},self.menu)
   self.assertFalse(quote(state,self.menu)['orderable'])
  r=self.send(batch('plat',PLAT)).json();self.assertTrue(r['quote']['orderable']);self.assertEqual(r['quote']['total'],55)
 def test_multiple_drinks_direct_cart_and_remove(self):
  r=self.send(batch('drink',['drink.drink.coca_cola','drink.drink.orange'])).json()
  self.assertEqual(r['meal_state'],create_meal());self.assertEqual(len(r['cart']['lines']),2);self.assertEqual(r['cart']['total'],25)
  r=self.send([action('REMOVE_ITEM',item_id='drink.drink.coca_cola')],remove_item_id='drink.drink.coca_cola').json()
  self.assertEqual(r['cart']['total'],15);self.assertEqual(len(r['cart']['lines']),1)
 def test_duplicate_drinks_have_distinct_lines_and_remove_by_id(self):
  r=self.send(batch('drink',['drink.drink.coca_cola','drink.drink.coca_cola'])).json()
  ids=[l['id'] for l in r['cart']['lines']];self.assertEqual(len(set(ids)),2)
  self.assertEqual(self.send([action('REMOVE_ITEM',item_id='drink.drink.coca_cola')],remove_item_id='drink.drink.coca_cola').status_code,422)
  r=self.send(cart_command='remove',cart_line_id=ids[0]).json();self.assertEqual(r['cart']['total'],10)
 def test_cart_atomic_rejection_no_model_price_and_isolation(self):
  r=self.send(batch('drink',['drink.drink.coca_cola','not.real']));self.assertEqual(r.status_code,422);self.assertEqual(r.json()['cart']['lines'],[])
  self.provider.response={'message':'Total 1 MAD','actions':batch('drink',['drink.drink.orange'])}
  self.assertEqual(self.send().json()['cart']['total'],15)
  r=self.client.post('/chat',json={'conversation_id':'other','message':'hello','cart_mode':True}).json()
  self.assertEqual(len(r['cart']['lines']),1)
  self.client.delete('/chat/other')
  with self.store.lease('final') as entry:self.assertEqual(len(entry.cart),1)
 def test_all_categories_cart_total_confirmation_and_reset(self):
  for category,actions in [('salad',SALAD),('sandwich',batch('sandwich',SANDWICH)),('plat',batch('plat',PLAT))]:
   self.assertEqual(self.send(actions).status_code,200)
   r=self.send(cart_command='add',cart_category=category);self.assertEqual(r.status_code,200)
  r=self.send(batch('drink',['drink.drink.coca_cola','drink.drink.orange'])).json()
  self.assertEqual(r['cart']['total'],153);self.assertEqual(len(r['cart']['lines']),5)
  r=self.send(cart_command='confirm').json();self.assertTrue(r['cart']['confirmed']);self.assertFalse(r['cart']['external_order_submitted'])
  r=self.send(cart_command='remove',cart_line_id=r['cart']['lines'][0]['id']).json();self.assertFalse(r['cart']['confirmed']);self.assertEqual(r['cart']['total'],118)
  self.client.delete('/chat/final')
  with self.store.lease('final') as e:self.assertEqual(e.cart,[]);self.assertEqual(e.state,create_meal())
 def test_incomplete_commit_stale_and_missing_grant_rejected(self):
  self.send(batch('sandwich',SANDWICH[:1]))
  self.assertEqual(self.send(cart_command='add',cart_category='sandwich').status_code,422)
  r=self.client.post('/chat',json={'conversation_id':'final','message':'Add','cart_mode':True,'cart_command':'add','cart_category':'sandwich','expected_revision':0})
  self.assertEqual(r.status_code,409)
  self.assertEqual(self.send(cart_command='confirm').status_code,422)
 def test_cart_bound_and_clear_authorization(self):
  self.assertEqual(self.send([action('CLEAR_MEAL')]).status_code,422)
  self.assertEqual(self.send(batch('drink',['drink.drink.coca_cola']*40)).status_code,200)
  self.assertEqual(self.send(batch('drink',['drink.drink.coca_cola'])).status_code,422)

 def test_final_confirm_after_drink_validates_cart_not_empty_transfer_draft(self):
  actions=batch('drink',['drink.drink.orange'])+[action('CONFIRM_ORDER')]
  r=self.send(actions,confirm_composition=True)
  self.assertEqual(r.status_code,200)
  self.assertTrue(r.json()['cart']['confirmed'])
  self.assertEqual(r.json()['cart']['total'],15)
  self.assertFalse(r.json()['cart']['external_order_submitted'])
