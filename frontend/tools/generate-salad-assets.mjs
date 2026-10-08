// Original procedural assets, confined to the seven-ingredient vertical slice.
// Run from frontend: node tools/generate-salad-assets.mjs
import * as T from 'three'
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js'
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js'
import { mkdir, writeFile } from 'node:fs/promises'
globalThis.FileReader = class {
  readAsArrayBuffer(blob) { blob.arrayBuffer().then(v => { this.result=v; this.onloadend?.() }) }
  readAsDataURL(blob) { blob.arrayBuffer().then(v => { this.result=`data:${blob.type};base64,${Buffer.from(v).toString('base64')}`; this.onloadend?.() }) }
}
const out = new URL('../public/models/salad/', import.meta.url)
await mkdir(out, { recursive: true })
const mat = (color, roughness=.55, extra={}) => new T.MeshStandardMaterial({color, roughness, ...extra})
function part(group, geometry, material, position=[0,0,0], scale=[1,1,1], rotation=[0,0,0]) {
  const mesh=new T.Mesh(geometry,material); mesh.position.set(...position); mesh.scale.set(...scale); mesh.rotation.set(...rotation); group.add(mesh); return mesh
}
function irregular(g, amount) {
 const a=g.attributes.position
 for(let i=0;i<a.count;i++){const x=a.getX(i),y=a.getY(i),z=a.getZ(i);const n=1+amount*Math.sin(x*47+y*31+z*29)*Math.cos(z*37-x*19);a.setXYZ(i,x*n,y*n,z*n)}
 g.computeVertexNormals();return g
}
async function save(name, group){
 const data=await new GLTFExporter().parseAsync(group,{binary:true});await writeFile(new URL(`${name}.glb`,out),Buffer.from(data))
 console.log(name, data.byteLength, 'bytes')
 group.traverse(o=>{if(o.isMesh){o.geometry.dispose();o.material.dispose()}})
}
let g=new T.Group()
const profile=[[0,.06],[.65,.06],[.84,.12],[1.10,.39],[1.34,.77],[1.43,1.00],[1.43,1.04],[1.39,1.06],[1.35,1.02],[1.28,.80],[1.04,.43],[.77,.22],[0,.20]].map(p=>new T.Vector2(...p))
part(g,new T.LatheGeometry(profile,96),mat('#ece1c9',.3));
part(g,new T.TorusGeometry(1.40,.013,8,96),mat('#4d2514',.55),[0,1.068,0],[1,1,1],[Math.PI/2,0,0]);await save('bowl',g)
g=new T.Group();let leaf=new T.PlaneGeometry(.55,.80,16,22);const p=leaf.attributes.position, colors=[]
for(let i=0;i<p.count;i++){let x=p.getX(i),v=(p.getY(i)+.4)/.8;const width=Math.sin(v*Math.PI)*.8+.2;x*=width;const edge=Math.abs(x)/.275;let z=.08*Math.sin(v*3.14)+.045*edge*edge*Math.sin(v*28)+.035*Math.sin(x*28);p.setXYZ(i,x,z,p.getY(i));const c=new T.Color().setHSL(.235+v*.035,.48,.23+v*.13+edge*.04);colors.push(c.r,c.g,c.b)}
leaf.setAttribute('color',new T.Float32BufferAttribute(colors,3));leaf.computeVertexNormals();part(g,leaf,mat('#ffffff',.68,{vertexColors:true,side:T.DoubleSide}));
part(g,new T.CylinderGeometry(.006,.012,.67,5),mat('#99ad52'),[0,.045,0],[1,1,1],[Math.PI/2,0,0]);await save('lettuce',g)
g=new T.Group();const wedge=new T.Shape();wedge.moveTo(0,0);wedge.absarc(0,0,.29,0,Math.PI*.72,false);wedge.lineTo(0,0)
part(g,new T.ExtrudeGeometry(wedge,{depth:.075,bevelEnabled:true,bevelThickness:.015,bevelSize:.012,bevelSegments:2,steps:1,curveSegments:18}),mat('#a93928',.42),[-.05,.02,0],[1,1,1],[-Math.PI/2,0,0]);
const flesh=new T.Shape();flesh.moveTo(.025,.025);flesh.absarc(0,0,.245,.12,Math.PI*.68,false);flesh.lineTo(.025,.025)
part(g,new T.ShapeGeometry(flesh,18),mat('#d45a40',.5,{side:T.DoubleSide}),[-.05,.111,0],[1,1,1],[-Math.PI/2,0,0]);
for(let i=0;i<7;i++){let a=.25+i*.25;part(g,new T.SphereGeometry(.018,8,6),mat('#edc66e',.33),[Math.cos(a)*.18-.05,.116,-Math.sin(a)*.18],[.5,.25,1.3],[0,-a,0])}await save('tomato',g)
g=new T.Group();part(g,new T.CylinderGeometry(.23,.23,.07,40),mat('#426337',.45));part(g,new T.CylinderGeometry(.207,.207,.072,40),mat('#c3d18a',.4));
for(let i=0;i<9;i++){let a=i*2.399;part(g,new T.SphereGeometry(.019,8,6),mat('#e6e4ba',.4),[Math.cos(a)*.10,.039,Math.sin(a)*.10],[.55,.22,1.6],[0,-a,0])}await save('cucumber',g)
g=new T.Group();const chicken=irregular(new T.CapsuleGeometry(.11,.34,5,12,8),.07)
const cp=chicken.attributes.position, cooked=[]
for(let i=0;i<cp.count;i++){
 const x=cp.getX(i),y=cp.getY(i),z=cp.getZ(i)
 cp.setX(i,x*(.85+.2*Math.sin(y*10))+.016*Math.sin(y*17))
 const sear=Math.pow(Math.max(0,Math.cos(y*57+x*9)),2)*.82
 const c=new T.Color('#ceaa74').lerp(new T.Color('#623921'),sear);cooked.push(c.r,c.g,c.b)
}
chicken.setAttribute('color',new T.Float32BufferAttribute(cooked,3));chicken.computeVertexNormals()
part(g,chicken,mat('#ffffff',.68,{vertexColors:true}),[0,0,0],[1,1,.7],[0,0,Math.PI/2]);await save('chicken',g)
g=new T.Group();part(g,new T.SphereGeometry(.055,10,8),mat('#e6b83c',.35),[0,0,0],[1,.8,1.35]);await save('corn',g)
g=new T.Group();part(g,irregular(new RoundedBoxGeometry(.16,.13,.17,2,.018),.06),mat('#b87b39',.9));
for(let i=0;i<10;i++)part(g,new T.SphereGeometry(.009,5,4),mat('#e0b576',1),[Math.sin(i*12)*.058,.068,Math.cos(i*7)*.063],[1,.22,1]);await save('croutons',g)
g=new T.Group();
// Short ribbons avoid a single hovering zigzag across unrelated ingredients.
for(let j=0;j<4;j++){
 const points=Array.from({length:16},(_,i)=>{const t=i/15;return new T.Vector3(-.65+t*.40+j*.29,1.065+.025*Math.sin(t*Math.PI),-.48+j*.29+.04*Math.sin(t*4))})
 const ribbon=new T.TubeGeometry(new T.CatmullRomCurve3(points),24,.019,7,false)
 ribbon.scale(1,.997,1)
 part(g,ribbon,mat('#e4d9ba',.42))
}
await save('caesar',g)
