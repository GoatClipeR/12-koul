import { useEffect, useRef, useState } from 'react'
import { KOOLChat } from '../chat/KOOLChat'
import { Composition } from '../meal/Composition'
import { Cart } from '../meal/Cart'
import { MealScene } from '../3d/MealScene'
import { useConversation } from '../state/useConversation'
import { Atmosphere } from '../experience/Atmosphere'
import { mealFeedback } from '../experience/mealFeedback'
import type { ChatResult } from '../api/chatApi'
import menu from '../../../backend/app/data/menu.json'
const empty={active_category:null,categories:{}}
const categories={salad:['SALAD BAR'],sandwich:['SANDWICH'],plat:['PLATS'],drink:['BOISSONS']} as const
export type Category=keyof typeof categories
export function App(){
 const chat=useConversation();const [category,setCategory]=useState<Category>('salad');const [drawer,setDrawer]=useState<'cart'|'menu'|'about'|null>(null)
 const dialog=useRef<HTMLDialogElement>(null)
 const previousCartIds=useRef(new Set<string>())
 useEffect(()=>{
  const result=chat.result
  if(!result){previousCartIds.current.clear();setCategory('salad');return}
  const lines=result.cart?.lines??[]
  // Drinks move straight into the validated cart, so the remaining draft's
  // active category does not identify the drink the guest just selected.
  const addedDrink=lines.some(line=>!previousCartIds.current.has(line.id)&&line.items.some(item=>item.id.startsWith('drink.')))
  previousCartIds.current=new Set(lines.map(line=>line.id))
  if(!result.accepted)return
  if(addedDrink)setCategory('drink')
  else if(result.meal_state.active_category)setCategory(result.meal_state.active_category)
 },[chat.result])
 useEffect(()=>{if(drawer)dialog.current?.showModal();else dialog.current?.close()},[drawer])
 const previousResult=useRef<ChatResult|null>(null)
 const [feedback,setFeedback]=useState<{id:number;label:string}|null>(null)
 useEffect(()=>{if(chat.busy)setFeedback(null)},[chat.busy])
 useEffect(()=>{
  const label=mealFeedback(previousResult.current,chat.result)
  previousResult.current=chat.result
  if(label)setFeedback(old=>({id:(old?.id??0)+1,label}))
 },[chat.result])
 const count=chat.result?.cart?.lines.length??0
 function select(id:Category){setCategory(id)}
 return <div className="restaurant" data-category={category}>
  <Atmosphere category={category}/>
  <header className="main-header"><a className="brand" href="/" aria-label="12-KOUL accueil"><img src={`${import.meta.env.BASE_URL}brand/logo_12kool-transparent.svg`} alt="12-KOUL Fast Food & Drinks"/></a><div className="header-tools"><button disabled={chat.busy} onClick={()=>void chat.reset()} className="new-chat" aria-label="Nouvelle conversation">Recommencer <span>↺</span></button><button onClick={()=>setDrawer('cart')} className="basket">Mon panier <span>{count}</span></button></div></header>
  <main className="experience">
   <aside className="menu-rail"><div className="rail-heading"><p className="eyebrow">LA CARTE</p></div><nav aria-label="Carte du restaurant">{Object.entries(categories).map(([id,[name]])=><button className="category-choice" key={id} aria-label={name} aria-current={category===id?'page':undefined} onClick={()=>select(id as Category)} onPointerMove={e=>{const rect=e.currentTarget.getBoundingClientRect();e.currentTarget.style.setProperty('--pointer-x',`${(e.clientX-rect.left)/rect.width-.5}`);e.currentTarget.style.setProperty('--pointer-y',`${(e.clientY-rect.top)/rect.height-.5}`)}} onPointerLeave={e=>{e.currentTarget.style.setProperty('--pointer-x','0');e.currentTarget.style.setProperty('--pointer-y','0')}}><img src={`${import.meta.env.BASE_URL}images/${id}.png`} alt=""/><span className="category-copy"><strong>{name}</strong></span><span className="category-arrow" aria-hidden="true">↗</span></button>)}</nav><button className="full-menu" onClick={()=>setDrawer('menu')}>Explorer les ingrédients <span>↗</span></button></aside>
   <div className="stage-layout">
    <MealScene feedback={feedback} meal={chat.result?.meal_state??empty} category={category} drinkId={chat.result?.cart?.lines.flatMap(l=>l.items).filter(i=>i.id.startsWith('drink.')).at(-1)?.id}/>
    <aside id="composition" className="composition-dock">
     {category==='drink'?<section className="drink-menu"><p className="eyebrow">À LA CARTE</p><h2>Choisissez<br/>votre boisson.</h2><div>{menu.items.filter(i=>i.category==='drink').map(i=><button disabled={chat.busy} key={i.id} onClick={()=>void chat.send(`Ajoute un ${i.name.fr}.`)}><span>{i.name.fr}</span><small>{i.price} MAD</small><b>＋</b></button>)}</div></section>:<Composition category={category} result={chat.result} busy={chat.busy} onRemove={(id,name)=>void chat.send(`Enlève ${name}.`,false,id)} onConfirm={()=>void chat.send('Je souhaite valider cette composition.',true)} onAdd={()=>void chat.send('Ajouter ma composition au panier.',false,undefined,{cart_command:'add',cart_category:category})}/>}
    </aside>
    <KOOLChat {...chat} category={category} feedback={feedback}/>
   </div>
  </main>
  <footer className="main-footer"><span>12-KOUL · FAST FOOD & DRINKS</span><button onClick={()=>setDrawer('about')}>À propos de KOOL AI ↗</button></footer>
  {chat.result?.provider_mode==='mock'&&<p className="mode-note">Mode démonstration du serveur — aucun modèle réel.</p>}
  <dialog ref={dialog} aria-label={drawer==='cart'?'Votre panier':drawer==='menu'?'Les ingrédients':'À propos de KOOL AI'} className="experience-drawer" onCancel={()=>setDrawer(null)} onClick={e=>{if(e.target===e.currentTarget)setDrawer(null)}}><div className="drawer-content"><button className="drawer-close" onClick={()=>setDrawer(null)} aria-label="Fermer">×</button>
   {drawer==='cart'&&<Cart result={chat.result} busy={chat.busy} remove={id=>void chat.send('Retirer cette ligne du panier.',false,undefined,{cart_command:'remove',cart_line_id:id})} confirm={()=>void chat.send('Confirmer mon panier de simulation.',false,undefined,{cart_command:'confirm'})}/>}
   {drawer==='menu'&&<section className="menu-guide"><p className="eyebrow">LA CARTE · {categories[category][0]}</p><h2>Les bons ingrédients.</h2><p className="quiet">Dites à KOOL AI ce qui vous fait envie.</p>{Object.entries(menu.categories[category].slot_labels).map(([slot,label])=><div className="menu-slot" key={slot}><h3>{label.fr}</h3>{menu.items.filter(i=>i.category===category&&i.slot===slot).map(i=><button key={i.id} disabled={chat.busy} onClick={()=>{void chat.send(`Pour ${category==='salad'?'ma salade':category==='sandwich'?'mon sandwich':category==='plat'?'mon plat':'ma boisson'}, ajoute ${i.name.fr}.`);setDrawer(null)}}>{i.name.fr}<span>＋</span></button>)}</div>)}</section>}
   {drawer==='about'&&<section className="about"><p className="eyebrow">VOTRE COMPLICE EN CUISINE</p><h2>Rencontrez KOOL AI.</h2><p>Décrivez vos envies, puis regardez votre composition prendre forme. KOOL AI vous accompagne à partir de la carte 12-KOUL.</p><p>{chat.result?.limits.allergen_note??'Pour les allergènes, consultez le personnel. Nutrition et disponibilité non suivies.'}</p><p>Pour retirer un ingrédient, utilisez × dans votre composition. Les prix et les choix affichés sont validés par le restaurant.</p><p>Simulation universitaire. Aucune commande envoyée, aucun paiement.</p></section>}
  </div></dialog>
 </div>
}
