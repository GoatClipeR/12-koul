import { useEffect, useMemo } from 'react'
import { Color, Float32BufferAttribute, SphereGeometry } from 'three'
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js'
import { foodColorTexture, surfaceTexture } from '../salad/surface'
export function PlatedProtein({id}:{id:string}){
 const cooked=useMemo(()=>{
  const geometry=new SphereGeometry(1,72,48),positions=geometry.attributes.position,colors=[]
  const dark=id.includes('steak'),base=new Color(dark?'#885031':'#c08a46'),sear=new Color('#412319'),edge=new Color('#99572b')
  for(let i=0;i<positions.count;i++){
   const x=positions.getX(i),y=positions.getY(i),z=positions.getZ(i)
   const uneven=.018*Math.sin(x*34+z*11)*Math.cos(z*28-y*7)
   positions.setXYZ(i,x*(.9+.17*z)+uneven,y<-.25?-.25+(y+.25)*.22:y+uneven,z+uneven)
   const grill=Math.pow(Math.max(0,Math.cos((z+x*.32)*25)),14)*Math.max(0,y)*.88
   const toasted=Math.pow(1-Math.max(0,y),2)*.45
   const c=base.clone().lerp(edge,toasted).lerp(sear,grill).multiplyScalar(.9+.1*Math.sin(x*60+z*47))
   colors.push(c.r,c.g,c.b)
  }
  geometry.setAttribute('color',new Float32BufferAttribute(colors,3));geometry.computeVertexNormals()
  return {geometry,bump:surfaceTexture('chicken'),map:foodColorTexture('chicken')}
 },[id])
 useEffect(()=>()=>{cooked.geometry.dispose();cooked.bump.dispose();cooked.map.dispose()},[cooked])
 return <mesh position={[0,-.02,0]} scale={[.67,.25,.87]} rotation={[0,.2,0]} geometry={cooked.geometry} castShadow receiveShadow><meshStandardMaterial vertexColors map={cooked.map} bumpMap={cooked.bump} bumpScale={.015} roughness={.62}/></mesh>
}
export function Fries(){
 const assets=useMemo(()=>({geometry:new RoundedBoxGeometry(.085,.075,.67,2,.013),bump:surfaceTexture('croutons')}),[])
 useEffect(()=>()=>{assets.geometry.dispose();assets.bump.dispose()},[assets])
 return <>{Array.from({length:26},(_,i)=><mesh key={i} geometry={assets.geometry} position={[(i%4)*.13-.2,Math.floor(i/4)*.048,(i%5)*.13-.35]} rotation={[.06*Math.sin(i),i*.72,.12]} castShadow receiveShadow><meshStandardMaterial color={i%3===0?'#ba7f2c':i%2?'#d7a546':'#c99639'} roughness={.76} bumpMap={assets.bump} bumpScale={.012}/></mesh>)}</>
}
