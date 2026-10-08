import { Component,lazy,Suspense,useEffect,useState,type ReactNode } from 'react'
import { projectMeal,type MealState } from '../salad/mealScene'
const SandwichScene=lazy(()=>import('./SandwichScene'))
const PlatsScene=lazy(()=>import('./PlatsScene'))
const SaladScene=lazy(()=>import('../salad/SaladScene'))
const DrinkScene=lazy(()=>import('./DrinkScene'))
class SceneBoundary extends Component<{children:ReactNode},{failed:boolean}>{
 state={failed:false};static getDerivedStateFromError(){return {failed:true}}
 render(){return this.state.failed?<p className="scene-fallback">La vue 3D est indisponible. Votre composition reste accessible.</p>:this.props.children}
}
function StageLayer({active,children}:{active:boolean;children:(running:boolean)=>ReactNode}){
 const [running,setRunning]=useState(active)
 useEffect(()=>{
  if(active){setRunning(true);return}
  const timer=window.setTimeout(()=>setRunning(false),1200)
  return()=>window.clearTimeout(timer)
 },[active])
 return <div className="category-stage" data-active={active} data-running={running} hidden={!active&&!running} aria-hidden={!active}>{children(active||running)}</div>
}
const editorial:Record<string,{title:string;accent:string}>={salad:{title:'Fraîchement',accent:'vous.'},sandwich:{title:'À pleines',accent:'dents.'},plat:{title:'L’envie en',accent:'grand.'},drink:{title:'Un instant',accent:'de fraîcheur.'}}
export function MealScene({meal,category='salad',drinkId,feedback}:{meal:MealState;category?:string;drinkId?:string;feedback?:{id:number;label:string}|null}){
 const [visited,setVisited]=useState([category]);const [view,setView]=useState(0)
 useEffect(()=>{
  // Warm the small category modules after the initial dish is visible. Canvas
  // roots still mount only on first visit; first selection avoids a blank load.
  const timer=window.setTimeout(()=>{void Promise.allSettled([import('./SandwichScene'),import('./PlatsScene'),import('./DrinkScene')])},1200)
  return()=>window.clearTimeout(timer)
 },[])
 useEffect(()=>setVisited(previous=>previous.includes(category)?previous:[...previous,category]),[category])
 const copy=editorial[category];const hasMeal=!!meal.categories[category]||(category==='drink'&&!!drinkId)
 const unmapped=category==='salad'?projectMeal(meal).unmapped.length:0
 return <section className="hero-scene" aria-label="Votre composition visuelle">
  <div className="hero-heading" key={category}><h1>{copy.title}<br/><em>{copy.accent}</em></h1></div>
  <div className="stage-floor" aria-hidden="true"/>
  <div className="canvas-wrap">{visited.map(id=><StageLayer key={id} active={id===category}>{running=><SceneBoundary><Suspense fallback={<p className="scene-fallback">Mise en place de votre table…</p>}>{id==='salad'?<SaladScene meal={meal} active={running} presented={id===category} view={view}/>:id==='sandwich'?<SandwichScene meal={meal} active={running} presented={id===category} view={view}/>:id==='plat'?<PlatsScene meal={meal} active={running} presented={id===category} view={view}/>:<DrinkScene id={drinkId} active={running} presented={id===category} view={view}/>}</Suspense></SceneBoundary>}</StageLayer>)}</div>
  {feedback&&<div key={feedback.id} className="scene-feedback" aria-hidden="true"><span>✓</span> {feedback.label}</div>}

  <div className="scene-caption"><div><span className="live-dot"/>{hasMeal?'VOTRE COMPOSITION':'VOTRE PLAT EN 3D'}{unmapped>0&&<small>{unmapped} sélection(s) affichée(s) dans la composition, sans modèle 3D.</small>}</div><button onClick={()=>setView(v=>v+1)} aria-label="Recentrer la vue 3D">⟲</button><span className="orbit-hint">Glissez pour explorer <b>↔</b><small>Molette pour vous rapprocher</small></span></div>
 </section>
}
