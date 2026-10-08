import { vi,describe,it,expect,beforeEach } from 'vitest'
import { render,screen,waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App } from './App'
import { Composition } from '../meal/Composition'
import fixtures from '../test-fixtures.json'
import removalFixtures from '../removal-fixtures.json'
import { projectMeal } from '../salad/mealScene'
import { chatResponse,type ChatResult } from '../api/chatApi'
vi.mock('../3d/MealScene',()=>({MealScene:({meal}:{meal:unknown})=><div data-testid="scene">{JSON.stringify(meal)}</div>}))
let response:ChatResult
const fetchMock=vi.fn()
beforeEach(()=>{response=chatResponse.parse(fixtures.partial);fetchMock.mockReset();vi.stubGlobal('fetch',fetchMock)})
function reply(data=response){return {ok:true,status:200,json:async()=>data}}
function wire(){fetchMock.mockImplementation(async(_url:string,options:RequestInit)=>{const body=JSON.parse(options.body as string);return reply({...response,conversation_id:body.conversation_id})})}
describe('Restaurant integration',()=>{
 it('ADD → explicit REMOVE → ADD updates API consent, composition and actual scene projection',async()=>{
  let turn=0
  fetchMock.mockImplementation(async(_url:string,options:RequestInit)=>{
   const body=JSON.parse(options.body as string)
   return reply(chatResponse.parse({...removalFixtures[turn++],conversation_id:body.conversation_id}))
  })
  render(<App/>);const user=userEvent.setup()
  await user.type(screen.getByLabelText('Votre envie du moment'),'Je veux une grande salade avec poulet, tomate et maïs.{Enter}')
  await screen.findByLabelText('Ingrédients : 3 sur 5')
  await user.click(screen.getByRole('button',{name:'Retirer Tomate'}))
  await screen.findByLabelText('Ingrédients : 2 sur 5')
  expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({message:'Enlève Tomate.',remove_item_id:'salad.ingredient.tomato',expected_revision:1})
  expect(screen.queryByRole('button',{name:'Retirer Tomate'})).not.toBeInTheDocument()
  let projected=projectMeal(JSON.parse(screen.getByTestId('scene').textContent!))
  expect(projected.ingredients).toEqual(['chicken','corn'])
  await user.type(screen.getByLabelText('Votre envie du moment'),'Ajoute la tomate.{Enter}')
  await screen.findByLabelText('Ingrédients : 3 sur 5')
  projected=projectMeal(JSON.parse(screen.getByTestId('scene').textContent!))
  expect(projected.ingredients).toEqual(['chicken','corn','tomato'])
  expect(JSON.parse(fetchMock.mock.calls[2][1].body)).not.toHaveProperty('remove_item_id')
  expect(screen.getByText('55 MAD')).toBeVisible()
 })
 it('renders the empty experience without inventing a price or sending a request',()=>{render(<App/>);expect(screen.getByRole('heading',{name:'KOOL AI'})).toBeVisible();expect(screen.getByText('—')).toBeVisible();expect(screen.getByRole('button',{name:'Envoyer le message'})).toBeDisabled();expect(fetchMock).not.toHaveBeenCalled()})
 it('sends through POST, renders real response facts, slots and scene snapshot',async()=>{wire();render(<App/>);const user=userEvent.setup();await user.type(screen.getByLabelText('Votre envie du moment'),'Une salade{Enter}');await screen.findByText('Je propose la laitue et la tomate.');expect(fetchMock.mock.calls[0][0]).toBe('http://127.0.0.1:8000/chat');expect(screen.getByText('55 MAD')).toBeVisible();expect(screen.getByLabelText('Bases : 1 sur 2')).toBeVisible();expect(screen.getByLabelText('Ingrédients : 1 sur 5')).toBeVisible();expect(screen.getByTestId('scene')).toHaveTextContent('salad.ingredient.tomato');expect(screen.getByRole('button',{name:/Valider la composition/})).toBeDisabled()})
 it('shows loading and blocks duplicate send/reset',async()=>{let finish!:(v:unknown)=>void;fetchMock.mockImplementation(()=>new Promise(r=>finish=r));render(<App/>);await userEvent.click(screen.getByRole('button',{name:/Une grande salade/}));expect(screen.getByRole('status')).toHaveTextContent('Un instant');expect(screen.getByRole('button',{name:/Nouvelle conversation/})).toBeDisabled();const body=JSON.parse(fetchMock.mock.calls[0][1].body);finish(reply({...response,conversation_id:body.conversation_id}));await screen.findByText('Je propose la laitue et la tomate.')})
 it('keeps the last meal on malformed response and offers retry',async()=>{wire();render(<App/>);await userEvent.click(screen.getByRole('button',{name:/Une grande salade/}));await screen.findByText('55 MAD');fetchMock.mockResolvedValue(reply({} as typeof response));await userEvent.type(screen.getByLabelText('Votre envie du moment'),'Ajoute du maïs{Enter}');await screen.findByRole('alert');expect(screen.getByText('55 MAD')).toBeVisible();expect(screen.getByRole('button',{name:'Réessayer'})).toBeVisible()})
 it('shows a network error without fake assistant messages',async()=>{fetchMock.mockRejectedValue(new TypeError('offline'));render(<App/>);await userEvent.click(screen.getByRole('button',{name:/Une grande salade/}));await screen.findByRole('alert');expect(screen.getByText(/Impossible de joindre/)).toBeVisible();expect(screen.getByText('—')).toBeVisible()})
 it('DELETE resets only after success, renews ID and clears price/state',async()=>{wire();render(<App/>);await userEvent.click(screen.getByRole('button',{name:/Une grande salade/}));await screen.findByText('55 MAD');const firstId=JSON.parse(fetchMock.mock.calls[0][1].body).conversation_id;fetchMock.mockResolvedValue({ok:true,status:200,json:async()=>({conversation_id:firstId,deleted:true})});await userEvent.click(screen.getByRole('button',{name:/Nouvelle conversation/}));await screen.findByText('—');expect(fetchMock.mock.calls[1][0]).toContain('/chat/'+firstId);expect(fetchMock.mock.calls[1][1].method).toBe('DELETE');wire();await userEvent.click(screen.getByRole('button',{name:/Une grande salade/}));await screen.findByText('55 MAD');expect(JSON.parse(fetchMock.mock.calls[2][1].body).conversation_id).not.toBe(firstId)})
 it('keeps the conversation when DELETE fails',async()=>{wire();render(<App/>);await userEvent.click(screen.getByRole('button',{name:/Une grande salade/}));await screen.findByText('55 MAD');fetchMock.mockRejectedValue(new TypeError('offline'));await userEvent.click(screen.getByRole('button',{name:/Nouvelle conversation/}));await screen.findByRole('alert');expect(screen.getByText('55 MAD')).toBeVisible()})
 it('uses backend completeness for confirmation and sends explicit revision consent',async()=>{response=chatResponse.parse(fixtures.complete);wire();render(<App/>);await userEvent.click(screen.getByRole('button',{name:/Une grande salade/}));await screen.findByText('55 MAD');response={...response,revision:4};await userEvent.click(screen.getByRole('button',{name:/Valider la composition/}));await waitFor(()=>expect(fetchMock).toHaveBeenCalledTimes(2));expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({confirm_composition:true,expected_revision:3})})
 it('renders backend snapshot removal and size changes, with no local quota/price calculation',()=>{const small=chatResponse.parse(fixtures.complete);small.meal_state.categories.salad.size='small';small.meal_state.categories.salad.slots.ingredient=['salad.ingredient.tomato'];small.quote.missing=[{category:'salad',slot:'ingredient',count:1}];small.quote.total=35;small.quote.orderable=false;render(<Composition result={chatResponse.parse(small)} busy={false} onConfirm={()=>{}}/>);expect(screen.getByText('Petite salade')).toBeVisible();expect(screen.getByText('35 MAD')).toBeVisible();expect(screen.getByLabelText('Ingrédients : 1 sur 2')).toBeVisible()})
})
it('removes the demo banner when the backend reports real mode',async()=>{
 response.provider_mode='mock';wire();render(<App/>);const user=userEvent.setup()
 await user.type(screen.getByLabelText('Votre envie du moment'),'Bonjour{Enter}')
 await screen.findByText('Mode démonstration du serveur — aucun modèle réel.')
 response={...response,provider_mode:'real',revision:response.revision+1,assistant_message:'Proposition du modèle réel.'}
 await user.type(screen.getByLabelText('Votre envie du moment'),'Une salade{Enter}')
 await screen.findByText('Proposition du modèle réel.')
 expect(screen.queryByText('Mode démonstration du serveur — aucun modèle réel.')).not.toBeInTheDocument()
})
it('shows a real provider error without a fake greeting or demo banner',async()=>{
 response.provider_mode='real';wire();render(<App/>);const user=userEvent.setup()
 await user.type(screen.getByLabelText('Votre envie du moment'),'Une salade{Enter}');await screen.findByText('55 MAD')
 fetchMock.mockImplementation(async(_url,options)=>({ok:false,status:503,json:async()=>({...response,conversation_id:JSON.parse(options.body).conversation_id,revision:response.revision+1,accepted:false,assistant_message:null,actions:[],error:{code:'PROVIDER_UNAVAILABLE',message:'Le modèle est temporairement indisponible.'}})}))
 await user.type(screen.getByLabelText('Votre envie du moment'),'Du maïs{Enter}');await screen.findByRole('alert')
 expect(screen.getByRole('alert')).toHaveTextContent('Le modèle est temporairement indisponible.')
 expect(screen.queryByText('Mode démonstration du serveur — aucun modèle réel.')).not.toBeInTheDocument()
 expect(screen.queryByText('Bienvenue chez 12-KOUL ! Que souhaitez-vous composer ?')).not.toBeInTheDocument()
})
it('reports the selected dish completeness independently of other unfinished drafts',()=>{
 const result=chatResponse.parse(fixtures.complete)
 result.quote.orderable=false
 render(<Composition category="salad" result={result} busy={false} onConfirm={()=>{}} onAdd={()=>{}}/>)
 expect(screen.getByText('Composition complète')).toBeVisible()
 expect(screen.getByRole('button',{name:'Ajouter au panier ↗'})).toBeEnabled()
 expect(screen.getByRole('button',{name:/Valider la composition/})).toBeDisabled()
})
