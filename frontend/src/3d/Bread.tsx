import { useEffect, useMemo } from 'react'
import { useTexture } from '@react-three/drei'
import { RepeatWrapping, SphereGeometry, SRGBColorSpace } from 'three'
export function Bread({top,wholeWheat}:{top?:boolean;wholeWheat:boolean}){
 const source=useTexture(`${import.meta.env.BASE_URL}images/bread-crust.png`)
 const texture=useMemo(()=>{const t=source.clone();t.wrapS=t.wrapT=RepeatWrapping;t.repeat.set(2,1);t.colorSpace=SRGBColorSpace;t.needsUpdate=true;return t},[source])
 const geometry=useMemo(()=>{
  const g=new SphereGeometry(1,96,64),p=g.attributes.position
  for(let i=0;i<p.count;i++){
   const x=p.getX(i),y=p.getY(i),z=p.getZ(i)
   g.attributes.uv.setXY(i,(x+1)*.5,(z+1)*.5)
   const crust=.008*Math.sin(x*42+z*17)*Math.sin(y*33-z*29)
   let score=0
   if(top&&y>.2)for(let j=0;j<5;j++){const distance=x-(-.65+j*.32)+z*.12;score+=Math.exp(-distance*distance/.0009)*.045*y}
   p.setXYZ(i,x*(1+crust),y*(1+crust)-score,z*(1+crust))
  }
  g.computeVertexNormals();return g
 },[top])
 useEffect(()=>()=>{texture.dispose();geometry.dispose()},[texture,geometry])
 return <mesh geometry={geometry} position={top?[0,.89,-.03]:[0,.24,0]} rotation={top?[-.1,0,.025]:[0,0,0]} scale={top?[1.37,.32,.54]:[1.35,.2,.51]} castShadow receiveShadow><meshStandardMaterial map={texture} bumpMap={texture} bumpScale={.025} color={wholeWheat?'#bd9569':'#fff3df'} roughness={.86}/></mesh>
}
