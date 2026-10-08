import { useRef, type ReactNode } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { Group, PerspectiveCamera, DirectionalLight, Color } from 'three'
import { useReducedMotion } from '../experience/useReducedMotion'

/** One directed arrival/exit per selection; never an idle floating animation. */
export function SceneMotion({ presented, children }: { presented: boolean; children: ReactNode }) {
  const group = useRef<Group>(null!)
  const progress = useRef(0)
  const reduced = useReducedMotion()
  const { camera } = useThree()
  useFrame((_, delta) => {
    const target = presented ? 1 : 0
    progress.current = reduced ? target : progress.current + (target - progress.current) * (1 - Math.exp(-Math.min(delta, .05) * 5.5))
    const remaining = 1 - progress.current
    group.current.position.set(remaining * (presented ? .5 : -.6), -.18 * remaining, -1.6 * remaining)
    group.current.rotation.y = remaining * (presented ? -.24 : .24)
    group.current.scale.setScalar(1 - remaining * .13)
    const lens = camera as PerspectiveCamera
    const fov = 32 + remaining * 4
    if (Math.abs(lens.fov - fov) > .002) { lens.fov = fov; lens.updateProjectionMatrix() }
  })
  return <group ref={group}>{children}</group>
}

const warm = new Color('#ffe4bf'), settled = new Color('#fff0d9')
export function ArrivalLight({ presented }: { presented: boolean }) {
  const light = useRef<DirectionalLight>(null!)
  const progress = useRef(0)
  const reduced = useReducedMotion()
  useFrame((_, delta) => {
    progress.current = reduced ? Number(presented) : progress.current + (Number(presented) - progress.current) * (1 - Math.exp(-delta * 3))
    light.current.intensity = .25 + progress.current * .7
    light.current.color.copy(warm).lerp(settled, progress.current)
  })
  return <directionalLight ref={light} position={[-3, 3, -2]} />
}
