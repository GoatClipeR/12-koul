import { Component, lazy, Suspense, useState, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/bricolage-grotesque'
import '@fontsource-variable/figtree'
import '../design/tokens.css'
import './salad.css'
import { demoMeal } from './mealScene'
const SaladScene=lazy(()=>import('./SaladScene'))
class SceneBoundary extends Component<{children:ReactNode},{failed:boolean}> {
  state={failed:false}
  static getDerivedStateFromError(){return {failed:true}}
  render(){return this.state.failed?<p className="fallback">La vue 3D est indisponible sur cet appareil. Retrouvez les ingrédients ci-dessous.</p>:this.props.children}
}
function App(){
 const [key,setKey]=useState(0)
 const [meal,setMeal]=useState(demoMeal)
 const review=import.meta.env.DEV && new URLSearchParams(location.search).has('review')
 return <main>
   <header><a href="./" aria-label="12-KOUL, accueil"><img src={`${import.meta.env.BASE_URL}brand/logo_12kool.png`} alt="12-KOUL — Fast Food & Drinks"/></a><span>LE SALAD BAR</span><span className="edition">ÉTUDE N° 01</span></header>
   <section className="intro"><p className="eyebrow">FRAÎCHEUR, EN GRAND.</p><h1>Une belle<br/><em>composition.</em></h1><p className="description">Du croquant, de la couleur, du caractère.<br/>La grande salade 12-KOUL prend forme.</p></section>
   <section className="scene" aria-label="Grande salade en 3D : faites glisser pour tourner le bol">
     <SceneBoundary><Suspense fallback={<p className="fallback">Mise en place de votre salade…</p>}><SaladScene key={key} meal={meal}/></Suspense></SceneBoundary>
   </section>
   <div className="scene-caption"><span>GRANDE SALADE · VUE 3D</span><button onClick={()=>setKey(k=>k+1)}>Recentrer la vue ↗</button></div>
   {review && <nav aria-label="Contrôles QA locaux" style={{display:'flex',gap:16,flexWrap:'wrap'}}>
     <button onClick={()=>setMeal({...demoMeal,categories:{salad:{...demoMeal.categories.salad,slots:{...demoMeal.categories.salad.slots,sauce:[]}}}})}>QA sans sauce</button>
     <button onClick={()=>setMeal({active_category:null,categories:{}})}>QA vider</button>
     <button onClick={()=>setMeal({...demoMeal,categories:{salad:{type:'salad',size:'small',slots:{base:['salad.base.lettuce'],ingredient:['salad.ingredient.tomato','salad.ingredient.cucumber'],topping:['salad.topping.croutons'],sauce:['salad.sauce.caesar']}}}})}>QA petite</button>
     <button onClick={()=>setMeal(demoMeal)}>QA restaurer</button>
   </nav>}
   <footer><div><p className="eyebrow">DANS LE BOL</p><p>Laitue · Tomate · Concombre · Poulet grillé<br/>Maïs · Croûtons · Sauce Caesar</p></div><div className="note"><span className="dot"/> Composition en cours<p>Étude visuelle de 7 ingrédients.<br/>Les choix requis restent à compléter.</p></div><span className="gesture">Glissez pour explorer ↔</span></footer>
 </main>
}
createRoot(document.getElementById('root')!).render(<App/> )
