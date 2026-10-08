import { afterEach, expect, it, vi } from 'vitest'
import { fireEvent, render } from '@testing-library/react'
import { Atmosphere, atmosphereVideos } from './Atmosphere'
import { mealFeedback } from './mealFeedback'
import { springStep } from '../salad/motion'
import { chatResponse } from '../api/chatApi'
import fixtures from '../test-fixtures.json'

afterEach(()=>{delete atmosphereVideos.salad;delete atmosphereVideos.sandwich;vi.restoreAllMocks();vi.unstubAllGlobals()})

it('plays the supplied kitchen directly and preserves its video node across categories',()=>{
 const {container,rerender}=render(<Atmosphere category="salad"/>)
 const video=container.querySelector('video')!
 expect(video.src).toContain('/video/12koul-kitchen.mp4')
 expect(video.autoplay&&video.loop&&video.muted&&video.playsInline).toBe(true)
 fireEvent.playing(video)
 expect(video).toHaveAttribute('data-active','true')
 rerender(<Atmosphere category="sandwich"/>)
 expect(container.querySelector('video')).toBe(video)
 expect(container.querySelectorAll('video')).toHaveLength(1)
 fireEvent.error(video)
 expect(container.querySelector('video')).toBeNull()
 expect(container.querySelector('.atmosphere-veil')).not.toBeNull()
})

it('falls back from missing category footage to kitchen, then to the lighting layer',()=>{
 atmosphereVideos.salad='12koul-salad-atmosphere.mp4'
 const {container}=render(<Atmosphere category="salad"/>)
 let video=container.querySelector('video')!
 expect(video.src).toContain('/video/12koul-salad-atmosphere.mp4')
 expect(video.loop&&video.muted&&video.playsInline).toBe(true)
 fireEvent.error(video)
 video=container.querySelector('video')!
 expect(video.src).toContain('/video/12koul-kitchen.mp4')
 fireEvent.error(video)
 expect(container.querySelector('video')).toBeNull()
 expect(container.querySelector('.atmosphere-light')).not.toBeNull()
})

it('pauses outgoing footage and suspends all videos in a background tab',()=>{
 atmosphereVideos.sandwich='12koul-sandwich-atmosphere.mp4'
 const pause=vi.spyOn(HTMLMediaElement.prototype,'pause')
 const {container,rerender}=render(<Atmosphere category="salad"/>)
 rerender(<Atmosphere category="sandwich"/>)
 expect(pause).toHaveBeenCalled()
 expect(container.querySelectorAll('video')).toHaveLength(2)
 vi.spyOn(document,'hidden','get').mockReturnValue(true)
 fireEvent(document,new Event('visibilitychange'))
 expect(container.querySelector('video')).toBeNull()
})

it('does not request video playback with reduced motion',()=>{
 vi.stubGlobal('matchMedia',()=>({matches:true,addEventListener:vi.fn(),removeEventListener:vi.fn()}))
 const play=vi.spyOn(HTMLMediaElement.prototype,'play')
 const {container}=render(<Atmosphere category="plat"/>)
 expect(container.querySelector('video')).toBeNull()
 expect(play).not.toHaveBeenCalled()
})

it('announces only accepted state changes and clears gracefully on reset',()=>{
 const result=chatResponse.parse(fixtures.partial)
 expect(mealFeedback(null,result)).toContain('Tomate')
 expect(mealFeedback(result,result)).toBeNull()
 expect(mealFeedback(null,{...result,accepted:false})).toBeNull()
 expect(mealFeedback(result,null)).toBe('La table est à nouveau à vous.')
})

it('landing spring settles consistently across frame rates and reverses on removal',()=>{
 const simulate=(hz:number)=>{let value=0,velocity=0;for(let i=0;i<hz*2;i++)[value,velocity]=springStep(value,velocity,1,1/hz);return value}
 expect(simulate(30)).toBeCloseTo(1,3)
 expect(simulate(144)).toBeCloseTo(simulate(30),3)
 let value=.6,velocity=1
 for(let i=0;i<120;i++)[value,velocity]=springStep(value,velocity,0,1/60)
 expect(value).toBeCloseTo(0,3)
})
