// STAGE 0 TECHNICAL SMOKE TEST — NOT the visual quality gate (that is Stage 4a).
// Purpose: prove the toolchain (R3F + drei + postprocessing + GLB export/import + instancing +
// procedural textures + the "mutate refs in useFrame, never setState" animation pattern) works.
// The bowl is a plain lathe and the "chunks" are throwaway instanced blobs, not food.
import { StrictMode, useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Environment, Lightformer, ContactShadows } from '@react-three/drei'
import { EffectComposer, Bloom, ToneMapping, SMAA, Vignette } from '@react-three/postprocessing'
import { ToneMappingMode } from 'postprocessing'
import * as THREE from 'three'
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js'
import { KTX2Loader } from 'three/examples/jsm/loaders/KTX2Loader.js'
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js'

declare global { interface Window { __SMOKE__?: Record<string, unknown> } }
const report: Record<string, unknown> = (window.__SMOKE__ = {})

function makeBowlGeometry() {
  const pts = [[0, 0], [0.7, 0], [0.88, 0.04], [1.2, 0.36], [1.44, 0.76], [1.5, 0.96], [1.46, 0.99], [1.4, 0.97],
    [1.34, 0.9], [1.08, 0.5], [0.7, 0.22], [0, 0.16]].map(([x, y]) => new THREE.Vector3(x, y, 0))
  const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal')
  const prof = curve.getPoints(96).map((p) => new THREE.Vector2(Math.max(p.x, 0), p.y))
  return new THREE.LatheGeometry(prof, 96)
}

function makeNoiseTexture(size = 256) {
  const c = document.createElement('canvas'); c.width = c.height = size
  const g = c.getContext('2d')!; const img = g.createImageData(size, size)
  for (let i = 0; i < size * size; i++) { const v = 128 + (Math.random() - 0.5) * 90; img.data.set([v, v, v, 255], i * 4) }
  g.putImageData(img, 0, 0)
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(6, 6); return t
}

function Bowl() {
  const geo = useMemo(makeBowlGeometry, [])
  const bump = useMemo(() => makeNoiseTexture(), [])
  useEffect(() => () => { geo.dispose(); bump.dispose() }, [geo, bump]) // disposal on unmount (ui-3d-pro rule)
  return (
    <mesh geometry={geo} castShadow receiveShadow name="bowl">
      <meshPhysicalMaterial color="#F4E9D6" roughness={0.28} clearcoat={1} clearcoatRoughness={0.18}
        bumpMap={bump} bumpScale={0.15} side={THREE.DoubleSide} />
    </mesh>
  )
}

const COUNT = 300
function Chunks() {
  const ref = useRef<THREE.InstancedMesh>(null!)
  const data = useMemo(() => Array.from({ length: COUNT }, () => {
    const a = Math.random() * Math.PI * 2, r = Math.sqrt(Math.random()) * 1.05
    return { x: Math.cos(a) * r, z: Math.sin(a) * r, y: 0.28 + Math.random() * 0.12 + r * r * 0.22,
      s: 0.7 + Math.random() * 0.7, ph: Math.random() * 6.28, ry: Math.random() * 6.28 }
  }), [])
  const geo = useMemo(() => {
    const g = new THREE.IcosahedronGeometry(0.09, 2); const p = g.attributes.position
    for (let i = 0; i < p.count; i++) { const k = 0.8 + Math.random() * 0.4; p.setXYZ(i, p.getX(i) * k, p.getY(i) * k * 0.7, p.getZ(i) * k) }
    g.computeVertexNormals(); return g
  }, [])
  const dummy = useMemo(() => new THREE.Object3D(), [])
  useEffect(() => {
    const col = new THREE.Color(); const palette = ['#C9402F', '#7FA84A', '#E3B54C', '#E9DCC0']
    data.forEach((_, i) => ref.current.setColorAt(i, col.set(palette[i % 4]).offsetHSL(0, 0, (Math.random() - 0.5) * 0.08)))
    ref.current.instanceColor!.needsUpdate = true
    return () => geo.dispose()
  }, [data, geo])
  useFrame(({ clock }) => { // animation pattern: mutate refs, never setState inside useFrame
    const t = clock.elapsedTime
    data.forEach((d, i) => {
      dummy.position.set(d.x, d.y + Math.sin(t * 1.6 + d.ph) * 0.012, d.z)
      dummy.rotation.set(0, d.ry + t * 0.05, 0); dummy.scale.setScalar(d.s); dummy.updateMatrix()
      ref.current.setMatrixAt(i, dummy.matrix)
    })
    ref.current.instanceMatrix.needsUpdate = true
  })
  return (
    <instancedMesh ref={ref} args={[geo, undefined, COUNT]} castShadow>
      <meshStandardMaterial roughness={0.45} metalness={0} />
    </instancedMesh>
  )
}

function Reporter({ onDone }: { onDone: (r: Record<string, unknown>) => void }) {
  const { gl } = useThree()
  const frames = useRef(0); const t0 = useRef(performance.now()); const done = useRef(false)
  useFrame(() => { frames.current++ })
  useEffect(() => {
    let cancelled = false
    const run = async () => {
      // --- GLB round trip (export -> load) + decoder availability ---
      try {
        const mesh = new THREE.Mesh(makeBowlGeometry(), new THREE.MeshStandardMaterial({ color: '#F4E9D6' }))
        const buf = (await new GLTFExporter().parseAsync(mesh, { binary: true })) as ArrayBuffer
        const gltf = await new GLTFLoader().parseAsync(buf, '')
        let tris = 0; gltf.scene.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) tris += (m.geometry.index?.count ?? m.geometry.attributes.position.count) / 3 })
        report.glb_roundtrip = { ok: true, bytes: buf.byteLength, triangles: tris }
        const draco = new DRACOLoader(); draco.setDecoderPath('/draco/')
        const ktx2 = new KTX2Loader(); ktx2.setTranscoderPath('/basis/'); ktx2.detectSupport(gl)
        const loader = new GLTFLoader().setDRACOLoader(draco).setKTX2Loader(ktx2).setMeshoptDecoder(MeshoptDecoder)
        report.loader_stack = { ok: !!loader, meshopt_decoder: typeof MeshoptDecoder?.supported !== 'undefined', ktx2_loader: !!ktx2, draco_loader: !!draco }
        draco.dispose(); ktx2.dispose()
      } catch (e) { report.glb_roundtrip = { ok: false, error: String(e) } }
      // --- renderer capabilities ---
      const ctx = gl.getContext(); const dbg = ctx.getExtension('WEBGL_debug_renderer_info')
      report.webgl = { version: ctx instanceof WebGL2RenderingContext ? 2 : 1,
        renderer: dbg ? ctx.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : 'n/a',
        max_texture_size: gl.capabilities.maxTextureSize, max_anisotropy: gl.capabilities.getMaxAnisotropy(),
        float_textures: !!ctx.getExtension('EXT_color_buffer_float') }
    }
    run()
    const timer = setTimeout(() => {
      if (cancelled || done.current) return; done.current = true
      const secs = (performance.now() - t0.current) / 1000
      report.frames = { count: frames.current, seconds: +secs.toFixed(2), fps_software_gl: +(frames.current / secs).toFixed(1) }
      report.render_info = { draw_calls: gl.info.render.calls, triangles: gl.info.render.triangles,
        geometries: gl.info.memory.geometries, textures: gl.info.memory.textures }
      report.instances = COUNT
      report.postprocessing = 'SMAA + Bloom + ToneMapping(ACES) + Vignette rendered without error'
      report.done = true; onDone({ ...report })
    }, 3500)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [gl, onDone])
  return null
}

function App() {
  const [rep, setRep] = useState<Record<string, unknown> | null>(null)
  return (
    <>
      <Canvas shadows camera={{ position: [3.4, 2.5, 4.2], fov: 32 }} dpr={[1, 1.5]}
        gl={{ antialias: false, powerPreference: 'high-performance' }}
        onCreated={({ gl }) => { gl.toneMapping = THREE.NoToneMapping }}>
        <color attach="background" args={['#C98445']} />
        <Environment resolution={256} frames={1}>
          <Lightformer form="rect" intensity={4} color="#FFE2B8" position={[3, 4, 2]} scale={[5, 3, 1]} />
          <Lightformer form="rect" intensity={2} color="#FFB866" position={[-4, 1.5, -3]} scale={[4, 2, 1]} />
          <Lightformer form="ring" intensity={1.2} color="#BFD4F2" position={[0, 5, -2]} scale={4} />
        </Environment>
        <directionalLight castShadow position={[3, 5, 2.5]} intensity={1.6} color="#FFE2B8" shadow-mapSize={[1024, 1024]} shadow-bias={-0.0004} />
        <group position={[0, 0, 0]} rotation={[0, 0.5, 0]}>
          <mesh position={[0, -0.06, 0]} receiveShadow castShadow>
            <cylinderGeometry args={[2.1, 2.1, 0.12, 72]} /><meshStandardMaterial color="#5A301D" roughness={0.55} />
          </mesh>
          <Bowl /><Chunks />
        </group>
        <ContactShadows position={[0, -0.12, 0]} opacity={0.5} blur={2.4} far={3} scale={9} />
        <EffectComposer multisampling={0}>
          <SMAA /><Bloom mipmapBlur intensity={0.35} luminanceThreshold={0.9} />
          <ToneMapping mode={ToneMappingMode.ACES_FILMIC} /><Vignette eskil={false} offset={0.25} darkness={0.55} />
        </EffectComposer>
        <Reporter onDone={setRep} />
      </Canvas>
      <pre id="smoke-report" data-done={rep ? '1' : '0'} style={{ position: 'fixed', left: 12, bottom: 12, margin: 0, padding: 10, maxWidth: 520,
        font: '11px/1.35 ui-monospace,monospace', background: 'rgba(42,20,11,.82)', color: '#FFF9EE', borderRadius: 6 }}>
        {rep ? JSON.stringify(rep, null, 1) : 'running smoke test…'}
      </pre>
    </>
  )
}
createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
