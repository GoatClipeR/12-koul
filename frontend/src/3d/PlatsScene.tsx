import type { MealState } from '../salad/mealScene'
import { ProductStudio, FoodPiece } from './ProductStudio'
import { Selections } from './SelectedFood'
import { PlatedProtein, Fries } from './PlatedFood'
const none:string[]=[]
export default function PlatsScene({meal,active=true,presented=true,view=0}:{meal:MealState;active?:boolean;presented?:boolean;view?:number}){
 const slots=meal.categories.plat?.slots
 return <ProductStudio active={active} presented={presented} view={view}><group rotation={[0,-.2,0]}><mesh receiveShadow><cylinderGeometry args={[1.7,1.55,.12,96]}/><meshStandardMaterial color="#ede2cb" roughness={.32}/></mesh><mesh position={[0,.07,0]} rotation={[Math.PI/2,0,0]}><torusGeometry args={[1.57,.055,16,96]}/><meshStandardMaterial color="#d4c3a5" roughness={.4}/></mesh>
 <Selections ids={slots?.protein??none}>{protein=><group position={[-.55,.3,0]}><PlatedProtein id={protein}/></group>}</Selections>
 <Selections ids={slots?.side??none}>{side=><group position={[.7,.2,.05]}>{side.includes('fries')?<Fries/>:Array.from({length:side.includes('rice')?100:18},(_,i)=><FoodPiece key={i} position={[Math.cos(i*2.4)*Math.sqrt(i/(side.includes('rice')?100:18))*.43,.18*(1-i/(side.includes('rice')?100:18)),Math.sin(i*2.4)*Math.sqrt(i/(side.includes('rice')?100:18))*.5]} scale={side.includes('rice')?[.035,.025,.07]:[.15,.1,.13]} color={side.includes('rice')?'#e7d8b0':side.includes('vegetables')?(i%2?'#69864b':'#bd753b'):'#d1a15a'} roughness={.68}/>)}</group>}</Selections>
 <Selections ids={slots?.sauce??none}>{id=><FoodPiece position={[0,.12,.98]} scale={[.45,.025,.28]} color={id.includes('barbecue')?'#713e25':'#b49367'} roughness={.25}/>}</Selections>
 </group></ProductStudio>
}
