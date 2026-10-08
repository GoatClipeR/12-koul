import menu from '../../../backend/app/data/menu.json'
import type { ChatResult } from '../api/chatApi'
const labels:Record<string,string>={base:'Bases',ingredient:'Ingrédients',topping:'Toppings',sauce:'Sauces',bread:'Pain',protein:'Protéine',cheese:'Fromage',vegetable:'Légumes',extra:'Extras',side:'Accompagnement',drink:'Boisson'}
export function Composition({result,onConfirm,onRemove,busy,category,onAdd}:{result:ChatResult|null;onConfirm:()=>void;onRemove?:(id:string,name:string)=>void;busy:boolean;category?:string;onAdd?:()=>void}){
 const selectedCategory=category??result?.meal_state.active_category??'salad'
 const salad=result?.meal_state.categories[selectedCategory]
 const line=result?.quote.lines.find(l=>l.category===selectedCategory)
 const amount=category?line?.amount:result?.quote.total
 const names=new Map(result?.display.facts.selected_items.map(i=>[i.id,i.name.fr])??[])
 return <section className="composition" aria-labelledby="composition-title"><div className="composition-top"><div><p className="eyebrow">VOTRE CRÉATION</p><h2 id="composition-title">Votre composition<span className="red">.</span></h2></div><span className="meal-size">{selectedCategory!=='salad'?({sandwich:'Sandwich',plat:'Plat',drink:'Boisson'}[selectedCategory]??'Composition'):salad?.size==='large'?'Grande salade':salad?.size==='small'?'Petite salade':'À vous de composer'}</span></div>
 {!salad||(selectedCategory==='salad'&&!salad.size)?<p className="quiet">Tout commence par une envie. Choisissez votre format avec KOOL AI, puis composez à votre façon.</p>:<div className="slots">{Object.entries(salad.slots).map(([slot,ids])=>{
  const missing=result!.quote.missing.find(m=>'slot' in m&&m.category===selectedCategory&&m.slot===slot)
  const rules=(menu.categories as Record<string,{slots?:Record<string,{min:number;max:number}>}>)[selectedCategory]?.slots?.[slot]
  const optional=rules?.min===0
  const target=optional?rules!.max:ids.length+(missing&&'count'in missing?missing.count:0)
  return <div className="slot" key={slot}><div><h3>{labels[slot]??slot}</h3><span>{ids.length} / {target}</span></div><div className="seeds" aria-label={`${labels[slot]??slot} : ${ids.length} sur ${target}`}>{Array.from({length:Math.min(target,64)},(_,i)=><span key={i} className={i<ids.length?'filled':''} aria-hidden="true"/>)}</div><div className="selected-items">{ids.length?ids.map(id=><span key={id}>{names.get(id)??id}{onRemove&&<button disabled={busy} aria-label={`Retirer ${names.get(id)??id}`} onClick={()=>onRemove(id,names.get(id)??id)}>×</button>}</span>):<p>{optional?'Optionnel':'Votre choix reste à faire'}</p>}</div></div>
 })}</div>}
 <div className="quote-row"><div><span className="eyebrow">VOTRE TOTAL</span><strong>{amount!=null&&result?.quote.lines.length?`${amount} ${result.quote.currency}`:'—'}</strong><small>{result?((category?line?.complete:result.quote.orderable)?'Composition complète':'Composition à compléter'):'À composer ensemble.'}</small></div><button className="confirm" disabled={busy||!result?.quote.orderable} onClick={onConfirm}>Valider la composition <span>↗</span></button></div>{onAdd&&<button className="add-cart" disabled={busy||!line?.complete} onClick={onAdd}>Ajouter au panier ↗</button>}<p className="quiet footnote">Validation de composition uniquement. Aucune commande envoyée, aucun paiement.</p>
 </section>
}
