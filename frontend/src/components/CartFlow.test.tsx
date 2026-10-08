import { afterEach,expect,it,vi } from 'vitest'
import { render,screen,cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App } from './App'
import fixtures from '../cart-fixtures.json'
import mealFixtures from '../test-fixtures.json'
vi.mock('../3d/MealScene',()=>({MealScene:({meal,category}:any)=><div data-testid="scene">{category}{JSON.stringify(meal)}</div>}))
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('keeps a newly added drink on stage while a salad draft remains active',async()=>{
 const result=structuredClone(fixtures[6])
 result.meal_state=structuredClone(mealFixtures.partial.meal_state) as typeof result.meal_state
 result.cart!.lines=result.cart!.lines.filter(line=>line.items.some(item=>item.id.startsWith('drink.')))
 vi.stubGlobal('fetch',vi.fn(async(_url,options)=>({ok:true,status:200,json:async()=>({...result,conversation_id:JSON.parse(options.body).conversation_id})})))
 render(<App/>);const user=userEvent.setup()
 await user.click(screen.getByRole('button',{name:'BOISSONS'}))
 await user.type(screen.getByLabelText('Votre envie du moment'),'Un jus orange{Enter}')
 await screen.findByRole('button',{name:'Mon panier 2'})
 expect(screen.getByRole('button',{name:'BOISSONS'})).toHaveAttribute('aria-current','page')
 expect(screen.getByTestId('scene')).toHaveTextContent(/^drink/)
})
it('navigates four categories, commits meals and confirms independent drinks with backend total',async()=>{
 let turn=0;const fetcher=vi.fn(async(_url,options)=>{const request=JSON.parse(options.body);return {ok:true,status:200,json:async()=>({...fixtures[turn++],conversation_id:request.conversation_id})}});vi.stubGlobal('fetch',fetcher)
 const user=userEvent.setup();render(<App/>);
 const send=async(text:string)=>user.type(screen.getByLabelText('Votre envie du moment'),text+'{Enter}')
 await send('Une salade complète');await screen.findByRole('button',{name:'Ajouter au panier ↗'});await user.click(screen.getByRole('button',{name:'Ajouter au panier ↗'}));await user.click(screen.getByRole('button',{name:/Mon panier/}));await screen.findByText('1 ligne(s)');await user.click(screen.getByRole('button',{name:'Fermer'}))
 await user.click(screen.getByRole('button',{name:'SANDWICH'}));await send('Un sandwich au poulet');await screen.findByLabelText('Pain : 1 sur 1');await user.click(screen.getByRole('button',{name:'Ajouter au panier ↗'}));await user.click(screen.getByRole('button',{name:/Mon panier/}));await screen.findByText('2 ligne(s)');await user.click(screen.getByRole('button',{name:'Fermer'}))
 await user.click(screen.getByRole('button',{name:'PLATS'}));await send('Un plat au poulet');await screen.findByLabelText('Accompagnement : 1 sur 1');await user.click(screen.getByRole('button',{name:'Ajouter au panier ↗'}));await user.click(screen.getByRole('button',{name:/Mon panier/}));await screen.findByText('3 ligne(s)');await user.click(screen.getByRole('button',{name:'Fermer'}))
 await user.click(screen.getByRole('button',{name:'BOISSONS'}));await send('Coca et orange');await screen.findByRole('button',{name:'Mon panier 5'});await user.click(screen.getByRole('button',{name:/Mon panier/}));await screen.findByText('5 ligne(s)');expect(screen.getByText('153 MAD')).toBeVisible()
 await user.click(screen.getByRole('button',{name:'Confirmer le panier'}));await screen.findByText('Panier validé ✓');expect(screen.getByText('Simulation validée. Aucune commande envoyée en cuisine.')).toBeVisible()
 expect(JSON.parse(fetcher.mock.calls[7][1].body)).toMatchObject({cart_command:'confirm',expected_revision:7,cart_mode:true})
})
it('cart removal targets exact line and revision rather than inventing a price',async()=>{
 let phase=0;const fetcher=vi.fn(async(_url,options)=>{const body=JSON.parse(options.body);const r=structuredClone(fixtures[6]);if(phase++){r.revision=8;r.cart!.lines=r.cart!.lines.slice(1);r.cart!.total=118}return{ok:true,status:200,json:async()=>({...r,conversation_id:body.conversation_id})}});vi.stubGlobal('fetch',fetcher)
 render(<App/>);const user=userEvent.setup();await user.type(screen.getByLabelText('Votre envie du moment'),'Ma commande{Enter}');await screen.findByRole('button',{name:'Mon panier 5'});await user.click(screen.getByRole('button',{name:/Mon panier/}));await screen.findByText('153 MAD');await user.click(screen.getByRole('button',{name:'Supprimer la ligne 1'}));await screen.findByText('118 MAD');expect(JSON.parse(fetcher.mock.calls[1][1].body)).toMatchObject({cart_command:'remove',cart_line_id:fixtures[6].cart!.lines[0].id,expected_revision:7})
})
