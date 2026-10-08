import { useRef, useState } from 'react'
import { ApiFailure,chatApi,type ChatInput,type ChatResult } from '../api/chatApi'
export type Message={id:number;role:'user'|'assistant';text:string;fact?:string}
export function useConversation(){
 const [id,setId]=useState(()=>crypto.randomUUID())
 const [messages,setMessages]=useState<Message[]>([])
 const [result,setResult]=useState<ChatResult|null>(null)
 const [busy,setBusy]=useState(false)
 const [failure,setFailure]=useState<{message:string;uncertain:boolean;retry:()=>void}|null>(null)
 const lock=useRef(false);const serial=useRef(0);const current=useRef<ChatResult|null>(null)
 async function send(text:string,confirmation=false,removeItemId?:string,cartCommand?:Pick<ChatInput,'cart_command'|'cart_category'|'cart_line_id'>){
  if(lock.current||!text.trim())return
  lock.current=true;setBusy(true);setFailure(null)
  const value=text.trim();setMessages(m=>[...m,{id:++serial.current,role:'user',text:value}])
  try{
   const answer=await chatApi.sendMessage({conversation_id:id,message:value,locale:'fr',cart_mode:true,...cartCommand,expected_revision:current.current?.revision??0,...(confirmation?{confirm_composition:true}:{}),...(removeItemId?{remove_item_id:removeItemId}:{})})
   // Error turns retain server state; never infer a selection from model prose.
   if(!answer.accepted && JSON.stringify(answer.meal_state)!==JSON.stringify(current.current?.meal_state??{active_category:null,categories:{}}))throw new ApiFailure('Réponse incohérente : votre repas est conservé.',true)
   current.current=answer;setResult(answer)
   setMessages(m=>[...m,{id:++serial.current,role:'assistant',text:answer.assistant_message??answer.error?.message??answer.display.message,fact:answer.assistant_message?answer.display.message:undefined}])
   if(!answer.accepted)setFailure({message:answer.error!.message,uncertain:false,retry:()=>void send(value,confirmation,removeItemId,cartCommand)})
  }catch(e){setFailure({message:e instanceof Error?e.message:'Une erreur est survenue.',uncertain:e instanceof ApiFailure&&e.uncertain,retry:()=>void send(value,confirmation,removeItemId,cartCommand)})}
  finally{lock.current=false;setBusy(false)}
 }
 async function reset(){
  if(lock.current)return
  lock.current=true;setBusy(true);setFailure(null)
  try{await chatApi.resetConversation(id);setId(crypto.randomUUID());setMessages([]);current.current=null;setResult(null)}
  catch(e){setFailure({message:e instanceof Error?e.message:'Reset impossible.',uncertain:false,retry:()=>void reset()})}
  finally{lock.current=false;setBusy(false)}
 }
 return {id,messages,result,busy,failure,send,reset}
}
