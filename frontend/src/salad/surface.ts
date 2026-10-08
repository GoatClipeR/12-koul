import { CanvasTexture, RepeatWrapping } from 'three'
/** Seeded microstructure: no network image, no random changes between renders. */
export function surfaceTexture(kind: string) {
  const canvas=document.createElement('canvas');canvas.width=128;canvas.height=128
  const context=canvas.getContext('2d')!, pixels=context.createImageData(128,128)
  let seed=751
  for(let i=0;i<128*128;i++){
    seed=(Math.imul(seed,1664525)+1013904223)>>>0
    const grain=kind==='chicken'?120+22*Math.sin(i%128*.8)+(seed>>>27):kind==='croutons'?75+(seed>>>24)*.5:110+(seed>>>25)
    pixels.data.set([grain,grain,grain,255],i*4)
  }
  context.putImageData(pixels,0,0)
  const texture=new CanvasTexture(canvas);texture.wrapS=texture.wrapT=RepeatWrapping;texture.repeat.set(3,3)
  return texture
}
/** Neutral albedo variation: keeps each GLB's authored color and adds organic detail. */
export function foodColorTexture(kind:string){
 const canvas=document.createElement('canvas');canvas.width=canvas.height=256
 const ctx=canvas.getContext('2d')!, pixels=ctx.createImageData(256,256)
 let seed=7343
 for(let y=0;y<256;y++)for(let x=0;x<256;x++){
  seed=(Math.imul(seed,1664525)+1013904223)>>>0
  const n=(seed>>>24)/255
  const clouds=(Math.sin(x*.11+Math.sin(y*.07)*2)+Math.sin(y*.15+x*.035))*.5
  let shade=240+clouds*10-n*12
  if(kind==='chicken')shade=205+clouds*20-n*28
  if(kind==='croutons')shade=n>.83?145:230+clouds*10-n*30
  if(kind==='lettuce')shade=238+clouds*12-Math.pow(Math.max(0,Math.cos(x*.22+y*.09)),18)*17
  pixels.data.set([shade,shade,shade,255],(y*256+x)*4)
 }
 ctx.putImageData(pixels,0,0)
 const texture=new CanvasTexture(canvas);texture.wrapS=texture.wrapT=RepeatWrapping;texture.repeat.set(2,2)
 return texture
}
