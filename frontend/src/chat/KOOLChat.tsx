import { useState } from 'react'
import type { Message } from '../state/useConversation'
import type { ChatResult } from '../api/chatApi'
import type { Category } from '../components/App'
const starters:Record<Category,[string,string][]>= {
 salad:[['Grande salade','Je veux une grande salade avec poulet et tomate.'],['Petite salade','Je veux une petite salade.'],['Inspirez-moi','Recommande-moi une salade.']],
 sandwich:[['Poulet grillé','Je veux un sandwich au poulet grillé.'],['Baguette','Je veux un sandwich avec une baguette.'],['Inspirez-moi','Recommande-moi un sandwich gourmand.']],
 plat:[['Poulet & frites','Je veux un plat de poulet grillé avec des frites.'],['Steak','Je veux un plat avec un steak.'],['Inspirez-moi','Recommande-moi un plat.']],
 drink:[['Jus d’orange',"Ajoute un jus d'orange."],['Jus de mangue','Ajoute un jus de mangue.'],['Eau gazeuse','Ajoute une petite eau gazeuse.']],
}
export function KOOLChat({messages,busy,failure,send,category='salad',result,feedback}:{messages:Message[];busy:boolean;failure:{message:string;uncertain:boolean;retry:()=>void}|null;send:(text:string)=>Promise<void>;category?:Category;result?:ChatResult|null;feedback?:{id:number;label:string}|null}){
 const [text,setText]=useState('');const [history,setHistory]=useState(false)
 const latest=messages.filter(m=>m.role==='assistant').at(-1)
 const selected=Object.values(result?.meal_state.categories[category]?.slots??{}).flat()
 const suggestions=category==='salad'&&selected.length?[
 ...(!selected.includes('salad.ingredient.corn')?[['Du maïs en plus','Ajoute du maïs à ma salade.'] as [string,string]]:[]),
 ...(!selected.includes('salad.ingredient.grilled_chicken')?[['Poulet grillé','Ajoute du poulet grillé à ma salade.'] as [string,string]]:[]),
 ['Compléter ma salade','Que manque-t-il pour compléter ma salade ?'] as [string,string],
 ]:starters[category]
 function submit(){if(!busy&&text.trim()){void send(text);setText('')}}
 return <section id="kool-chat" className="chat-panel" data-state={busy?'thinking':feedback?'updated':'idle'} aria-labelledby="chat-title">
  <div className="concierge-line" role="log" aria-label="Conversation KOOL AI" aria-live="polite"><span className="concierge-spark" aria-hidden="true">✳</span>{busy?<p role="status" className="thinking">Un instant, on s’occupe de vous…</p>:<p>{latest?.text??'Une envie en tête ? On lui donne forme, ensemble.'}</p>}{messages.length>0&&<button className="history-toggle" onClick={()=>setHistory(!history)} aria-expanded={history} aria-label="Voir la conversation">↶</button>}</div>
  {!busy&&feedback&&<p className="sr-only" aria-live="polite">{feedback.label}</p>}
  {!busy&&!!result?.display.facts.recommended_items.length&&<div className="recommended-choices"><span>LE CONSEIL KOOL</span>{result.display.facts.recommended_items.map(item=><button key={item.id} onClick={()=>void send(`Ajoute ${item.name.fr}.`)}>{item.name.fr} <b>＋</b></button>)}</div>}
  {history&&<div className="conversation-history"><button onClick={()=>setHistory(false)} aria-label="Fermer la conversation">×</button>{messages.map(m=><article className={'message '+m.role} key={m.id}><span className="eyebrow">{m.role==='user'?'VOUS':'KOOL AI'}</span><p>{m.text}</p>{m.fact&&<p className="verified">✓ {m.fact}</p>}</article>)}</div>}
  {failure&&<div role="alert" className="chat-error"><p>{failure.message}</p>{failure.uncertain&&<small>Réessayer conserve la révision précédente pour éviter un doublon.</small>}<button disabled={busy} onClick={failure.retry}>Réessayer</button></div>}
  <div className="suggestions">{suggestions.map(([label,prompt])=><button key={label} disabled={busy} onClick={()=>void send(prompt)} aria-label={label==='Grande salade'?'Une grande salade, poulet & tomate':label}>{label}<span>＋</span></button>)}</div>
  <form onSubmit={e=>{e.preventDefault();submit()}} className="composer"><div className="composer-brand"><span className="concierge-emblem" aria-hidden="true">✳</span><h2 id="chat-title">KOOL AI</h2><small>Votre concierge gourmand</small></div><label className="sr-only" htmlFor="chat-message">Votre envie du moment</label><div className="composer-field"><textarea id="chat-message" rows={1} maxLength={1000} value={text} disabled={busy} placeholder={selected.length?(category==='salad'?'Un peu de maïs, une touche de sauce…':'Une touche de sauce, un ingrédient en plus…'):'Que voulez-vous manger ?'} onChange={e=>setText(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();submit()}}}/><button disabled={busy||!text.trim()} aria-label="Envoyer le message" type="submit">↑</button></div></form>
  <div className="composer-foot"><span>Entrée ↵ pour envoyer</span></div>
 </section>
}
