import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { projectMeal, demoMeal, ingredientAssets } from '../src/salad/mealScene.ts'
test('accepted state snapshots drive additions, removals, size and clear without mutation',()=>{
 const original=JSON.stringify(demoMeal), state=structuredClone(demoMeal)
 assert.equal(projectMeal(state).ingredients.length,7)
 state.categories.salad.slots.ingredient=state.categories.salad.slots.ingredient.filter(id=>!id.endsWith('tomato'))
 assert.equal(projectMeal(state).ingredients.includes('tomato'),false)
 state.categories.salad.slots.ingredient.push('salad.ingredient.tomato')
 assert.equal(projectMeal(state).ingredients.includes('tomato'),true)
 state.categories.salad.size='small';assert.equal(projectMeal(state).scale,.82)
 assert.equal(projectMeal({active_category:null,categories:{}}).visible,false)
 assert.equal(JSON.stringify(demoMeal),original)
})
test('unknown visual assets are reported rather than invented',()=>{
 const state=structuredClone(demoMeal);state.categories.salad.slots.base.push('salad.base.arugula')
 assert.deepEqual(projectMeal(state).unmapped,['salad.base.arugula'])
 const menu=JSON.parse(readFileSync(new URL('../../backend/app/data/menu.json',import.meta.url)))
 for(const id of Object.keys(ingredientAssets)) assert.ok(menu.items.some(item=>item.id===id))
})
test('all eight GLBs are self-contained valid containers within slice budget',()=>{
 const dir=new URL('../public/models/salad/',import.meta.url)
 const files=readdirSync(dir).filter(f=>f.endsWith('.glb'));assert.equal(files.length,8)
 let bytes=0,triangles=0,visibleTriangles=0
 const counts={bowl:1,lettuce:32,tomato:8,cucumber:9,chicken:7,corn:65,croutons:14,caesar:1}
 for(const file of files){
  const b=readFileSync(new URL(file,dir));bytes+=b.length
  assert.equal(b.readUInt32LE(0),0x46546c67);assert.equal(b.readUInt32LE(4),2);assert.equal(b.readUInt32LE(8),b.length)
  const gltf=JSON.parse(b.subarray(20,20+b.readUInt32LE(12)).toString())
  assert.ok(gltf.buffers.every(buf=>!buf.uri))
  for(const mesh of gltf.meshes)for(const primitive of mesh.primitives){
   const n=gltf.accessors[primitive.indices ?? primitive.attributes.POSITION].count/3
   triangles+=n;visibleTriangles+=n*counts[file.slice(0,-4)]
  }
 }
 assert.ok(bytes<500_000);assert.ok(triangles<80_000);assert.ok(visibleTriangles<80_000)
 console.log({assetBytes:bytes,uniqueAssetTriangles:triangles,visibleTriangles})
})

test('transition reverses smoothly, converges and respects reduced motion', async()=>{
 const {approach}=await import('../src/salad/motion.ts')
 let value=0
 for(let i=0;i<40;i++){const next=approach(value,1,1/60);assert.ok(next>=value && next<=1);value=next}
 assert.equal(value,1)
 const fading=approach(value,0,1/60);assert.ok(fading>0 && fading<1)
 assert.ok(approach(fading,1,1/60)>fading)
 assert.equal(approach(.4,0,1/60,true),0)
 assert.equal(approach(.4,1,1/60,true),1)
})
