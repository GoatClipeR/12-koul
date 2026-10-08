import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Environment, Lightformer, OrbitControls, Html } from '@react-three/drei'
import { Bloom, EffectComposer, SMAA, ToneMapping, N8AO } from '@react-three/postprocessing'
import { ToneMappingMode } from 'postprocessing'
import { Group, NoToneMapping, PCFShadowMap, PerspectiveCamera, CanvasTexture } from 'three'
import { SceneMotion, ArrivalLight } from '../3d/SceneMotion'
import { useReducedMotion } from '../experience/useReducedMotion'
import { approach } from './motion'
import { Bowl, Ingredient } from './Ingredients'
import { projectMeal, type IngredientKind, type MealState } from './mealScene'


function Composition({meal,reduced}: {meal:MealState;reduced:boolean}) {
  const ref=useRef<Group>(null!), scale=useRef(1), view=useMemo(()=>projectMeal(meal),[meal])
  const [visited,setVisited]=useState<IngredientKind[]>(view.ingredients)
  useEffect(()=>{setVisited(previous=>view.ingredients.every(k=>previous.includes(k))?previous:[...new Set([...previous,...view.ingredients])])},[view])
  useFrame((_,delta)=>{
    scale.current=approach(scale.current,view.scale,delta,reduced)
    ref.current.visible=scale.current>0
    ref.current.scale.setScalar(scale.current)
  })
  return <group ref={ref} rotation={[0,.12,0]}><Bowl/>{visited.map(kind=><Ingredient key={kind} kind={kind} active={view.ingredients.includes(kind)} reduced={reduced} hasLeaves={view.ingredients.includes('lettuce')}/>)}</group>
}
function ProductCamera({view}:{view:number}){
  const {camera,size}=useThree()
  useEffect(()=>{camera.position.set(3.1,3.7,4.6);camera.lookAt(0,.65,0)},[camera,view])
  useEffect(()=>{
    // Preserve the product's horizontal fit in portrait; no abrupt whole-page scaling.
    const c=camera as PerspectiveCamera
    c.fov=Math.max(32,2*Math.atan(Math.tan(16*Math.PI/180)/Math.min(1,size.width/size.height))*180/Math.PI)
    c.updateProjectionMatrix()
  },[camera,size.width,size.height])
  return null
}
function ContactPatch({meal,reduced}: {meal:MealState;reduced:boolean}) {
  const ref=useRef<Group>(null!), scale=useRef(1), view=projectMeal(meal)
  const texture=useMemo(()=>{
    const canvas=document.createElement('canvas');canvas.width=canvas.height=128
    const ctx=canvas.getContext('2d')!, gradient=ctx.createRadialGradient(64,64,12,64,64,64)
    gradient.addColorStop(0,'rgba(42,20,11,.23)');gradient.addColorStop(.55,'rgba(42,20,11,.12)');gradient.addColorStop(1,'rgba(42,20,11,0)')
    ctx.fillStyle=gradient;ctx.fillRect(0,0,128,128);return new CanvasTexture(canvas)
  },[])
  useEffect(()=>()=>texture.dispose(),[texture])
  useFrame((_,delta)=>{scale.current=approach(scale.current,view.scale,delta,reduced);ref.current.scale.setScalar(scale.current);ref.current.visible=scale.current>0})
  return <group ref={ref}><mesh rotation={[-Math.PI/2,0,0]} position={[0,.026,0]}><planeGeometry args={[3.8,3.8]}/><meshBasicMaterial map={texture} transparent depthWrite={false}/></mesh></group>
}
export default function SaladScene({meal,active=true,presented=true,view=0}: {meal:MealState;active?:boolean;presented?:boolean;view?:number}) {
  const reduced=useReducedMotion()
  return <Canvas frameloop={active?'always':'never'} shadows={{type:PCFShadowMap}} dpr={[1,1.5]} camera={{position:[3.1,3.7,4.6],fov:32}}
    gl={{alpha:true,antialias:false,powerPreference:'high-performance',toneMapping:NoToneMapping}}
    fallback={<p>La scène nécessite WebGL 2. La composition reste disponible en texte.</p>}>
    <Suspense fallback={<Html center><span style={{whiteSpace:'nowrap',color:'#4D2514'}}>Préparation du bol…</span></Html>}>
      <ProductCamera view={view}/>
      <Environment frames={1} resolution={128}>
        <Lightformer intensity={3} position={[3,5,2]} scale={[5,4,1]} rotation={[-Math.PI/3,0,0]} color="#fff0d7"/>
        <Lightformer intensity={1.6} position={[-4,3,-2]} scale={[4,4,1]} rotation={[0,Math.PI/2,0]} color="#d6e2ed"/>
      </Environment>
      <ambientLight intensity={.7}/>
      <directionalLight castShadow position={[2.5,6,3]} intensity={2.1} color="#fff0d9"
        shadow-mapSize={[2048,2048]} shadow-camera-left={-4} shadow-camera-right={4} shadow-camera-top={4} shadow-camera-bottom={-4}
        shadow-camera-near={.5} shadow-camera-far={14} shadow-radius={4} shadow-normalBias={.025} shadow-bias={-.0001}/>
      <ArrivalLight presented={presented}/><SceneMotion presented={presented}><Composition meal={meal} reduced={reduced}/></SceneMotion>
      <mesh rotation={[-Math.PI/2,0,0]} position={[0,.015,0]} ><planeGeometry args={[200,200]}/><shadowMaterial transparent opacity={.14}/></mesh>
      <ContactPatch meal={meal} reduced={reduced}/>
      <OrbitControls key={view} target={[0,.65,0]} enablePan={false} enableZoom minDistance={5} maxDistance={9} minPolarAngle={.35} maxPolarAngle={1.08} enableDamping={!reduced}/>
      <EffectComposer multisampling={0}>
        <N8AO aoRadius={.18} intensity={.8} distanceFalloff={1} quality="low" color="#594832"/>
        <Bloom intensity={.12} luminanceThreshold={1.1} mipmapBlur/>
        <ToneMapping mode={ToneMappingMode.ACES_FILMIC}/><SMAA/>
      </EffectComposer>
    </Suspense>
  </Canvas>
}
