import { z } from 'zod'
const category = z.enum(['salad','sandwich','plat','drink'])
const draft = z.object({type:category,size:z.enum(['small','large']).nullable(),slots:z.record(z.string(),z.array(z.string()))})
const meal = z.object({active_category:category.nullable(),categories:z.record(z.string(),draft)})
const missing = z.union([z.object({category:z.string(),slot:z.string(),count:z.number().int().positive()}),z.object({category:z.literal('salad'),size_required:z.literal(true)})])
const quote = z.object({currency:z.literal('MAD'),total:z.number().int().nonnegative().nullable(),orderable:z.boolean(),missing:z.array(missing),lines:z.array(z.object({category,meal:draft,amount:z.number().int().nonnegative().nullable(),complete:z.boolean()}))})
const item = z.object({id:z.string(),name:z.record(z.string(),z.string())})
const action=z.discriminatedUnion('type',[
 z.object({type:z.literal('SET_CATEGORY'),category}).strict(),
 z.object({type:z.literal('SET_SIZE'),size:z.enum(['small','large'])}).strict(),
 z.object({type:z.literal('ADD_ITEM'),item_id:z.string()}).strict(),
 z.object({type:z.literal('REMOVE_ITEM'),item_id:z.string()}).strict(),
 z.object({type:z.literal('RECOMMEND_ITEM'),item_id:z.string()}).strict(),
 z.object({type:z.literal('CLEAR_CATEGORY'),category}).strict(),
 z.object({type:z.literal('CLEAR_MEAL')}).strict(),
 z.object({type:z.literal('CONFIRM_ORDER')}).strict(),
])
const error = z.object({code:z.string(),message:z.string()})
const cartSchema=z.object({lines:z.array(z.object({id:z.string(),meal_state:meal,quote,items:z.array(item)})),total:z.number().int().nonnegative(),currency:z.literal('MAD'),confirmed:z.boolean(),external_order_submitted:z.literal(false)})
export const chatResponse = z.object({conversation_id:z.string(),revision:z.number().int().nonnegative(),prompt_version:z.literal('v3'),cart:cartSchema.nullable().optional().default(null),provider_mode:z.enum(['mock','real']),accepted:z.boolean(),assistant_message:z.string().nullable(),model_text_trusted:z.literal(false),actions:z.array(action).max(64),meal_state:meal,quote,display:z.object({message:z.string(),facts:z.object({quote,selected_items:z.array(item),recommended_items:z.array(item),allergen_scope:z.array(z.string()),allergen_note:z.string(),nutrition_available:z.boolean(),availability_tracked:z.boolean()})}),limits:z.object({fictional_menu:z.boolean(),nutrition_available:z.boolean(),availability_tracked:z.boolean(),allergen_scope:z.array(z.string()),allergen_note:z.string(),external_order_submitted:z.literal(false),payments_supported:z.literal(false)}),error:error.nullable()})
export type ChatResult = z.infer<typeof chatResponse>
export type ChatInput = {conversation_id:string;message:string;locale:'fr';cart_mode?:boolean;cart_command?:'add'|'remove'|'confirm';cart_category?:'salad'|'sandwich'|'plat'|'drink';cart_line_id?:string;expected_revision?:number;confirm_composition?:boolean;remove_item_id?:string}
export class ApiFailure extends Error {constructor(message:string,public uncertain=false){super(message)}}
const base=(import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/,'')
async function request(path:string,method:string,body?:ChatInput){
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),130000)
 try{
  const response=await fetch(base+path,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined,signal:controller.signal})
  let data:unknown;try{data=await response.json()}catch{throw new ApiFailure('Réponse du serveur illisible. Votre composition affichée est conservée.',true)}
  return {response,data}
 }catch(e){if(e instanceof ApiFailure)throw e;throw new ApiFailure(controller.signal.aborted?'Le délai est dépassé. Le serveur a peut-être traité le message.':'Impossible de joindre le restaurant. Vérifiez que le backend est démarré.',true)}finally{clearTimeout(timer)}
}
export const chatApi={
 async sendMessage(input:ChatInput):Promise<ChatResult>{
  const {response,data}=await request('/chat','POST',input);const parsed=chatResponse.safeParse(data)
  if(parsed.success){
   if(parsed.data.conversation_id!==input.conversation_id || parsed.data.revision<=(input.expected_revision??0) || parsed.data.accepted!==response.ok || (parsed.data.accepted?parsed.data.error!==null:parsed.data.error===null))throw new ApiFailure('Réponse incohérente : composition conservée.',true)
   return parsed.data
  }
  const failure=z.object({error}).safeParse(data)
  if(!response.ok && failure.success)throw new ApiFailure(failure.data.error.message,response.status>=500)
  throw new ApiFailure('Réponse du serveur invalide : composition conservée.',true)
 },
 async resetConversation(id:string){
  const {response,data}=await request('/chat/'+encodeURIComponent(id),'DELETE')
  const result=z.object({conversation_id:z.literal(id),deleted:z.boolean()}).safeParse(data)
  if(!response.ok || !result.success)throw new ApiFailure('Le reset n’a pas abouti. Votre conversation est conservée.')
 }
}
