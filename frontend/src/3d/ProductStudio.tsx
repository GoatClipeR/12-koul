import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, ContactShadows, Environment, Lightformer } from '@react-three/drei'
import { ACESFilmicToneMapping, Group, MeshStandardMaterial } from 'three'
import { useEffect, useMemo, useRef, type ReactNode } from 'react'
import { SceneMotion, ArrivalLight } from './SceneMotion'
import { useReducedMotion } from '../experience/useReducedMotion'
import { springStep } from '../salad/motion'
import { surfaceTexture } from '../salad/surface'
function CameraReset({view}:{view:number}){
 const {camera}=useThree()
 useEffect(()=>{camera.position.set(3.4,4.3,5.7);camera.lookAt(0,.6,0)},[camera,view])
 return null
}
export function ProductStudio({children,active=true,presented=true,view=0}:{children:ReactNode;active?:boolean;presented?:boolean;view?:number}){
 return <Canvas shadows frameloop={active?'always':'never'} dpr={[1,1.5]} camera={{position:[3.4,4.3,5.7],fov:32}} gl={{alpha:true,toneMapping:ACESFilmicToneMapping}} fallback={<p>Vue 3D indisponible. Votre composition reste disponible en texte.</p>}>
 <CameraReset view={view}/><ambientLight intensity={.65}/><hemisphereLight args={['#fff2d7','#806043',1]}/><directionalLight castShadow position={[2,6,3]} intensity={2.6} color="#fff0d7" shadow-mapSize={[1024,1024]}/><directionalLight position={[-3,3,-2]} intensity={1.2} color="#e5eced"/>
 <Environment resolution={128} frames={1}><Lightformer intensity={2.5} position={[3,5,2]} scale={[5,4,1]} rotation={[-Math.PI/3,0,0]} color="#fff0da"/><Lightformer intensity={1} position={[-4,3,-2]} scale={[4,4,1]} rotation={[0,Math.PI/2,0]} color="#dce4ea"/></Environment>
 <ArrivalLight presented={presented}/><SceneMotion presented={presented}><group position={[0,.1,0]}>{children}</group></SceneMotion><ContactShadows position={[0,-.03,0]} opacity={.36} scale={9} blur={2.8} far={3} resolution={512}/><OrbitControls key={view} target={[0,.6,0]} enablePan={false} minDistance={5} maxDistance={8.8} minPolarAngle={.4} maxPolarAngle={1.15} enableDamping dampingFactor={.07}/></Canvas>
}
export function FoodPiece({position,scale,color,rotation=[0,0,0],roughness=.75}:{position:[number,number,number];scale:[number,number,number];color:string;rotation?:[number,number,number];roughness?:number}){
 const material=useMemo(()=>{const map=surfaceTexture(roughness>.7?'croutons':'chicken');return new MeshStandardMaterial({color,roughness,bumpMap:map,bumpScale:roughness>.7?.025:.008})},[color,roughness])
 useEffect(()=>()=>{material.bumpMap?.dispose();material.dispose()},[material])
 return <mesh position={position} scale={scale} rotation={rotation} castShadow receiveShadow material={material}><sphereGeometry args={[1,40,24]}/></mesh>
}
/** Keep departing selections mounted until their exit has finished. No inferred food state. */
export function FoodTransition({active,children,delay=0}:{active:boolean;children:ReactNode;delay?:number}){
 const reduced=useReducedMotion()
 const ref=useRef<Group>(null!);const elapsed=useRef(0);const value=useRef(0);const velocity=useRef(0);const previous=useRef(active)
 useFrame((_,dt)=>{
  if(previous.current!==active){elapsed.current=0;previous.current=active}
  elapsed.current+=Math.min(dt,.05)
  const target=active&&elapsed.current>=delay?1:0
  const step=reduced?[Number(active),0]:springStep(value.current,velocity.current,target,dt)
  value.current=step[0];velocity.current=step[1]
  ref.current.visible=value.current>.005;ref.current.scale.setScalar(Math.max(.001,Math.min(1,value.current*2)));ref.current.position.y=(1-value.current)*(active?1.2:-.3)
  ref.current.rotation.z=(1-value.current)*.08
 })
 return <group ref={ref}>{children}</group>
}
