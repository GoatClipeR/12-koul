import type { MealState } from '../salad/mealScene'
import { ProductStudio, FoodPiece } from './ProductStudio'
import { AssetPiece, Selections } from './SelectedFood'
import { Bread } from './Bread'
const none:string[]=[]
export default function SandwichScene({meal,active=true,presented=true,view=0}:{meal:MealState;active?:boolean;presented?:boolean;view?:number}){
 const slots=meal.categories.sandwich?.slots
 return <ProductStudio active={active} presented={presented} view={view}><group rotation={[0,-.35,0]}>
 <mesh position={[0,0,0]} receiveShadow><cylinderGeometry args={[1.75,1.68,.07,96]}/><meshStandardMaterial color="#e6d7ba" roughness={.38}/></mesh>
 <Selections ids={slots?.bread??none}>{bread=><group><Bread wholeWheat={bread.includes('whole_wheat')}/><Bread top wholeWheat={bread.includes('whole_wheat')}/></group>}</Selections>
 <Selections ids={slots?.protein??none}>{protein=><>{Array.from({length:6},(_,i)=>protein.includes('grilled_chicken')?<AssetPiece key={i} kind="chicken" position={[-.88+i*.34,.45,0]} rotation={[0,1.1,0]} scale={1.7}/>:<FoodPiece key={i} position={[-.85+i*.34,.45,0]} scale={[.25,.11,.45]} rotation={[0,.1*i,0]} color={protein.includes('beef')?'#75482e':protein.includes('tuna')?'#c58d7b':'#bb7e43'} roughness={.88}/>)}</>}</Selections>
 <Selections ids={slots?.vegetable??none}>{(id,i)=><>{Array.from({length:id.includes('lettuce')?12:6},(_,j)=><group key={j} position={[-1+(j%6)*.4,.59+i*.025,(j>5?.2:-.14)]}>{id.includes('lettuce')?<AssetPiece kind="lettuce" position={[0,0,0]} rotation={[.1,j*.7,.05]} scale={1.12}/>:id.includes('tomato')||id.includes('cucumber')?<AssetPiece kind={id.includes('tomato')?'tomato':'cucumber'} position={[0,0,0]} rotation={[0,j*.7,0]} scale={1.05}/>:<FoodPiece position={[0,0,0]} scale={[.24,.025,.32]} color={id.includes('onion')?'#d9b6cb':'#88933d'} roughness={.38}/>}</group>)}</>}</Selections>
 <Selections ids={slots?.cheese??none}>{id=><mesh position={[0,.7,0]} rotation={[0,.1,.025]} castShadow><boxGeometry args={[2.05,.035,.86]}/><meshStandardMaterial color={id.includes('cheddar')?'#edb93e':'#eddfb8'} roughness={.4}/></mesh>}</Selections>
 <Selections ids={slots?.sauce??none}>{id=><FoodPiece position={[0,.73,0]} scale={[1.1,.025,.35]} color={id.includes('algerian')?'#d69864':'#edce9a'} roughness={.23}/>}</Selections>
 <Selections ids={slots?.extra??none}>{(id,i)=><FoodPiece position={[-.5+i*.5,.78,0]} scale={[.35,.05,.37]} color={id.includes('avocado')?'#8f9c45':id.includes('bacon')?'#9f5040':'#ecd594'} roughness={.5}/>}</Selections>
 </group></ProductStudio>
}
