import { useMemo } from 'react'
import { Vector2 } from 'three'
import { ProductStudio } from './ProductStudio'
import { Selections } from './SelectedFood'
export default function DrinkScene({id,active,presented=true,view}:{id?:string;active?:boolean;presented?:boolean;view?:number}){
 const profile=useMemo(()=>[[0,0],[.47,0],[.5,.05],[.61,1.9],[.59,1.93],[.56,1.9],[.46,.12],[0,.12]].map(p=>new Vector2(...p)),[])

 return <ProductStudio active={active} presented={presented} view={view}><group position={[0,0,0]}>
  <mesh castShadow receiveShadow><cylinderGeometry args={[.88,.88,.055,64]}/><meshStandardMaterial color="#8e6645" roughness={.85}/></mesh>
  <mesh position={[0,.045,0]}><latheGeometry args={[profile,96]}/><meshPhysicalMaterial color="#fff9ef" roughness={.07} transmission={.94} thickness={.12} ior={1.46} transparent opacity={.52}/></mesh>
  <Selections ids={id?[id]:[]}>{drink=><Liquid id={drink}/>}</Selections>
 </group></ProductStudio>
}

function Liquid({id}:{id:string}){
 const color=id?.includes('coca')?'#351509':id?.includes('water')||id?.includes('sprite')?'#e0e9d5':id?.includes('lemon')?'#e9d589':id?.includes('apple')?'#bd9235':id?.includes('mango')?'#e9a332':'#eb921b'
 return <><mesh position={[0,.88,0]}><cylinderGeometry args={[.553,.458,1.48,64]}/><meshPhysicalMaterial color={color} roughness={.25} metalness={0} clearcoat={.5} transmission={id?.includes('water')?.8:.08} thickness={.5}/></mesh>
  {Array.from({length:5},(_,i)=><mesh key={i} position={[Math.sin(i*2.4)*.32,1.62,Math.cos(i*2.4)*.3]} rotation={[i*.3,i,.2]}><boxGeometry args={[.24,.23,.24]}/><meshPhysicalMaterial color="#fff9eb" roughness={.12} transmission={.85} thickness={.4} transparent opacity={.65}/></mesh>)}
  </>
}
