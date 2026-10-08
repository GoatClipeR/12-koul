import type { ChatResult } from '../api/chatApi'
export function Cart({result,busy,remove,confirm}:{result:ChatResult|null;busy:boolean;remove:(id:string)=>void;confirm:()=>void}){
 const cart=result?.cart
 return <section className="cart-panel" id="panier" aria-label="Panier"><div className="composition-top"><div><p className="eyebrow">À PARTAGER · OU PAS</p><h2>Votre panier<span className="red">.</span></h2></div><span>{cart?.lines.length??0} ligne(s)</span></div>
 {!cart?.lines.length?<p className="quiet">Ajoutez une composition complète. Les boissons rejoignent directement le panier.</p>:<ul>{cart.lines.map((line,index)=><li key={line.id}><div><strong>{Object.keys(line.meal_state.categories).map(c=>({salad:'Salade',sandwich:'Sandwich',plat:'Plat',drink:'Boisson'})[c]).join(', ')} <small>#{index+1}</small></strong><p>{line.items.map(i=>i.name.fr).join(' · ')}</p></div><strong>{line.quote.total} MAD</strong><button disabled={busy} aria-label={`Supprimer la ligne ${index+1}`} onClick={()=>remove(line.id)}>×</button></li>)}</ul>}
 <div className="cart-total"><span>Total panier</span><strong>{cart?.total??0} MAD</strong></div><button className="confirm" disabled={busy||!cart?.lines.length||!!result?.quote.lines.length||cart.confirmed} onClick={confirm}>{cart?.confirmed?'Panier validé ✓':'Confirmer le panier'}</button>
 {!!result?.quote.lines.length&&<p className="quiet">Ajoutez vos brouillons complets au panier avant confirmation.</p>}
 {cart?.confirmed&&<p role="status">Simulation validée. Aucune commande envoyée en cuisine.</p>}<p className="quiet">Projet universitaire · aucun paiement, aucune commande externe.</p></section>
}
