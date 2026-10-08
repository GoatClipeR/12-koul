/** Frame-rate independent easing, with no object allocation. */
export function approach(current: number, target: number, delta: number, reduced=false) {
  if (reduced || Math.abs(target-current)<.001) return target
  return current+(target-current)*(1-Math.exp(-Math.min(delta,.1)*16))
}

/** Damped arrival with a small landing overshoot, integrated in bounded steps. */
export function springStep(value:number, velocity:number, target:number, delta:number): [number,number] {
  const duration=Math.min(delta,.05), steps=Math.max(1,Math.ceil(duration*120)), dt=duration/steps
  for(let i=0;i<steps;i++){
    velocity+=((target-value)*170-velocity*(target?20:27))*dt
    value+=velocity*dt
  }
  if(Math.abs(target-value)<.0005&&Math.abs(velocity)<.001)return [target,0]
  return [value,velocity]
}
