import { useEffect, useRef, useState } from 'react'
import type { Category } from '../components/App'
import { useReducedMotion } from './useReducedMotion'

// Local, replaceable atmosphere only. These files never drive meal contents.
// Register category overrides only when those files are supplied.
// e.g. salad: '12koul-salad-atmosphere.mp4'
export const atmosphereVideos: Partial<Record<Category, string>> = {}
export const kitchenVideo = '12koul-kitchen.mp4'

function AtmosphereClip({ source, active, paused }: { source: string; active: boolean; paused: boolean }) {
  const video = useRef<HTMLVideoElement>(null)
  const [fallback, setFallback] = useState(0)
  const [ready, setReady] = useState(false)
  const failed = fallback > (source === kitchenVideo ? 0 : 1)
  const src = `${import.meta.env.BASE_URL}video/${fallback ? kitchenVideo : source}`
  useEffect(() => {
    const element = video.current
    if (!element) return
    let current = true
    if (active && !paused) void element.play().catch(() => { if(current)setReady(false) })
    else element.pause()
    return () => { current = false; element.pause() }
  }, [active, paused, src, fallback])
  if (failed || paused) return null
  return <video ref={video} className="atmosphere-video" data-active={active && ready} src={src}
    autoPlay={active} loop muted playsInline preload={active ? 'auto' : 'none'} tabIndex={-1}
    onPlaying={() => setReady(true)} onError={() => { setReady(false); setFallback(value => value + 1) }} />
}

export function Atmosphere({ category }: { category: Category }) {
  const reduced = useReducedMotion()
  const [hidden, setHidden] = useState(document.hidden)
  const source = atmosphereVideos[category] ?? kitchenVideo
  const [visited, setVisited] = useState<string[]>([source])
  useEffect(() => setVisited(previous => previous.includes(source) ? previous : [...previous, source]), [source])
  useEffect(() => {
    const update = () => setHidden(document.hidden)
    document.addEventListener('visibilitychange', update)
    return () => document.removeEventListener('visibilitychange', update)
  }, [])
  return <div className="atmosphere" data-category={category} aria-hidden="true">
    <div className="atmosphere-tones" />
    {visited.map(file => <AtmosphereClip key={file} source={file} active={file === source} paused={reduced || hidden} />)}
    <div className="atmosphere-veil" />
    <div className="atmosphere-light atmosphere-light-one" />
    <div className="atmosphere-light atmosphere-light-two" />
    <div className="atmosphere-table" />
  </div>
}
