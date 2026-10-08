import { memo, useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { approach, springStep } from './motion'
import { useGLTF } from '@react-three/drei'
import { InstancedMesh, Matrix4, Mesh, MeshStandardMaterial, Object3D, Group } from 'three'
import { surfaceTexture, foodColorTexture } from './surface'
import type { IngredientKind } from './mealScene'

export const assetUrl = (name: string) => `${import.meta.env.BASE_URL}models/salad/${name}.glb`
type Placement = { position: [number, number, number]; rotation: [number, number, number]; scale: number }
const counts: Record<IngredientKind, number> = {lettuce:32,tomato:8,cucumber:9,chicken:7,corn:65,croutons:14,caesar:1}
function placements(kind: IngredientKind): Placement[] {
  if(kind === 'caesar') return [{position:[0,.065,0],rotation:[0,.2,0],scale:1}]
  return Array.from({length:counts[kind]},(_,i)=>{
    const a=i*2.399963+kind.length*.8+.12*Math.sin(i*7), r=Math.sqrt((i+.5)/counts[kind])*(kind==='lettuce'?.99:.88)
    const isLeaf=kind==='lettuce'
    return {position:[Math.cos(a)*r, isLeaf ? .90+.09*Math.sin(i*2) : 1.015+.13*(1-r)+.06*Math.sin(i*5), Math.sin(a)*r],
      rotation:[isLeaf?.18*Math.sin(i):.28*Math.sin(i*2),a,isLeaf?.18*Math.cos(i):.22*Math.cos(i*2)],
      scale:isLeaf?1.0+.25*Math.sin(i*3):.88+.15*Math.sin(i*3)}
  })
}
function Instances({part, locations, material,active,reduced,kind,hasLeaves}: {part: Mesh; locations: Placement[]; material: MeshStandardMaterial | MeshStandardMaterial[];active:boolean;reduced:boolean;kind:IngredientKind;hasLeaves:boolean}) {
  const ref=useRef<InstancedMesh>(null!)
  const foundation=useRef(hasLeaves?1:0)
  const elapsed=useRef(0), progress=useRef(locations.map(()=>0)), previous=useRef(active)
  const velocity=useRef(locations.map(()=>0))
  const scratch=useMemo(()=>({dummy:new Object3D(),matrix:new Matrix4()}),[])
  useLayoutEffect(()=>{ref.current.instanceMatrix.setUsage(35048);ref.current.frustumCulled=false;const mesh=ref.current;return()=>mesh.dispose()},[])
  useFrame((_,delta)=>{
    if(previous.current!==active){elapsed.current=0;previous.current=active}
    elapsed.current+=Math.min(delta,.05)
    foundation.current=approach(foundation.current,hasLeaves?1:0,delta*.5,reduced)
    const order={lettuce:.12,tomato:.32,cucumber:.4,chicken:.55,corn:.73,croutons:.87,caesar:1.05}[kind]
    locations.forEach((p,i)=>{
      const target=active&&elapsed.current>order+(i%9)*.024?1:0
      const step=reduced?[Number(active),0]:springStep(progress.current[i],velocity.current[i],target,delta)
      const t=progress.current[i]=step[0];velocity.current[i]=step[1]
      const travel=1-t
      scratch.dummy.position.set(p.position[0]+Math.sin(i*2.4)*travel*.22,p.position[1]-(kind==='lettuce'?0:(1-foundation.current)*(.68-.4*(p.position[0]**2+p.position[2]**2)))+(active?1.65:-.5)*travel,p.position[2]+Math.cos(i*2.4)*travel*.18)
      scratch.dummy.rotation.set(p.rotation[0]+travel*.48,p.rotation[1]+travel*Math.sin(i)*.4,p.rotation[2]+travel*.26)
      scratch.dummy.scale.setScalar(p.scale*Math.max(.001,active?Math.min(1,t*3):t))
      scratch.dummy.updateMatrix();scratch.matrix.multiplyMatrices(scratch.dummy.matrix,part.matrixWorld);ref.current.setMatrixAt(i,scratch.matrix)
    })
    ref.current.instanceMatrix.needsUpdate=true
  })
  // Geometry/material belong to useGLTF's shared cache; do not dispose while cached.
  return <instancedMesh ref={ref} args={[part.geometry,material,locations.length]} castShadow receiveShadow dispose={null}/>
}
export const Ingredient=memo(function Ingredient({kind,active=true,reduced=false,hasLeaves=true}: {kind: IngredientKind;active?:boolean;reduced?:boolean;hasLeaves?:boolean}) {
  const {scene}=useGLTF(assetUrl(kind),false)
  const ref=useRef<Group>(null!), opacity=useRef(reduced?1:0)
  const parts=useMemo(()=>{scene.updateMatrixWorld(true);const result:Mesh[]=[];scene.traverse(o=>{if((o as Mesh).isMesh)result.push(o as Mesh)});return result},[scene])
  // One texture per ingredient, not per seed/submesh. Cached GLB materials stay untouched.
  const surface=useMemo(()=>{
    const texture=surfaceTexture(kind), colorTexture=foodColorTexture(kind)
    const bySource=new Map<MeshStandardMaterial,MeshStandardMaterial>()
    const materials=parts.map(part=>{
      const get=(value:MeshStandardMaterial)=>{
        if(!bySource.has(value)){
          const m=value.clone();m.bumpMap=texture;m.map=colorTexture;if(kind==='chicken')m.color.set('#d7aa76')
          m.bumpScale=kind==='croutons'?.018:kind==='chicken'?.009:kind==='lettuce'?.003:.0015
          m.roughness=kind==='tomato'?.29:kind==='cucumber'?.34:kind==='corn'?.32:kind==='caesar'?.25:kind==='croutons'?.92:kind==='lettuce'?.57:.65;m.alphaHash=true;bySource.set(value,m)
        }
        return bySource.get(value)!
      }
      return Array.isArray(part.material)?part.material.map(v=>get(v as MeshStandardMaterial)):get(part.material as MeshStandardMaterial)
    })
    return {texture,colorTexture,materials,owned:[...bySource.values()]}
  },[parts,kind])
  useEffect(()=>()=>{surface.texture.dispose();surface.colorTexture.dispose();surface.owned.forEach(m=>m.dispose())},[surface])
  const locations=useMemo(()=>placements(kind),[kind])
  useFrame((_,delta)=>{
    opacity.current=approach(opacity.current,active?1:0,delta*(active?1:.35),reduced)
    ref.current.visible=opacity.current>0
    ref.current.position.y=0
    for(let i=0;i<surface.owned.length;i++)surface.owned[i].opacity=opacity.current
  })
  return <group ref={ref} name={kind}>{parts.map((p,i)=><Instances key={p.uuid} part={p} locations={locations} material={surface.materials[i]} active={active} reduced={reduced} kind={kind} hasLeaves={hasLeaves}/>)}</group>
})
export function Bowl() {
  const {scene}=useGLTF(assetUrl('bowl'),false)
  const copy=useMemo(()=>{const object=scene.clone(true);object.traverse(o=>{if((o as Mesh).isMesh){o.castShadow=true;o.receiveShadow=true}});return object},[scene])
  return <primitive object={copy} dispose={null}/>
}
