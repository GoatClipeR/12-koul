import { expect,it,vi } from 'vitest'
import { render,screen,waitFor } from '@testing-library/react'
import { MealScene } from './MealScene'
vi.mock('../salad/SaladScene',()=>({default:()=> <div data-testid="salad-canvas"/>}))
vi.mock('./SandwichScene',()=>({default:()=> <div data-testid="sandwich-canvas"/>}))
vi.mock('./PlatsScene',()=>({default:()=> <div data-testid="plat-canvas"/>}))
it('keeps visited canvas roots stable across category switches and reset',async()=>{
 const meal={active_category:null,categories:{}}
 const view=render(<MealScene meal={meal} category="salad"/>);const first=await screen.findByTestId('salad-canvas')
 view.rerender(<MealScene meal={meal} category="sandwich"/>);await screen.findByTestId('sandwich-canvas');expect(first.isConnected).toBe(true);expect(first.closest('.category-stage')).toHaveAttribute('aria-hidden','true');await waitFor(()=>expect(first).not.toBeVisible(),{timeout:2000})
 view.rerender(<MealScene meal={meal} category="plat"/>);await screen.findByTestId('plat-canvas');expect(first.isConnected).toBe(true)
 view.rerender(<MealScene meal={meal} category="salad"/>);await waitFor(()=>expect(first).toBeVisible());expect(screen.getByTestId('salad-canvas')).toBe(first)
 view.unmount()
})
