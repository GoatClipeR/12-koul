import { useEffect, useMemo, useState } from 'react'
import { useGLTF } from '@react-three/drei'
import { Mesh, MeshStandardMaterial } from 'three'
import { FoodTransition } from './ProductStudio'
import { assetUrl } from '../salad/Ingredients'
import { surfaceTexture } from '../salad/surface'
import type { ReactNode } from 'react'
/** Retain departing ingredients for the exit animation; selection is always server state. */
export function Selections({ids,children}:{ids:string[];children:(id:string,index:number)=>ReactNode}){
 const [seen,setSeen]=useState(ids)
 useEffect(()=>setSeen(previous=>ids.every(id=>previous.includes(id))?previous:[...new Set([...previous,...ids])]),[ids.join('|')])
 return <>{seen.map((id,i)=><FoodTransition key={id} active={ids.includes(id)} delay={i*.06}>{children(id,i)}</FoodTransition>)}</>
}
export function AssetPiece({kind,position,rotation=[0,0,0],scale=1}:{kind:string;position:[number,number,number];rotation?:[number,number,number];scale?:number|[number,number,number]}){
 const {scene}=useGLTF(assetUrl(kind),false)
 const owned=useMemo(()=>{const object=scene.clone(true),texture=surfaceTexture(kind),materials:MeshStandardMaterial[]=[];object.traverse(node=>{if(node instanceof Mesh){node.castShadow=true;node.receiveShadow=true;const clone=(m:MeshStandardMaterial)=>{const next=m.clone();next.bumpMap=texture;next.bumpScale=kind==='chicken'?.012:.003;materials.push(next);return next};node.material=Array.isArray(node.material)?node.material.map(m=>clone(m as MeshStandardMaterial)):clone(node.material as MeshStandardMaterial)}});return {object,texture,materials}},[scene,kind])
 useEffect(()=>()=>{owned.texture.dispose();owned.materials.forEach(m=>m.dispose())},[owned])
 return <primitive object={owned.object} position={position} rotation={rotation} scale={scale} dispose={null}/>
}
